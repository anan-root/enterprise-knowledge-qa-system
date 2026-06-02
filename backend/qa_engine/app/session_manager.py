import asyncio
import json
import os
from datetime import datetime

import requests
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pymilvus import AsyncMilvusClient  # type: ignore

from backend.qa_engine.app.redis_client import get_redis

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

COLLECTION_NAME = "bid_conversations"
MESSAGES_TTL = 3 * 24 * 3600
MAX_RECENT = 20
COMPRESS_BATCH_SIZE = 10
KEEP_FULL_TURNS = 10

_milvus_client: AsyncMilvusClient | None = None
_milvus_lock = asyncio.Lock()
_llm_client = None


async def _get_milvus():
    global _milvus_client
    if _milvus_client is not None:
        return _milvus_client
    async with _milvus_lock:
        if _milvus_client is not None:
            return _milvus_client
        host = os.getenv("MILVUS_HOST", "47.117.173.99")
        port = os.getenv("MILVUS_PORT", "19530")
        _milvus_client = AsyncMilvusClient(uri=f"http://{host}:{port}")
        return _milvus_client


def _get_embedding(text: str) -> list:
    url = os.getenv("BGE_M3_URL", "http://47.117.173.99:8000")
    resp = requests.post(
        f"{url}/embed",
        json={"sentences": [text], "return_dense": True},
        timeout=30,
    )
    if resp.status_code != 200:
        raise Exception(f"Embedding API failed: {resp.status_code}")
    return resp.json()["dense_embeddings"][0]


def _get_llm():
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            api_key=os.getenv("API_KEY"),
            base_url=os.getenv("BASE_URL"),
        )
    return _llm_client


def _now():
    return datetime.now().isoformat()


def _zero_vector(dim=1024):
    return [0.0] * dim


# ---------------------------------------------------------------------------
# Redis helpers (gracefully degrade if Redis unavailable)
# ---------------------------------------------------------------------------

async def _cache_meta(meta_list: list):
    r = await get_redis()
    if r:
        await r.set("sessions:meta", json.dumps(meta_list, ensure_ascii=False))


async def _read_meta() -> list | None:
    r = await get_redis()
    if r is None:
        return None
    raw = await r.get("sessions:meta")
    return json.loads(raw) if raw else None


async def _cache_messages(sid: str, messages: list):
    r = await get_redis()
    if r:
        await r.setex(
            f"session:{sid}:msgs",
            MESSAGES_TTL,
            json.dumps(messages, ensure_ascii=False),
        )


async def _read_messages(sid: str) -> list | None:
    r = await get_redis()
    if r is None:
        return None
    raw = await r.get(f"session:{sid}:msgs")
    return json.loads(raw) if raw else None


async def _track_recent(sid: str):
    r = await get_redis()
    if r is None:
        return
    score = datetime.now().timestamp()
    await r.zadd("sessions:recent", {sid: score})
    await r.zremrangebyrank("sessions:recent", 0, -(MAX_RECENT + 1))


async def _invalidate(sid: str):
    r = await get_redis()
    if r:
        await r.delete(f"session:{sid}:msgs", "sessions:meta")


async def _rebuild_meta():
    try:
        client = await _get_milvus()
        results = await client.query(
            collection_name=COLLECTION_NAME,
            filter="",
            output_fields=[
                "session_id", "title", "created_at", "updated_at",
                "is_starred", "message_count",
            ],
            limit=10000,
        )
        meta = []
        for row in results:
            meta.append({
                "session_id": row["session_id"],
                "title": row.get("title", "新会话"),
                "created_at": row.get("created_at", ""),
                "updated_at": row.get("updated_at", ""),
                "is_starred": row.get("is_starred", False),
                "message_count": row.get("message_count", 0),
            })
        meta.sort(key=lambda x: x["updated_at"] or x["created_at"] or "", reverse=True)
        await _cache_meta(meta)
        return meta
    except Exception as e:
        print(f"Rebuild meta failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Milvus helpers
# ---------------------------------------------------------------------------

async def _milvus_insert(
    sid: str,
    title: str,
    messages_json: str = "[]",
    summary: str = "",
    summary_vector: list | None = None,
    created_at: str = "",
    updated_at: str = "",
    is_starred: bool = False,
    message_count: int = 0,
    replace: bool = False,
):
    try:
        client = await _get_milvus()

        if replace:
            await client.delete(
                collection_name=COLLECTION_NAME,
                filter=f'session_id == "{sid}"',
            )

        now = _now()
        data = [{
            "session_id": sid,
            "title": title,
            "messages_json": messages_json,
            "summary": summary,
            "summary_vector": summary_vector or _zero_vector(),
            "created_at": created_at or now,
            "updated_at": updated_at or now,
            "is_starred": is_starred,
            "message_count": message_count,
        }]
        await client.insert(collection_name=COLLECTION_NAME, data=data)
    except Exception as e:
        print(f"Milvus insert failed for {sid}: {e}")


async def _milvus_query(sid: str) -> dict | None:
    try:
        client = await _get_milvus()
        results = await client.query(
            collection_name=COLLECTION_NAME,
            filter=f'session_id == "{sid}"',
            output_fields=["*"],
            limit=1,
        )
        return results[0] if results else None
    except Exception as e:
        print(f"Milvus query failed for {sid}: {e}")
        return None


async def _milvus_query_all() -> list:
    try:
        client = await _get_milvus()
        return await client.query(
            collection_name=COLLECTION_NAME,
            filter="",
            output_fields=["*"],
            limit=10000,
        )
    except Exception as e:
        print(f"Milvus query_all failed: {e}")
        return []


async def _milvus_delete(sid: str):
    try:
        client = await _get_milvus()
        await client.delete(
            collection_name=COLLECTION_NAME,
            filter=f'session_id == "{sid}"',
        )
    except Exception as e:
        print(f"Milvus delete failed for {sid}: {e}")


# ---------------------------------------------------------------------------
# Batch compression helpers
# ---------------------------------------------------------------------------

def _count_turns(messages: list) -> int:
    return sum(1 for m in messages if isinstance(m, dict) and m.get("role") == "user")


def _parse_turns(messages: list) -> list:
    """将原始消息列表按 Q&A 轮次分组。"""
    turns = []
    i = 0
    while i < len(messages):
        item = messages[i]
        if isinstance(item, dict) and item.get("role") == "user":
            user_content = item.get("content", "")
            assistant_content = ""
            if i + 1 < len(messages):
                next_item = messages[i + 1]
                if isinstance(next_item, dict) and next_item.get("role") == "assistant":
                    assistant_content = next_item.get("content", "")
                    i += 2
                else:
                    i += 1
            else:
                i += 1
            turns.append({"user": user_content, "assistant": assistant_content})
        else:
            i += 1
    return turns


def _parse_summary(summary_str: str) -> tuple:
    """解析摘要 JSON，返回 (compressed_turns, text)。兼容原始纯文本格式。"""
    if not summary_str:
        return 0, ""
    try:
        data = json.loads(summary_str)
        return data.get("compressed_turns", 0), data.get("text", "")
    except (json.JSONDecodeError, TypeError):
        return 0, summary_str


def _build_summary(compressed_turns: int, text: str) -> str:
    return json.dumps({"compressed_turns": compressed_turns, "text": text}, ensure_ascii=False)


async def _summarize_turns_batch(turns: list, batch_start: int, batch_end: int) -> str:
    """将一批对话轮次压缩为摘要文本。"""
    lines = []
    for i, t in enumerate(turns, batch_start + 1):
        lines.append(f"第{i}轮 - 用户：{t['user']}")
        if t["assistant"]:
            text = t["assistant"]
            truncated = text[:300] + ("..." if len(text) > 300 else "")
            lines.append(f"第{i}轮 - 助手：{truncated}")

    conversation_text = "\n".join(lines)

    prompt = f"""请从以下对话中提取关键信息，生成一份简洁的摘要。只保留对后续问题改写可能有用的信息。

【提取内容】
- 提到的实体名称（公司全称、人名、项目名等）
- 用户关注的主题和方向
- 助手提供过的重要结论或数据
- 对话中建立的上下文关系

【对话内容（第{batch_start + 1}-{batch_end}轮）】
{conversation_text}

请直接输出摘要（不超过200字），不要多余文字："""

    try:
        client = _get_llm()
        response = await client.chat.completions.create(
            model=os.getenv("CLS_MODEL", "qwen3.6-27b"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=300,
            extra_body={"enable_thinking": False},
        )
        summary = response.choices[0].message.content.strip()
        return summary if summary else ""
    except Exception as e:
        print(f"[memory] 批次压缩失败: {e}")
        return ""


async def _batch_compress(messages: list, current_summary_str: str) -> str | None:
    """每满 10 轮且超出的第一个轮次触发压缩。

    触发时机：第 11、21、31... 轮对话结束后。
    例如第 11 轮时压缩 1-10 轮，第 21 轮时压缩 11-20 轮。
    始终保留最近 10 轮完整文本，压缩的是刚刚移出窗口的那批。
    """
    total_turns = _count_turns(messages)

    # 触发条件：>10 轮且轮次 mod 10 == 1（即 11, 21, 31...）
    if total_turns <= 10 or total_turns % 10 != 1:
        return None

    compressed_turns, summary_text = _parse_summary(current_summary_str)

    next_batch_start = compressed_turns
    next_batch_end = compressed_turns + COMPRESS_BATCH_SIZE

    if next_batch_end > total_turns:
        return None

    turns = _parse_turns(messages)
    batch = turns[next_batch_start:next_batch_end]

    batch_summary = await _summarize_turns_batch(batch, next_batch_start, next_batch_end)
    if not batch_summary:
        return None

    block = f"[第{next_batch_start + 1}-{next_batch_end}轮] {batch_summary}"
    if summary_text:
        summary_text += f"\n{block}"
    else:
        summary_text = block

    compressed_turns = next_batch_end
    print(f"[memory] 批次压缩：第{next_batch_start + 1}-{next_batch_end}轮完成，累计压缩 {compressed_turns}/{total_turns} 轮")

    return _build_summary(compressed_turns, summary_text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def create_session(sid: str, title: str = "新会话") -> dict:
    now = _now()
    await _milvus_insert(
        sid=sid,
        title=title,
        created_at=now,
        updated_at=now,
    )
    await _track_recent(sid)
    r = await get_redis()
    if r:
        await r.delete("sessions:meta")
    return {
        "session_id": sid,
        "title": title,
        "created_at": now,
    }


async def list_sessions() -> list:
    meta = await _read_meta()
    if meta is not None:
        return meta
    return await _rebuild_meta()


async def get_session(sid: str) -> dict | None:
    messages = await _read_messages(sid)
    if messages is not None:
        row = await _milvus_query(sid)
        if row:
            return {
                "session_id": row["session_id"],
                "title": row.get("title", "新会话"),
                "messages": messages,
                "summary": row.get("summary", ""),
                "created_at": row.get("created_at", ""),
                "updated_at": row.get("updated_at", ""),
                "is_starred": row.get("is_starred", False),
            }

    row = await _milvus_query(sid)
    if row is None:
        return None

    try:
        messages = json.loads(row.get("messages_json", "[]"))
    except (json.JSONDecodeError, TypeError):
        messages = []

    asyncio.ensure_future(_cache_messages(sid, messages))

    return {
        "session_id": row["session_id"],
        "title": row.get("title", "新会话"),
        "messages": messages,
        "summary": row.get("summary", ""),
        "created_at": row.get("created_at", ""),
        "updated_at": row.get("updated_at", ""),
        "is_starred": row.get("is_starred", False),
    }


async def save_messages(sid: str, messages: list) -> None:
    messages_json = json.dumps(messages, ensure_ascii=False)

    while len(messages_json.encode("utf-8")) > 60000 and len(messages) > 2:
        messages = messages[2:]
        messages_json = json.dumps(messages, ensure_ascii=False)

    row = await _milvus_query(sid)
    created_at = row["created_at"] if row else _now()
    current_summary = row.get("summary", "") if row else ""

    # 批次压缩：每增长 10 轮触发一次，结果存入 Milvus summary 字段
    new_summary = await _batch_compress(messages, current_summary)
    summary_to_write = new_summary if new_summary is not None else current_summary

    await _milvus_insert(
        sid=sid,
        title=row.get("title", "新会话") if row else "新会话",
        messages_json=messages_json,
        summary=summary_to_write,
        summary_vector=row.get("summary_vector") if row else None,
        created_at=created_at,
        updated_at=_now(),
        is_starred=row.get("is_starred", False) if row else False,
        message_count=len(messages),
        replace=True,
    )

    await _cache_messages(sid, messages)
    await _track_recent(sid)
    r = await get_redis()
    if r:
        await r.delete("sessions:meta")


async def delete_session(sid: str) -> None:
    await _milvus_delete(sid)
    await _invalidate(sid)
    r = await get_redis()
    if r:
        await r.zrem("sessions:recent", sid)


async def update_meta(sid: str, updates: dict) -> None:
    row = await _milvus_query(sid)
    if row is None:
        return

    messages_json = row.get("messages_json", "[]")
    try:
        messages = json.loads(messages_json)
    except (json.JSONDecodeError, TypeError):
        messages = []

    await _milvus_insert(
        sid=sid,
        title=updates.get("title", row.get("title", "新会话")),
        messages_json=messages_json,
        summary=row.get("summary", ""),
        summary_vector=row.get("summary_vector"),
        created_at=row.get("created_at", _now()),
        updated_at=_now(),
        is_starred=updates.get("is_starred", row.get("is_starred", False)),
        message_count=len(messages),
        replace=True,
    )

    await _invalidate(sid)
    r = await get_redis()
    if r:
        await r.delete("sessions:meta")


async def generate_title(questions: list[str]) -> str:
    if not questions:
        return "新会话"

    q_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions[:3])])
    prompt = f"""请根据以下用户问题生成一个简短的对话标题（不超过30字），直接输出标题，不要额外文字。

问题：
{q_text}

标题："""

    try:
        client = _get_llm()
        response = await client.chat.completions.create(
            model=os.getenv("CLS_MODEL", "qwen3.6-27b"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=50,
            extra_body={"enable_thinking": False},
        )
        title = response.choices[0].message.content.strip()
        title = title.strip("《》\"\"''「」")
        return title[:30] if title else "新会话"
    except Exception as e:
        print(f"Title generation failed: {e}")
        raw = questions[0][:30]
        return raw + "..." if len(questions[0]) > 30 else raw
