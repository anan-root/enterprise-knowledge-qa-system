import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# 导入原始 pipeline（不修改原文件）
from backend.qa_engine.main import main as process_question, main_stream

# 新增的 memory 模块
from backend.qa_engine.app.session_manager import (
    create_session,
    list_sessions,
    get_session,
    save_messages,
    delete_session,
    update_meta,
    generate_title,
)
from backend.qa_engine.app.memory_history import rewrite_question_with_history
from backend.qa_engine.data_processing.create_conversations_collection import create_collection

app = FastAPI(
    title="企业知识库智能问答系统 API（含记忆模块）",
    description="基于分类-检索-生成的企业知识库智能问答系统，支持多轮对话记忆",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== Request / Response models =====

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    cot: bool = True
    max_concurrent: int = 5
    stream: bool = False
    history: Optional[list] = None


class ChatResponse(BaseModel):
    content: str
    category: Optional[str] = None
    session_id: str
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    timestamp: str


class CreateSessionResponse(BaseModel):
    session_id: str
    title: str
    created_at: str


class SessionMeta(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str
    is_starred: bool
    message_count: int


class SessionDetail(BaseModel):
    session_id: str
    title: str
    messages: list
    created_at: str
    updated_at: str
    is_starred: bool


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    is_starred: Optional[bool] = None


class SaveMessagesRequest(BaseModel):
    messages: list


class GenerateTitleRequest(BaseModel):
    questions: list[str]


# ===== Startup =====

@app.on_event("startup")
async def on_startup():
    try:
        create_collection(drop_old=False)
        print("Milvus collection ensured")
    except Exception as e:
        print(f"WARNING: Could not ensure Milvus collection: {e}")


# ===== Health =====

@app.get("/", response_model=HealthResponse)
async def root():
    return HealthResponse(status="ok", timestamp=datetime.now().isoformat())


# ===== Helpers =====

def _build_history_for_rewrite(messages: list) -> list:
    """从完整消息列表中提取 rewrite 所需的 [{role, content}] 格式。"""
    return [{"role": m["role"], "content": m["content"]} for m in messages
            if m.get("role") in ("user", "assistant") and m.get("content")]


async def _load_history(session_id: str, frontend_history: list | None) -> tuple:
    """获取用于问题改写的历史和缓存摘要。

    返回 (history, saved_summary)。
    优先用前端传来的 history（此时无 saved_summary），
    没有则从后端加载完整历史 + Milvus 中缓存的批次摘要。
    """
    if frontend_history:
        return frontend_history, ""

    detail = await get_session(session_id)
    if detail and detail.get("messages"):
        history = _build_history_for_rewrite(detail["messages"])
        saved_summary = detail.get("summary", "")
        return history, saved_summary
    return [], ""


# ===== Chat (non-streaming, legacy) =====

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())

    history, saved_summary = await _load_history(session_id, request.history)

    rewritten_question = await rewrite_question_with_history(
        request.question, history, saved_summary=saved_summary
    )
    if rewritten_question != request.question:
        print(f"问题改写: \"{request.question}\" → \"{rewritten_question}\"")

    answer = await process_question(
        user_question=rewritten_question,
        prompt_template="",
        print_retrieval_results=False,
        stream_print=True,
        if_evaluate=False,
    )

    # 持久化消息
    try:
        detail = await get_session(session_id)
        if detail is None:
            await create_session(session_id, request.question[:30])
            messages = []
        else:
            messages = detail.get("messages", [])
        messages.append({
            "id": str(int(datetime.now().timestamp() * 1000)),
            "role": "user",
            "content": request.question,
            "timestamp": datetime.now().isoformat(),
        })
        messages.append({
            "id": str(int(datetime.now().timestamp() * 1000) + 1),
            "role": "assistant",
            "content": answer,
            "timestamp": datetime.now().isoformat(),
        })
        await save_messages(session_id, messages)
    except Exception as e:
        print(f"Failed to persist chat: {e}")

    return ChatResponse(
        content=answer,
        category=None,
        session_id=session_id,
        timestamp=datetime.now().isoformat(),
    )


# ===== Chat (streaming) =====

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    original_question = request.question

    history, saved_summary = await _load_history(session_id, request.history)

    async def event_generator():
        rewritten_question = await rewrite_question_with_history(
            original_question, history, saved_summary=saved_summary
        )
        if rewritten_question != original_question:
            print(f"问题改写: \"{original_question}\" → \"{rewritten_question}\"")

        full_answer = ""
        try:
            async for chunk in main_stream(user_question=rewritten_question):
                full_answer += chunk
                yield chunk
        except Exception as e:
            yield f"\n\n系统错误：{str(e)}"
        finally:
            try:
                detail = await get_session(session_id)
                if detail is None:
                    await create_session(session_id, original_question[:30])
                    messages = []
                else:
                    messages = detail.get("messages", [])

                messages.append({
                    "id": str(int(datetime.now().timestamp() * 1000)),
                    "role": "user",
                    "content": original_question,
                    "timestamp": datetime.now().isoformat(),
                })
                messages.append({
                    "id": str(int(datetime.now().timestamp() * 1000) + 1),
                    "role": "assistant",
                    "content": full_answer,
                    "timestamp": datetime.now().isoformat(),
                })
                await save_messages(session_id, messages)
            except Exception as e:
                print(f"Failed to persist stream chat: {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/plain; charset=utf-8",
    )


# ===== Session CRUD =====

@app.post("/api/sessions", response_model=CreateSessionResponse)
async def create_session_endpoint():
    sid = str(uuid.uuid4())
    result = await create_session(sid)
    return result


@app.get("/api/sessions")
async def list_sessions_endpoint():
    sessions = await list_sessions()
    return {"sessions": sessions}


@app.get("/api/sessions/{session_id}")
async def get_session_endpoint(session_id: str):
    detail = await get_session(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return detail


@app.put("/api/sessions/{session_id}")
async def update_session_endpoint(session_id: str, req: UpdateSessionRequest):
    updates = {}
    if req.title is not None:
        updates["title"] = req.title
    if req.is_starred is not None:
        updates["is_starred"] = req.is_starred
    if not updates:
        return {"status": "ok"}
    await update_meta(session_id, updates)
    return {"status": "updated"}


@app.delete("/api/sessions/{session_id}")
async def delete_session_endpoint(session_id: str):
    await delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@app.post("/api/sessions/{session_id}/title")
async def generate_title_endpoint(session_id: str, req: GenerateTitleRequest):
    title = await generate_title(req.questions)
    await update_meta(session_id, {"title": title})
    return {"title": title}


@app.put("/api/sessions/{session_id}/messages")
async def save_messages_endpoint(session_id: str, req: SaveMessagesRequest):
    await save_messages(session_id, req.messages)
    return {"status": "saved"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.qa_engine.main_api_with_memory:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
