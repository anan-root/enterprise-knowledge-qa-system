import ast
import asyncio
import json
import os
import logging
from backend.qa_engine.app.questions_classify import async_classify_question_cot
from backend.qa_engine.app.vector_bm25_milvus_retrieval import hyde_retrieval, reranker
logger = logging.getLogger(__name__)

async def get_retrieval_chunks(user_question):
    cls_question = await async_classify_question_cot(user_question)
    print(cls_question)

    all_chunks = []
    for q_cls in cls_question:
        if q_cls[1]=='F':
            chunks = await hyde_retrieval(
                q_cls[0],
                collection_name="laws_m3",  # 默认 collection
                bm25_dir=os.getenv("BM25_DIR"),
                index_paths=ast.literal_eval(os.getenv("INDEX_PATH")),
                bm25_top_k=20,
                threshold=3
            )

            chunks = reranker(user_question, chunks, score_threshold=0.7,top_k=None)
            all_chunks.extend(chunks)
        else:
            all_chunks.append({"text": '分类错误！'})
    return all_chunks


async def get_q_r_a(q_a,timeout_per_query=60,max_concurrent=5, batch_size = 20):
    q_r_a = []

    semaphore = asyncio.Semaphore(max_concurrent)
    async def process_item(item):
        async with semaphore:
            try:
                # 设置单个查询的超时
                retrieval_chunks = await asyncio.wait_for(
                    get_retrieval_chunks(item['user_question']),
                    timeout=timeout_per_query
                )
                return {
                    'user_question': item['user_question'],
                    'answer_chunks': item['answer_chunks'] if isinstance(item['answer_chunks'], list) else [item['answer_chunks']],
                    'retrieval_chunks': [i['text'] for i in retrieval_chunks],
                }
            except asyncio.TimeoutError:
                logger.warning(f"查询超时: {item['user_question'][:50]}...")
                return {
                    'user_question': item['user_question'],
                    'answer_chunks': item['answer_chunks'],
                    'retrieval_chunks': ['查询超时!'],
                }
            except Exception as e:
                logger.error(f"查询失败: {item['user_question'][:50]}... 错误: {str(e)}")
                return {
                    'user_question': item['user_question'],
                    'answer_chunks': item['answer_chunks'],
                    'retrieval_chunks': ['查询错误！'],
                }

    for i in range(0,len(q_a),batch_size):
        tasks = []
        for item in q_a[i:i+batch_size]:
            task = asyncio.create_task(process_item(item))
            tasks.append((task,item))

        batch_results = await asyncio.gather(*[task for task,_ in tasks])

        q_r_a.extend(batch_results)
    return q_r_a

if __name__ == '__main__':
    with open('q_a_merged.json', 'r', encoding='utf-8') as f:
        q_a = json.load(f)
    q_r_a = asyncio.run(get_q_r_a(q_a))

    with open('q_r_a_merged.json', 'w', encoding='utf-8') as f:
        json.dump(q_r_a,f,ensure_ascii=False,indent=4)




