import os
import requests
from dotenv import load_dotenv
from tqdm import tqdm
from pymilvus import (
    connections, Collection, CollectionSchema,
    FieldSchema, DataType, utility
)

from backend.qa_engine.data_processing.nodes2pkl import load_nodes

env_path = os.path.join(os.path.dirname(__file__), '..', 'app', ".env")
load_dotenv(env_path)

# API 配置
MILVUS_HOST = "47.117.173.99"
MILVUS_PORT = "19530"
BGE_M3_URL = "http://47.117.173.99:8000"


def get_embeddings_api(texts: list, batch_size=32) -> list:
    """
    通过 HTTP API 获取文本稠密向量（BGE-M3）
    返回: [[...], ...]  # 稠密向量列表
    """
    all_embeddings = []
    total = len(texts)
    num_batches = (total + batch_size - 1) // batch_size

    for i in tqdm(range(0, total, batch_size),
                  total=num_batches,
                  desc="🚀 API 编码"):
        batch = texts[i:i + batch_size]

        resp = requests.post(
            f"{BGE_M3_URL}/embed",
            json={
                "sentences": batch,
                "return_dense": True,
                # 不发送 return_sparse 参数，或明确设为 False
            },
            timeout=30
        )

        if resp.status_code != 200:
            raise Exception(f"Embedding API 调用失败: {resp.status_code}, {resp.text}")

        result = resp.json()
        all_embeddings.extend(result["dense_embeddings"])

    print(f"✅ 完成编码 {total} 条文本")
    return all_embeddings


def nodes2vector(nodes_path,
                 collection_name='laws',
                 drop_old=False,
                 api_batch_size=32):
    """
    使用 BGE-M3 API 向量化节点并存储到远端 Milvus（仅稠密向量）
    """
    # ========== 0. 读取文件 ==========
    if not os.path.exists(nodes_path):
        raise FileNotFoundError(f"文件不存在: {os.path.abspath(nodes_path)}")

    nodes = load_nodes(nodes_path)
    total_nodes = len(nodes)
    print(f"📄 加载了 {total_nodes} 个节点")

    # ========== 1. 准备数据 ==========
    sources = [node.metadata.get('source', 'unknown') for node in nodes]
    node_ids = [node.id_ if hasattr(node, 'id_') else str(i) for i, node in enumerate(nodes)]
    texts = [node.text for node in nodes]

    # ========== 2. 测试 API 并获取维度 ==========
    print("🔍 测试 API 获取向量维度...")
    test_vector = get_embeddings_api([texts[0]], batch_size=1)[0]
    dim = len(test_vector)
    print(f"✅ 嵌入维度: {dim}")

    # ========== 3. 连接远端 Milvus 服务器 ==========
    print(f"🔌 连接 Milvus 服务器 {MILVUS_HOST}:{MILVUS_PORT}...")
    try:
        connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)
        print(f"✅ Milvus 连接成功")
    except Exception as e:
        print(f"❌ Milvus 连接失败: {e}")
        raise

    # ========== 4. 创建/管理集合 ==========
    collection = None

    if utility.has_collection(collection_name):
        if drop_old:
            utility.drop_collection(collection_name)
            print(f"✓ 已删除旧集合: {collection_name}")
        else:
            collection = Collection(collection_name)
            print(f"✓ 使用已存在集合: {collection_name}")

    # 如果集合不存在或被删除，创建新集合
    if collection is None:
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="node_id", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="chunk_index", dtype=DataType.INT32),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),  # 只用稠密向量
        ]

        schema = CollectionSchema(fields, description="法律文档向量库")
        collection = Collection(collection_name, schema)

        # 创建索引
        index_params = {
            "metric_type": "IP",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        collection.create_index("vector", index_params)

        collection.load()
        print(f"✓ 已创建新集合: {collection_name}")
        start_id = 0
    else:
        collection.load()
        start_id = collection.num_entities
        print(f"✓ 集合已存在，当前 {start_id} 行，将追加数据")

    # ========== 5. 批量编码并插入 ==========
    insert_batch_size = 100
    total_inserted = 0

    print(f"\n🚀 开始编码 {total_nodes} 条文本...")
    all_vectors = get_embeddings_api(texts, batch_size=api_batch_size)

    num_batches = (total_nodes + insert_batch_size - 1) // insert_batch_size

    for batch_idx in tqdm(range(num_batches), desc="插入 Milvus"):
        i = batch_idx * insert_batch_size

        batch_texts = texts[i:i + insert_batch_size]
        batch_sources = sources[i:i + insert_batch_size]
        batch_node_ids = node_ids[i:i + insert_batch_size]
        batch_vectors = all_vectors[i:i + insert_batch_size]

        # 组装数据（仅稠密向量）
        data_to_insert = [
            batch_texts,           # text
            batch_sources,         # source
            batch_node_ids,        # node_id
            list(range(i, i + len(batch_texts))),  # chunk_index
            batch_vectors,         # vector
        ]

        mr = collection.insert(data_to_insert)
        total_inserted += len(mr.primary_keys)

    # ========== 6. 完成 ==========
    print("⏳ 正在执行 Flush 操作...")
    collection.flush()

    final_count = collection.num_entities
    print(f"✅ 完成！集合总行数: {final_count} 条，本次插入: {total_inserted} 条")

    return collection


if __name__ == "__main__":

    nodes2vector(
        nodes_path='招标投标法律解读与风险防范实务.pkl',
        collection_name="laws_m3",
        drop_old=True,
        api_batch_size=32
    )

    nodes2vector(
        nodes_path='中华人民共和国招标投标法律法规全书.pkl',
        collection_name="laws_m3",
        drop_old=False,
        api_batch_size=32
    )