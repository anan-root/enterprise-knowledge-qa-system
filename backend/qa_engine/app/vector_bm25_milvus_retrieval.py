import ast
import asyncio
import time
from pprint import pprint
import requests
from pymilvus import AsyncMilvusClient  # 使用异步客户端连接远端服务器
import os
from dotenv import load_dotenv
from backend.qa_engine.data_processing.nodes2pkl import search_multiple_indices
from simhash import Simhash
from backend.qa_engine.app.questions_classify import async_client

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# API 配置
BGE_M3_URL = os.getenv("BGE_M3_URL")
MILVUS_HOST = os.getenv("MILVUS_HOST")
MILVUS_PORT = os.getenv("MILVUS_PORT")

# 全局变量 + 异步锁
_milvus_initialized = False
_async_client = None
_milvus_lock = asyncio.Lock()

async def get_milvus_client():
    """获取远端 Milvus 异步客户端"""
    global _milvus_initialized, _async_client

    if _milvus_initialized:
        return _async_client

    async with _milvus_lock:
        if _milvus_initialized:
            return _async_client

        # 直接连接远端 Milvus 服务器，不需要启动本地 Lite
        async_client = AsyncMilvusClient(uri=f"http://{MILVUS_HOST}:{MILVUS_PORT}")
        print(f"✅ 已连接远端 Milvus 服务器: {MILVUS_HOST}:{MILVUS_PORT}")

        # 检查可用 collections
        collections = await async_client.list_collections()
        print(f"可用的 Collections: {collections}")

        _async_client = async_client
        _milvus_initialized = True
        return _async_client

async def another_query(query: str) -> str:
    prompt = f"""问题：{query}

请根据问题，基于这个问题，生成一段可能包含答案的文本:

答案："""

    response = await async_client.chat.completions.create(
        model=os.getenv('CLS_MODEL'),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        extra_body={"enable_thinking": False},
        max_tokens=200
    )
    text = response.choices[0].message.content.strip()
    return text

async def get_embedding_api(text: str) -> list:
    """通过 HTTP API 获取文本向量（BGE-M3）"""

    def _call_api():
        resp = requests.post(
            f"{BGE_M3_URL}/embed",
            json={"sentences": [text], "return_dense": True},
            timeout=30
        )
        if resp.status_code != 200:
            raise Exception(f"Embedding API 失败: {resp.status_code}")

        result = resp.json()
        return result["dense_embeddings"][0]

    return await asyncio.to_thread(_call_api)

async def simple_milvus_query(
        query_text: str,
        collection_name: str = "laws_m3",  # 默认用你之前创建的 collection
        similarity_threshold: float = 0.65
):
    """
    使用 HTTP API 获取 embedding，远端 Milvus 进行检索
    """
    # 1. 通过 HTTP API 获取查询向量
    query_vector = await get_embedding_api(query_text)

    # 2. 获取 Milvus 客户端（连接远端服务器）
    client = await get_milvus_client()

    # 3. 执行向量检索
    results = await client.search(
        collection_name=collection_name,
        data=[query_vector],
        limit=15,
        output_fields=["text", "source"]
    )

    # 展平并过滤所有结果
    return [
        {
            'text': r['entity']['text'],
            'source': r['entity']['source'],
            'score': r['distance']
        }
        for result in results
        for r in result
        if r.get('distance', 0) >= similarity_threshold
    ]
# async def simple_milvus_query(
#     query_text: str,
#     collection_name: str = "laws_m3",
#     similarity_threshold: float = 0.65,
#     context_window: int = 1
# ):
#     query_vector = await get_embedding_api(query_text)
#     client = await get_milvus_client()
#
#     results = await client.search(
#         collection_name=collection_name,
#         data=[query_vector],
#         limit=15,
#         output_fields=["text", "source", "chunk_index"]
#     )
#
#     final_results = []
#
#     for hits in results:
#         for hit in hits:
#             if hit.distance < similarity_threshold:
#                 continue
#
#             source = hit.entity["source"]
#             center_idx = hit.entity["chunk_index"]
#
#             start_idx = center_idx - context_window
#             end_idx = center_idx + context_window
#
#             # 查询上下文
#             context_rows = await client.query(
#                 collection_name=collection_name,
#                 filter=(
#                     f'source == "{source}" '
#                     f'&& chunk_index >= {start_idx} '
#                     f'&& chunk_index <= {end_idx}'
#                 ),
#                 output_fields=["chunk_index", "text", "source"],
#                 sort_by="chunk_index"
#             )
#
#             for row in context_rows:
#                 final_results.append({
#                     "text": row["text"],
#                     "source": row["source"],
#                     "chunk_index": row["chunk_index"],
#                     "score": (
#                         hit.distance
#                         if row["chunk_index"] == center_idx
#                         else None
#                     )
#                 })
#
#     return final_results
async def hyde_retrieval(
        query,
        collection_name="laws_m3",  # 默认 collection
        bm25_dir=os.getenv("BM25_DIR"),
        index_paths=ast.literal_eval(os.getenv("INDEX_PATH")),
        bm25_top_k = 20,
        threshold=3
):
    # 准备 BM25 路径
    bm25_paths = [
        os.path.normpath(os.path.join(bm25_dir, ips))
        for ips in index_paths
    ]

    # BM25 + 生成假答案 并行
    bm25_task = search_multiple_indices(bm25_paths, query, bm25_top_k)
    fake_answer_task = another_query(query)
    bm25_results, fake_answer = await asyncio.gather(bm25_task, fake_answer_task)

    # 向量检索并行（查询文本 + 假答案）
    fake_answer_results, query_results = await asyncio.gather(
        simple_milvus_query(fake_answer, collection_name),
        simple_milvus_query(query, collection_name)
    )
    all_docs = bm25_results + query_results + fake_answer_results
    unique_by_simhash = deduplication(all_docs,threshold==threshold)
    return unique_by_simhash

def deduplication(all_docs,threshold=3):
    #精确去重（SimHash）
    unique_by_simhash = []
    seen_hashes = {}

    for doc in all_docs:
        current_simhash = Simhash(doc["text"])
        is_duplicate = False

        for seen_hash_obj in seen_hashes.values():
            # 正确的调用方式：使用Simhash对象的方法
            distance = current_simhash.distance(seen_hash_obj)
            if distance <= threshold:
                is_duplicate = True
                # print(f"检测到重复，海明距离: {distance}")
                break

        if not is_duplicate:
            # 存储Simhash对象，而不仅仅是数值
            seen_hashes[current_simhash.value] = current_simhash
            unique_by_simhash.append(doc)

    return unique_by_simhash

def reranker(
        query: str,
        candidates: list,
        score_threshold: float = 0.7,
        top_k = None,
        BGE_RERANKER_URL: str = os.getenv('BGE_RERANKER_URL')
):
    docs = [c['text'] for c in candidates]
    resp = requests.post(
        f"{BGE_RERANKER_URL}/rerank",
        json={"query": query, "documents": docs, "normalize": True}
    )

    if resp.status_code != 200:
        return candidates

    reranked = resp.json()["results"]
    results =  [
        {
            "index": r["index"],
            "text": r["document"],
            "source": candidates[r['index']]['source'],
            "score": r["relevance_score"]
        }
        for r in reranked
        if r["relevance_score"] >= score_threshold
    ]

    if len(results) > 15:
        results = results[:15]

    if top_k is not None:
        results = results[:top_k]

    return results

# 使用示例
if __name__ == "__main__":
    start = time.time()

    results = asyncio.run(hyde_retrieval(
        "依法必须进行招标的项目，其招标投标活动是否受地区或者部门的限制？",
        collection_name="laws_m3",  # 使用之前创建的 collection
        bm25_dir=os.getenv("BM25_DIR"),
        bm25_top_k=20,
        index_paths=ast.literal_eval(os.getenv("INDEX_PATH"))
    ))

    print(f"检索耗时: {time.time() - start:.2f} 秒")
    # pprint(results)

    # 重排序
    answer = reranker("依法必须进行招标的项目，其招标投标活动是否受地区或者部门的限制？", results,score_threshold=0.7)
    print(len(answer))
    pprint(answer)
