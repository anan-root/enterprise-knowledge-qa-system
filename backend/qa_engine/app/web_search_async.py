import asyncio
import os
import re
import hashlib
from pprint import pprint

import aiohttp
from typing import List, Dict, Optional
from dataclasses import dataclass
from dotenv import load_dotenv
from pathlib import Path
import numpy as np

# 加载环境变量
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

try:
    from bs4 import BeautifulSoup

    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


@dataclass
class Document:
    content: str
    title: str
    source: str
    doc_type: str
    chunk_index: int = 0
    total_chunks: int = 1
    score: float = 0.0

    def __post_init__(self):
        if not hasattr(self, 'doc_id'):
            self.doc_id = hashlib.md5(f"{self.source}_{self.chunk_index}".encode()).hexdigest()[:16]


from backend.qa_engine.app.vector_bm25_milvus_retrieval import get_embedding_api


class AsyncWebRetriever:
    def __init__(
            self,
            serper_api_key: Optional[str] = None,
            chunk_size: int = 600,
            chunk_overlap: int = 80,
            fetch_timeout: int = 10,
            min_content_length: int = 50,
            min_score: float = 0.5,
            max_concurrent: int = 5,
            max_retries: int = 2,
    ):
        self.api_key = serper_api_key or SERPER_API_KEY
        if not self.api_key:
            raise ValueError("SERPER_API_KEY 未设置")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.fetch_timeout = fetch_timeout
        self.min_content_length = min_content_length
        self.min_score = min_score  # 严格过滤阈值
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.google.com/',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        self.serper_headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }

        self.semaphore = asyncio.Semaphore(max_concurrent)

        self.connector = aiohttp.TCPConnector(
            limit=50,
            limit_per_host=10,
            use_dns_cache=True,
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
            force_close=False,
        )

        self.timeout = aiohttp.ClientTimeout(
            total=fetch_timeout,
            connect=5,
            sock_read=fetch_timeout
        )

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            connector=self.connector,
            timeout=self.timeout,
            skip_auto_headers={'User-Agent'},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'session') and self.session:
            await self.session.close()
        await self.connector.close()

    async def search(self, query: str, num_results: int) -> List[Dict]:
        """异步搜索"""
        url = "https://google.serper.dev/search"
        payload = {
            "q": query,
            "gl": "cn",
            "hl": "zh-cn",
            "num": num_results
        }

        try:
            async with self.session.post(
                    url,
                    headers=self.serper_headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                response.raise_for_status()
                data = await response.json()

                results = []
                for item in data.get('organic', []):
                    results.append({
                        'title': item.get('title', '').strip(),
                        'link': item.get('link', '').strip(),
                        'snippet': item.get('snippet', '').strip(),
                    })
                return results
        except Exception as e:
            print(f"搜索失败: {e}")
            return []

    async def fetch_webpage(self, url: str) -> Optional[str]:
        """真异步抓取 - 修复乱码问题"""
        async with self.semaphore:
            for attempt in range(self.max_retries + 1):
                try:
                    async with self.session.get(
                            url,
                            allow_redirects=True,
                            ssl=False
                    ) as response:
                        if response.status != 200:
                            return None

                        # 改进编码处理：优先使用响应头中的编码，自动检测备用
                        content = await response.read()

                        # 尝试从Content-Type获取编码
                        charset = response.charset
                        if charset:
                            try:
                                text = content.decode(charset, errors='ignore')
                            except (UnicodeDecodeError, LookupError):
                                text = None

                        # 如果失败，尝试常见中文编码
                        if not text:
                            for encoding in ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5']:
                                try:
                                    text = content.decode(encoding, errors='ignore')
                                    # 验证解码是否成功（检查是否有明显乱码特征）
                                    if self._is_valid_chinese_text(text):
                                        break
                                except (UnicodeDecodeError, LookupError):
                                    continue
                            else:
                                # 都失败则用utf-8强制解码
                                text = content.decode('utf-8', errors='ignore')

                        if BS4_AVAILABLE:
                            text = self._extract_with_bs4(text)
                        else:
                            text = self._extract_simple(text)

                        text = self._clean_text(text)

                        # 过滤乱码内容：如果乱码比例过高，返回None
                        if not self._is_valid_chinese_text(text):
                            print(f"内容乱码过多，丢弃: {url}")
                            return None

                        return text if len(text) >= self.min_content_length else None

                except Exception as e:
                    print(f"抓取失败 {url}, 尝试 {attempt + 1}: {e}")
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.5)
                        continue
                    return None

    def _is_valid_chinese_text(self, text: str, threshold: float = 0.3) -> bool:
        """检查文本是否为有效中文内容，过滤乱码"""
        if not text:
            return False

        # 统计中文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(re.findall(r'\w', text))

        if total_chars == 0:
            return False

        chinese_ratio = chinese_chars / total_chars

        # 检查是否有大量乱码特征（如连续的非打印字符、异常符号）
        garbage_pattern = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x80-\x9f\uFFFD\u0000-\u0019]{3,}')
        has_garbage = bool(garbage_pattern.search(text))

        # 中文比例足够且没有大量乱码
        return chinese_ratio > threshold and not has_garbage

    def _extract_with_bs4(self, html: str) -> str:
        """提取内容"""
        soup = BeautifulSoup(html, 'html.parser')

        for tag in soup(['script', 'style', 'nav', 'header', 'footer',
                         'aside', 'advertisement', 'iframe', 'form', 'noscript']):
            tag.decompose()

        selectors = [
            'article', 'main', '[role="main"]',
            '.content', '.article-content', '.post-content',
            '#content', '#main-content',
            '.detail', '.text-content',
        ]

        content_text = []

        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                texts = element.stripped_strings
                for text in texts:
                    if len(text) > 5:
                        content_text.append(text)

                total_len = sum(len(t) for t in content_text)
                if total_len > 1000:
                    break
            if sum(len(t) for t in content_text) > 1000:
                break

        if not content_text or sum(len(t) for t in content_text) < 200:
            body = soup.find('body')
            if body:
                for elem in body.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'div']):
                    class_id = ' '.join(elem.get('class', [])) + ' ' + elem.get('id', '')
                    if any(bad in class_id.lower() for bad in ['nav', 'menu', 'ad', 'banner', 'sidebar']):
                        continue
                    text = elem.get_text(strip=True)
                    if len(text) > 10:
                        content_text.append(text)

        return '\n'.join(content_text)

    def _extract_simple(self, html: str) -> str:
        """简单正则提取（备用）"""
        text = re.sub(r'<(script|style|noscript).*?>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = ' '.join(text.split())
        return text

    def _clean_text(self, text: str) -> str:
        """清洗文本"""
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text, flags=re.UNICODE)
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()

    def split_text(self, text: str) -> List[str]:
        """分块"""
        if not text:
            return []

        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        if not paragraphs:
            return []

        chunks = []
        current_chunk_parts = []
        current_length = 0

        for para in paragraphs:
            para_len = len(para)

            if para_len > self.chunk_size:
                if current_chunk_parts:
                    chunks.append('\n'.join(current_chunk_parts))
                    current_chunk_parts = []
                    current_length = 0

                sentences = re.split(r'(?<=[。！？.!?])\s+', para)
                temp_parts = []
                temp_length = 0

                for sent in sentences:
                    sent = sent.strip()
                    if not sent:
                        continue
                    sent_len = len(sent)

                    if temp_length + sent_len > self.chunk_size and temp_parts:
                        chunk_text = ''.join(temp_parts)
                        if len(chunk_text) >= self.min_content_length:
                            chunks.append(chunk_text)

                        overlap = temp_parts[-1] if temp_parts else ''
                        if len(overlap) > self.chunk_overlap:
                            overlap = overlap[-self.chunk_overlap:]

                        temp_parts = [overlap, sent] if overlap else [sent]
                        temp_length = sum(len(s) for s in temp_parts)
                    else:
                        temp_parts.append(sent)
                        temp_length += sent_len

                if temp_parts:
                    remaining = ''.join(temp_parts)
                    if len(remaining) >= self.min_content_length:
                        chunks.append(remaining)
                continue

            if current_length + para_len > self.chunk_size and current_chunk_parts:
                chunk_text = '\n'.join(current_chunk_parts)
                if len(chunk_text) >= self.min_content_length:
                    chunks.append(chunk_text)

                overlap_text = current_chunk_parts[-1] if current_chunk_parts else ''
                if len(overlap_text) > self.chunk_overlap:
                    overlap_text = overlap_text[-self.chunk_overlap:]

                if overlap_text and len(overlap_text) < self.chunk_overlap:
                    current_chunk_parts = [overlap_text, para]
                    current_length = len(overlap_text) + para_len
                else:
                    current_chunk_parts = [para]
                    current_length = para_len
            else:
                current_chunk_parts.append(para)
                current_length += para_len

        if current_chunk_parts:
            final_chunk = '\n'.join(current_chunk_parts)
            if len(final_chunk) >= self.min_content_length:
                chunks.append(final_chunk)

        return chunks

    async def calculate_similarity(self, query: str, chunks: List[str]) -> List[tuple]:
        """计算相似度（使用异步 Embedding API）"""
        if not chunks:
            return []

        all_texts = [query] + chunks

        # 并发获取所有 embedding
        tasks = [get_embedding_api(text) for text in all_texts]
        embeddings = await asyncio.gather(*tasks, return_exceptions=True)

        # 检查失败
        failed_indices = [i for i, emb in enumerate(embeddings) if isinstance(emb, Exception)]
        if failed_indices:
            for i in failed_indices:
                print(f"第 {i} 个文本 embedding 失败: {embeddings[i]}")
            # 如果有失败，用零向量占位
            expected_dim = 1024  # bge-m3 默认维度，可根据实际调整
            for i in failed_indices:
                embeddings[i] = [0.0] * expected_dim

        # 确保所有 embedding 有效
        for i, emb in enumerate(embeddings):
            if isinstance(emb, Exception):
                embeddings[i] = [0.0] * 1024

        # 分离 query 和 chunks 的向量
        query_embedding = np.array(embeddings[0], dtype=np.float32)
        chunk_embeddings = np.array(embeddings[1:], dtype=np.float32)

        # 检查 query 是否为零向量
        query_norm = np.linalg.norm(query_embedding)
        if query_norm == 0:
            print("警告: query embedding 是零向量")
            return [(i, 0.0) for i in range(len(chunks))]

        # 计算余弦相似度
        chunk_norms = np.linalg.norm(chunk_embeddings, axis=1)
        chunk_norms = np.maximum(chunk_norms, 1e-8)

        cos_scores = np.dot(chunk_embeddings, query_embedding) / (chunk_norms * query_norm)

        scores = [(i, float(cos_scores[i])) for i in range(len(chunks))]
        scores.sort(key=lambda x: x[1], reverse=True)

        print(f"相似度计算完成: top3 = {[s[1] for s in scores[:3]]}")
        return scores

    async def process_single_page(self, query: str, result: Dict, top_k_per_page: int) -> List[Document]:
        """异步处理单个页面 - 严格过滤低分内容"""
        title = result['title']
        link = result['link']
        snippet = result['snippet']

        full_content = await self.fetch_webpage(link)
        documents = []

        if full_content:
            chunks = self.split_text(full_content)

            if not chunks:
                # 只有当snippet分数足够时才保留
                # 这里给snippet一个基础分，但必须满足min_score
                snippet_score = 0.5  # snippet基础分较低
                if snippet_score >= self.min_score:
                    doc = Document(
                        content=snippet,
                        title=title,
                        source=link,
                        doc_type='snippet_fallback',
                        chunk_index=0,
                        total_chunks=1,
                        score=snippet_score
                    )
                    documents.append(doc)
                return documents

            # 相似度计算
            try:
                ranked = await self.calculate_similarity(query, chunks)
            except Exception as e:
                print(f"相似度计算异常 {link}: {e}")
                ranked = []

            if not ranked:
                return documents  # 直接返回空，不再强制保底

            # 严格过滤：只保留满足min_score的片段
            selected = [(idx, score) for idx, score in ranked[:top_k_per_page]
                        if score >= self.min_score]

            for idx, score in selected:
                doc = Document(
                    content=chunks[idx],
                    title=title,
                    source=link,
                    doc_type='full_content',
                    chunk_index=idx,
                    total_chunks=len(chunks),
                    score=score
                )
                documents.append(doc)

            # 移除保底逻辑：不再强制保留低分内容
            # 如果该页面没有满足条件的内容，直接返回空列表
        else:
            # 抓取失败时，snippet也不保留（因为无法验证相关性）
            # 或者可以选择保留，但这里选择严格模式
            pass

        return documents

    async def retrieve(self, query: str, num_results: int, top_k_per_page: int) -> List[Document]:
        """异步检索主入口"""
        search_results = await self.search(query, num_results)
        print(f"搜索返回 {len(search_results)} 个结果")

        if not search_results:
            return []

        tasks = [
            self.process_single_page(query, result, top_k_per_page)
            for result in search_results
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_documents = []
        for i, docs in enumerate(results):
            if isinstance(docs, Exception):
                print(f"第 {i + 1} 个结果处理异常: {docs}")
                continue
            all_documents.extend(docs)

        print(f"合并前共 {len(all_documents)} 个文档")

        # 最终过滤：再次确保所有文档满足min_score（双重保险）
        all_documents = [doc for doc in all_documents if doc.score >= self.min_score]

        all_documents.sort(key=lambda x: x.score, reverse=True)
        print(f"过滤后返回 {len(all_documents)} 个结果")
        return all_documents


# ========== 对外接口函数 ==========

async def web_search_rag(
        query: str,
        num_results: int = 5,
        top_k_per_page: int = 2,
        min_score: float = 0.7,
        max_concurrent: int = 5,
        fetch_timeout: int = 10,
) -> List[Dict]:
    """网页搜索RAG异步接口函数"""
    async with AsyncWebRetriever(
            min_score=min_score,
            max_concurrent=max_concurrent,
            fetch_timeout=fetch_timeout,
    ) as retriever:
        documents = await retriever.retrieve(query, num_results, top_k_per_page)

    return [
        {
            'content': doc.content,
            'title': doc.title,
            'source': doc.source,
            'score': doc.score,
            'doc_type': doc.doc_type,
            'chunk_index': doc.chunk_index,
            'total_chunks': doc.total_chunks
        }
        for doc in documents
    ]


# ========== 使用示例 ==========

async def main():
    import time

    start = time.time()
    results = await web_search_rag(
        query="房地产产业链有哪些",
        num_results=5,
        top_k_per_page=2,
        min_score=0.7,
        max_concurrent=5,
        fetch_timeout=8,
    )
    elapsed = time.time() - start

    print(f"\n{'=' * 60}")
    print(f"⏱️ 总耗时: {elapsed:.2f} 秒")
    print(f"{'=' * 60}")

    # for i, r in enumerate(results[:5], 1):
    #     print(f"\n【结果 {i}】{r['title']}")
    #     print(f"   来源: {r['source']}")
    #     print(f"   分数: {r['score']:.3f} | 类型: {r['doc_type']}")
    #     print(f"   内容: {r['content'][:200]}...")
    #     print(f"   片段: {r['chunk_index'] + 1}/{r['total_chunks']}")
    pprint(results)

if __name__ == '__main__':
    asyncio.run(main())