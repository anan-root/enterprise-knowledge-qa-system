import asyncio
import json
from pprint import pprint
from rank_bm25 import BM25Okapi
import pickle
import jieba  # 中文分词


def load_nodes(filepath='./nodes_cache.pkl'):
    with open(filepath, 'rb') as f:
        return pickle.load(f)

def build_and_save_bm25(nodes, save_path):
    """构建 BM25 索引并保存"""
    # 1. 提取文本并分词（中文需要 jieba）
    tokenized_corpus = []
    for node in nodes:
        # jieba 分词，BM25 需要词列表
        tokens = list(jieba.cut(node.text))
        tokenized_corpus.append(tokens)

    # 2. 构建 BM25 索引
    bm25 = BM25Okapi(tokenized_corpus)

    # 3. 保存索引和原始文本（需要保存 corpus 用于后续检索）
    data = {
        'bm25': bm25,
        'corpus': [node.text for node in nodes],  # 原始文本
        'metadata': [node.metadata for node in nodes]  # 元数据
    }

    with open(save_path, 'wb') as f:
        pickle.dump(data, f)

    print(f"✅ BM25 索引已保存: {save_path}")
    print(f"   文档数: {len(tokenized_corpus)}")


def load_bm25(index_path):
    """加载预构建的 BM25 索引"""
    with open(index_path, 'rb') as f:
        data = pickle.load(f)
    return data['bm25'], data['corpus'], data['metadata']


def search_bm25(bm25, corpus, metadata, query, top_k=5):
    """使用 BM25 检索"""
    # 查询分词
    tokenized_query = list(jieba.cut(query))

    # 获取分数
    scores = bm25.get_scores(tokenized_query)

    # 取 top_k
    import numpy as np
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        if scores[idx] > 0:  # 过滤无匹配结果
            results.append({
                'text': corpus[idx],
                'source': metadata[idx]['source'],
                'score': float(scores[idx])
            })

    return results


async def search_multiple_indices(index_paths :list, query, top_k=5):
    async def _search_single(path):
        """单个索引的异步搜索"""
        def _sync_search():
            bm25, corpus, metadata = load_bm25(path)
            return search_bm25(bm25, corpus, metadata, query, top_k=top_k)
            # 在线程池中执行（释放事件循环）
        return await asyncio.to_thread(_sync_search)
        # 并行执行所有索引搜索
    all_results_lists = await asyncio.gather(
            *[_search_single(path) for path in index_paths]
        )
    # 合并结果
    all_results = []
    for results in all_results_lists:
        all_results.extend(results)

    # 按分数排序
    all_results.sort(key=lambda x: x['score'], reverse=True)
    return all_results[:top_k]
# ========== 使用示例 ==========

if __name__ == '__main__':
    # # 1. 首次构建（只需一次）
    # nodes1 = load_nodes('招标投标法律解读与风险防范实务.pkl')
    # build_and_save_bm25(nodes1, '招标投标法律解读与风险防范实务_bm25.pkl')
    #
    # nodes2 = load_nodes('中华人民共和国招标投标法律法规全书.pkl')
    # build_and_save_bm25(nodes2, '中华人民共和国招标投标法律法规全书_bm25.pkl')

    # # 2. 后续检索（直接加载索引，秒开）
    # bm25, corpus, metadata = load_bm25('招标投标法律解读与风险防范实务_bm25.pkl')
    # results = search_bm25(bm25, corpus, metadata, "投标保证金退还", top_k=5)
    #
    # for r in results:
    #     pprint(r)
    # index_paths = ['招标投标法律解读与风险防范实务_bm25.pkl','中华人民共和国招标投标法律法规全书_bm25.pkl']
    # all_results = asyncio.run(search_multiple_indices(index_paths,'招标流程是什么',10))
    # for result in all_results:
    #     print(result)

    # bm25,corpus, metadata=load_bm25('招标投标法律解读与风险防范实务_bm25.pkl')
    # print(type(bm25))
    # print(type(corpus))
    # print(type(metadata))
    #
    # print(bm25)
    # print(corpus[100])
    # print(metadata[100])

    with open('中华人民共和国招标投标法律法规全书_bm25.pkl', 'rb') as f:
        data = pickle.load(f)
    texts = []
    for i in data['corpus']:
        i = i.replace('\n\n', '')
        texts.append(i)
        texts.append('-'*20)
    texts = '\n'.join(texts)
    with open('中华人民共和国招标投标法律法规全书_bm25.txt','w', encoding='utf-8') as f:
        f.write(texts)
    # result = asyncio.run(search_multiple_indices(['招标投标法律解读与风险防范实务_bm25.pkl'],'招标流程有哪些？'))
    # print(result)


