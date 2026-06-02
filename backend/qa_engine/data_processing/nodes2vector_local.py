import os
import pickle
from dotenv import load_dotenv
import torch
from langchain_huggingface import HuggingFaceEmbeddings
from pymilvus import MilvusClient
from milvus import default_server  # 新增
from tqdm import tqdm


def load_nodes(filepath='./nodes_cache.pkl'):
    with open(filepath, 'rb') as f:
        return pickle.load(f)

# ========== 环境初始化（只执行一次）==========
env_path = os.path.join(os.path.dirname(__file__), '..', 'app', ".env")
load_dotenv(env_path)


def nodes2vector(nodes_path, save_path=os.getenv("VECTOR_DATA"), collection_name='laws', drop_old=False):
    # ========== 0. 读取文件 ==========
    if not os.path.exists(nodes_path):
        raise FileNotFoundError(f"文件不存在: {os.path.abspath(nodes_path)}")

    nodes = load_nodes(nodes_path)

    # ========== 2. 存入 Milvus ==========
    # 启动 Milvus Lite 服务（如果未运行）

    data_dir = save_path
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True) #新建保存向量目录

    default_server.set_base_dir(data_dir) #告诉 Milvus Lite 把数据库文件存到哪里
    if not default_server.running:
        default_server.start()
        print(f"✓ Milvus Lite 已启动，数据目录: {data_dir}")

    host = "127.0.0.1"
    port = default_server.listen_port

    # 创建 Milvus 客户端连接
    client = MilvusClient(uri=f"http://{host}:{port}")

    test_vector = embeddings.embed_query("test")
    dim = len(test_vector)
    print(f'嵌入维度{dim}')

    # ========== 4. 创建集合并插入 ==========
    if client.has_collection(collection_name):
        if drop_old:
            # 直接删除并重建集合（Milvus Lite 最可靠的方式）
            client.drop_collection(collection_name=collection_name)
            print(f"✓ 已删除旧集合: {collection_name}")

    # 创建集合（如果不存在）
    if not client.has_collection(collection_name):
        client.create_collection(
            collection_name=collection_name,
            dimension=dim,
            metric_type="IP",
            consistency_level="Strong"
        )
        start_id = 0
        print(f"✓ 已创建新集合: {collection_name}")
    else:
        # 追加模式：获取当前行数
        stats = client.get_collection_stats(collection_name)
        start_id = stats["row_count"]
        print(f"✓ 集合已存在，当前 {start_id} 行，将追加数据")

    # ========== 5. 小批次流式处理（关键修改）==========
    batch_size = 32
    total_nodes = len(nodes)
    total_inserted = 0

    sources = [node.metadata.get('source', 'unknown') for node in nodes]
    node_ids = [node.id_ if hasattr(node, 'id_') else str(i) for i, node in enumerate(nodes)]
    texts = [node.text for node in nodes]

    # 计算总批次数用于 tqdm
    num_batches = (total_nodes + batch_size - 1) // batch_size

    for batch_idx in tqdm(range(num_batches), desc="编码并插入向量"):
        i = batch_idx * batch_size

        batch_texts = texts[i:i + batch_size]
        batch_sources = sources[i:i + batch_size]
        batch_node_ids = node_ids[i:i + batch_size]

        batch_vectors = embeddings.embed_documents(batch_texts)

        data = []
        for j in range(len(batch_texts)):
            record = {
                "id": start_id + i + j,
                "vector": batch_vectors[j],
                "text": batch_texts[j],
                "source": str(batch_sources[j]),
                "node_id": str(batch_node_ids[j]),
                "chunk_index": i + j,
            }
            data.append(record)

        client.insert(collection_name=collection_name, data=data)
        total_inserted += len(data)

        if device == 'cuda':
            torch.cuda.empty_cache()

    print("⏳ 正在执行 Flush 操作，请稍候...")
    client.flush(collection_name=collection_name)

    # ✅ 修复：最后验证总行数
    final_stats = client.get_collection_stats(collection_name)
    print(f"✅ 完成！集合总行数: {final_stats['row_count']} 条")

if __name__ == '__main__':
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    embeddings = HuggingFaceEmbeddings(
        model_name=os.getenv("SENTENCE_MODEL", "BAAI/bge-large-zh-v1.5"),
        model_kwargs={'device': device},
        encode_kwargs={'normalize_embeddings': True}
    )
    print(f'✅ Embedding model loaded on {device}')



    r1 = nodes2vector(nodes_path='招标投标法律解读与风险防范实务.pkl', collection_name='laws', drop_old=True)
    r2 = nodes2vector(nodes_path='中华人民共和国招标投标法律法规全书.pkl',
                      collection_name='laws', drop_old=False)

