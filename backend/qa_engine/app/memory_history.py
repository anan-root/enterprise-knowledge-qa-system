import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

_llm_client = None


def _get_llm():
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            api_key=os.getenv("API_KEY"),
            base_url=os.getenv("BASE_URL"),
        )
    return _llm_client


def _parse_turns(history: list) -> list:
    """将原始消息列表按 Q&A 轮次分组。"""
    turns = []
    i = 0
    while i < len(history):
        item = history[i]
        if isinstance(item, dict) and item.get("role") == "user":
            user_content = item.get("content", "")
            assistant_content = ""
            if i + 1 < len(history):
                next_item = history[i + 1]
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


def _parse_saved_summary(summary_str: str) -> tuple:
    """解析 Milvus 中存储的摘要 JSON，返回 (compressed_turns, text)。兼容纯文本。"""
    if not summary_str:
        return 0, ""
    try:
        data = json.loads(summary_str)
        return data.get("compressed_turns", 0), data.get("text", "")
    except (json.JSONDecodeError, TypeError):
        return 0, summary_str


async def _summarize_turns(turns: list) -> str:
    """将较早的对话轮次压缩为关键信息摘要。"""
    if not turns:
        return ""

    lines = []
    for i, t in enumerate(turns, 1):
        lines.append(f"第{i}轮 - 用户：{t['user']}")
        if t["assistant"]:
            text = t["assistant"]
            truncated = text[:400] + ("..." if len(text) > 400 else "")
            lines.append(f"第{i}轮 - 助手：{truncated}")

    conversation_text = "\n".join(lines)

    prompt = f"""请从以下对话历史中提取关键信息，生成一份简洁的摘要。只保留对后续问题改写可能有用的信息。

【提取内容】
- 提到的实体名称（公司全称、人名、项目名、产品名等）
- 用户关注的主题和方向
- 助手提供过的重要结论或数据
- 对话中建立的上下文关系

【对话历史】
{conversation_text}

请直接输出摘要（不超过400字），不要多余文字："""

    try:
        client = _get_llm()
        response = await client.chat.completions.create(
            model=os.getenv("CLS_MODEL", "qwen3.6-27b"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=500,
            extra_body={"enable_thinking": False},
        )
        summary = response.choices[0].message.content.strip()
        if summary:
            print(f"[memory] 在线摘要生成成功，覆盖 {len(turns)} 轮对话，{len(summary)} 字符")
            return summary
        return ""
    except Exception as e:
        print(f"[memory] 在线摘要生成失败: {e}")
        return ""


async def format_history_for_rewrite(
    history: list | None,
    max_turns: int = 10,
    saved_summary: str = "",
) -> str:
    """将消息列表格式化为对话历史文本，用于问题改写。

    始终保留最近 max_turns 轮完整文本，已压缩的摘要直接复用，
    不做在线压缩（摘要由 save_messages 时的批次压缩生成并缓存到 Milvus）。
    """
    if not history:
        return ""

    turns = _parse_turns(history)
    if not turns:
        return ""

    _, saved_text = _parse_saved_summary(saved_summary)

    # 始终取最近 max_turns 轮作为完整文本
    recent = turns[-max_turns:] if len(turns) >= max_turns else turns

    parts = []
    if saved_text:
        parts.append(f"【历史对话摘要（共{len(turns)}轮）】\n{saved_text}")

    recent_lines = []
    for t in recent:
        recent_lines.append(f"用户：{t['user']}")
        if t["assistant"]:
            recent_lines.append(f"助手：{t['assistant']}")
    parts.append("\n".join(recent_lines))

    return "\n\n".join(parts)


async def rewrite_question_with_history(
    user_question: str,
    history: list | None,
    saved_summary: str = "",
) -> str:
    """使用 LLM 根据对话历史改写用户问题，消解指代和省略。

    saved_summary: Milvus 中缓存的批次压缩摘要，避免重复压缩旧轮次。
    """
    history_text = await format_history_for_rewrite(
        history, saved_summary=saved_summary
    )
    if not history_text:
        return user_question

    prompt = f"""你是一个问题改写助手。根据对话历史，将用户的当前问题改写为一个独立、明确的问题。

【改写规则】
1. 将代词（它、他、这个、那个、该公司、该项目、该产品等）替换为对话历史中明确的具体实体名称
2. 补全省略的主语、宾语或限定条件（如地区、时间范围等）
3. 如果当前问题与对话历史完全无关（用户切换了话题），保持原问题不变
4. 改写后的问题要保持原意，不能添加用户没有询问的内容
5. 改写后的问题尽量简洁明确，但需要保留查询手段，方便在用户明确要求用那种方式查询时进行分类
6. 如果对话历史中助手提到了某个实体的完整名称（如公司全称），在改写时必须使用该完整名称


【对话历史】
{history_text}

【当前问题】
{user_question}

仅输出改写后的问题本身，不要多余文字："""

    print(f"[memory] 收到历史 {len(history) if history else 0} 条消息，格式化后 {len(history_text)} 字符")
    print(f"[memory] 原始问题: {user_question}")

    try:
        client = _get_llm()
        response = await client.chat.completions.create(
            model=os.getenv("CLS_MODEL", "qwen3.6-27b"),
            messages=[
                {"role": "system", "content": "你是问题改写助手，只输出改写后的问题，不做任何解释。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=200,
            extra_body={"enable_thinking": False},
        )
        rewritten = response.choices[0].message.content.strip()
        print(f"[memory] 改写结果: {rewritten}")
        if rewritten:
            return rewritten
        return user_question
    except Exception as e:
        print(f"Question rewrite failed, using original: {e}")
        return user_question
