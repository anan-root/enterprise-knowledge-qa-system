import pickle
import torch
from langchain_huggingface import HuggingFaceEmbeddings
from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import TextNode
from typing import List
import re
import numpy as np
import os
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), '..', 'app',".env")
# print(f"加载 .env 路径: {os.path.abspath(env_path)}")
# print(f"文件存在: {os.path.exists(env_path)}")
load_dotenv(env_path)

# ========================================
# 级联分块：Markdown层级 → 语义/字数细切分
# ========================================

class CascadingLawSplitter:
    """
    级联分块器：
    第1步：Markdown层级分块（保持章节结构，标题与内容合并，支持多级标题嵌套）
    第2步：对每个块按语义+字数再切分
    """

    def __init__(
            self,
            embed_model,
            max_chunk_size=500,
            overlap=50,
            similarity_threshold=0.75,
    ):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        self.similarity_threshold = similarity_threshold
        self.embed_model = embed_model

        # 第1步：Markdown分块器
        self.markdown_parser = MarkdownNodeParser()

        # 第2步：语义分块器
        self.semantic_splitter = SentenceSplitter(
            chunk_size=max_chunk_size,
            chunk_overlap=overlap,
            separator="。",
            secondary_chunking_regex=r"[；]"
        )

    def split(self, documents: List[Document]) -> List[TextNode]:
        all_nodes = []

        for doc in documents:
            # ========== 第1步：Markdown层级分块 ==========
            md_nodes = self.markdown_parser.get_nodes_from_documents([doc])

            # 关键修改：正确处理多级标题嵌套合并
            merged_nodes = self._merge_heading_with_content(md_nodes)

            for md_node in merged_nodes:
                heading = md_node.metadata.get("heading", "未知")
                text = md_node.text

                # 如果块不大，直接保留
                if len(text) <= self.max_chunk_size:
                    node = TextNode(
                        text=text,
                        metadata={
                            **md_node.metadata,
                            "chunk_level": "markdown",
                            "chunk_index": 0,
                            "total_chunks": 1
                        }
                    )
                    all_nodes.append(node)
                    continue

                # ========== 第2步：长块再细切分 ==========
                sub_chunks = self._smart_split(text)

                for i, chunk in enumerate(sub_chunks):
                    metadata = {
                        **md_node.metadata,
                        "chunk_level": "semantic",
                        "parent_heading": heading,
                        "chunk_index": i,
                        "total_chunks": len(sub_chunks),
                        "parent_length": len(text)
                    }

                    node = TextNode(text=chunk, metadata=metadata)
                    all_nodes.append(node)

        return all_nodes

    def _merge_heading_with_content(self, md_nodes: List[TextNode]) -> List[TextNode]:
        """
        将标题节点与其后的内容节点合并，正确处理多级标题嵌套

        示例：
        # 第一章          → 合并为：# 第一章\n## 第一节\n第一条...
        ## 第一节
        第一条 内容...

        ## 第二节         → 合并为：# 第一章\n## 第二节\n第三条...
        第三条 内容...
        """
        if not md_nodes:
            return []

        def is_heading(node: TextNode) -> bool:
            """判断节点是否为标题（以#开头）"""
            return node.text.strip().startswith('#')

        def get_heading_level(text: str) -> int:
            """获取标题级别（#数量）"""
            if not text.startswith('#'):
                return 0
            return len(text) - len(text.lstrip('#'))

        merged = []
        i = 0

        while i < len(md_nodes):
            current = md_nodes[i]

            if not is_heading(current):
                # 非标题节点，直接保留
                merged.append(current)
                i += 1
                continue

            # 当前是标题，开始收集连续的所有标题（多级嵌套）
            headings = [current]
            heading_texts = [current.text.strip()]
            current_level = get_heading_level(current.text.strip())

            # 向前查找连续的子标题（级别更深的标题）
            j = i + 1
            while j < len(md_nodes):
                next_node = md_nodes[j]
                if not is_heading(next_node):
                    break

                next_level = get_heading_level(next_node.text.strip())
                # 只有级别更深（数字更大）才是子标题，继续累积
                if next_level > current_level:
                    headings.append(next_node)
                    heading_texts.append(next_node.text.strip())
                    current_level = next_level
                    j += 1
                else:
                    # 同级或更高级别，停止累积
                    break

            # 现在 j 指向第一个非标题节点（或文档末尾）
            if j < len(md_nodes):
                # 找到了内容节点，合并所有标题 + 内容
                content_node = md_nodes[j]

                # 构建合并文本：标题层级 + 内容
                merged_text = '\n\n'.join(heading_texts) + '\n\n' + content_node.text

                # 构建元数据
                merged_node = TextNode(
                    text=merged_text,
                    metadata={
                        **content_node.metadata,
                        "heading": heading_texts[0].lstrip('#').strip(),  # 主标题
                        "heading_hierarchy": ' > '.join([
                            h.lstrip('#').strip() for h in heading_texts
                        ]),  # 完整层级路径，如：第一章 > 第一节
                        "heading_level": get_heading_level(heading_texts[0]),
                    }
                )
                merged.append(merged_node)
                i = j + 1  # 跳过已处理的所有节点
            else:
                # 标题后没有内容（文档末尾），直接保留最后一个标题
                merged.append(headings[-1])
                i = j

        return merged

    def _smart_split(self, text: str) -> List[str]:
        """智能切分：先按句子，再按语义相似度合并/切分"""
        sentences = re.split(r'([。；！？])', text)
        sentences = [''.join(i) for i in zip(sentences[::2], sentences[1::2] + [''])]
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 1:
            return [text]

        embeddings = self.embed_model.embed_documents(sentences)
        embeddings = [np.array(e, dtype=np.float32) for e in embeddings]

        chunks = []
        current_chunk = sentences[0]
        current_emb = embeddings[0]

        for i in range(1, len(sentences)):
            next_sent = sentences[i]
            next_emb = embeddings[i]

            similarity = self._cosine_similarity(current_emb, next_emb)

            should_split = (
                                   len(current_chunk) >= self.max_chunk_size and len(next_sent) > 20
                           ) or (
                                   similarity < self.similarity_threshold and len(current_chunk) > 200
                           )

            if should_split:
                chunks.append(current_chunk)
                overlap_text = current_chunk[-self.overlap:] if len(current_chunk) > self.overlap else current_chunk
                current_chunk = overlap_text + next_sent
                current_emb = next_emb
            else:
                current_chunk += next_sent
                current_emb = (current_emb + next_emb) / 2

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    @staticmethod
    def _cosine_similarity(a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)


def save_nodes(nodes, filepath='./nodes_cache.pkl'):
    with open(filepath, 'wb') as f:
        pickle.dump(nodes, f)

def load_nodes(filepath='./nodes_cache.pkl'):
    with open(filepath, 'rb') as f:
        return pickle.load(f)

def md2nodes(file_path,save_path,embed_model,max_chunk_size=400,overlap=50,similarity_threshold=0.75):
    # ========== 0. 读取文件 ==========
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {os.path.abspath(file_path)}")

    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    print(f"📄 读取文件: {file_path}")

    # 包装成 Document 列表
    documents = [Document(text=text, metadata={"source": os.path.basename(file_path)})]


    # ========== 1. 分块 ==========
    splitter = CascadingLawSplitter(embed_model=embed_model,
                                    max_chunk_size=max_chunk_size,
                                    overlap=overlap,
                                    similarity_threshold=similarity_threshold)
    nodes = splitter.split(documents)
    print(f"✂️ 分块完成: {len(nodes)} 个节点")

    save_nodes(nodes,filepath=save_path)
    print(f'已存储{save_path}')


if __name__ == '__main__':

    # device = 'cuda' if torch.cuda.is_available() else 'cpu'
    # print(device)
    #
    # embed_model = HuggingFaceEmbeddings(
    #     model_name=os.getenv("SENTENCE_MODEL", "BAAI/bge-large-zh-v1.5"),
    #     model_kwargs={'device': device},
    #     encode_kwargs={'normalize_embeddings': True}
    # )
    # print('embedding model loaded')
    #
    # md2nodes(file_path='./招标投标法律解读与风险防范实务.md',
    #          save_path='./招标投标法律解读与风险防范实务.pkl',
    #          embed_model=embed_model,
    #          max_chunk_size=400,overlap=50,similarity_threshold=0.75)
    # md2nodes(file_path='./中华人民共和国招标投标法律法规全书.md',
    #          save_path='./中华人民共和国招标投标法律法规全书.pkl',
    #          embed_model=embed_model,
    #          max_chunk_size=400, overlap=50, similarity_threshold=0.75)

    nodes1 = load_nodes('招标投标法律解读与风险防范实务.pkl')
    nodes2 = load_nodes('中华人民共和国招标投标法律法规全书.pkl')

    print(len(nodes1), len(nodes2))


    for i in range(300,305):
        print(nodes1[i])

    print('-'*50)
    for i in range(300,305):
        print(nodes2[i])








