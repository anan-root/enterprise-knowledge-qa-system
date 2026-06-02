import os

from dotenv import load_dotenv
from pymilvus import (
    Collection, CollectionSchema, DataType, FieldSchema,
    connections, utility,
)

env_path = os.path.join(os.path.dirname(__file__), "..", "app", ".env")
load_dotenv(env_path)

MILVUS_HOST = os.getenv("MILVUS_HOST", "47.117.173.99")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = "bid_conversations"


def create_collection(drop_old=False):
    print(f"Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT}...")
    connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)
    print("Connected to Milvus")

    if utility.has_collection(COLLECTION_NAME):
        if drop_old:
            utility.drop_collection(COLLECTION_NAME)
            print(f"Dropped existing collection: {COLLECTION_NAME}")
        else:
            print(f"Collection {COLLECTION_NAME} already exists, skipping creation")
            return Collection(COLLECTION_NAME)

    dim = 1024

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="session_id", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="messages_json", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="summary", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="summary_vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="created_at", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="updated_at", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="is_starred", dtype=DataType.BOOL),
        FieldSchema(name="message_count", dtype=DataType.INT32),
    ]

    schema = CollectionSchema(fields, description="Conversation history")
    collection = Collection(COLLECTION_NAME, schema)

    index_params = {
        "metric_type": "IP",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128},
    }
    collection.create_index("summary_vector", index_params)
    collection.load()
    print(f"Collection {COLLECTION_NAME} created with index")


if __name__ == "__main__":
    create_collection(drop_old=False)
