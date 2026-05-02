"""Chat session persistence and short-term memory helpers."""

from __future__ import annotations

import re
import xml.sax.saxutils as xml_esc
from typing import Any, Dict, List, Optional

from apps.models.document import ChatMessage, ChatSession
from apps.models.user import User

MAX_HISTORY_MESSAGES = 10
MAX_SESSION_TITLE_LENGTH = 32
DEFAULT_SESSION_TITLE = "新的对话"

_SPACE_RE = re.compile(r"\s+")
_MARKDOWN_RE = re.compile(r"[#>*_`~\[\]()]")
_LEADING_NOISE_RE = re.compile(
    r"^(请问|请帮我|帮我|麻烦|麻烦你|帮忙|能不能|可以|请|查询一下|查一下|看一下|分析一下|统计一下|统计|列出|告诉我)[，,。.\s]*"
)
_TITLE_STOP_CHARS = "。！？!?；;\n"


def make_session_title(question: str) -> str:
    """Build a stable, readable title from the first user question."""
    title = _MARKDOWN_RE.sub("", question or "")
    title = _SPACE_RE.sub(" ", title.strip())
    while True:
        cleaned = _LEADING_NOISE_RE.sub("", title).strip(" ，,。.!！？?；;：:")
        if cleaned == title:
            break
        title = cleaned
    if not title:
        return DEFAULT_SESSION_TITLE

    first_stop = min(
        (idx for idx in (title.find(ch) for ch in _TITLE_STOP_CHARS) if idx > 0),
        default=-1,
    )
    if 0 < first_stop <= MAX_SESSION_TITLE_LENGTH:
        title = title[:first_stop]

    if len(title) > MAX_SESSION_TITLE_LENGTH:
        cut = title[:MAX_SESSION_TITLE_LENGTH]
        last_space = cut.rfind(" ")
        if last_space >= 12:
            cut = cut[:last_space]
        title = cut.rstrip(" ，,。.!！？?；;：:") + "..."

    return title or DEFAULT_SESSION_TITLE


def escape_xml_text(text: str) -> str:
    return xml_esc.escape(text or "", entities={'"': "&quot;", "'": "&apos;"})


def format_chat_history(messages: List[ChatMessage]) -> str:
    lines: List[str] = []
    for idx, message in enumerate(messages, 1):
        role = "user" if message.role == "user" else "assistant"
        content = escape_xml_text(message.content)
        lines.append(f'<message index="{idx}" role="{role}">{content}</message>')
    return "\n".join(lines)


async def get_or_create_session(
    user: User,
    question: str,
    session_id: Optional[int],
) -> ChatSession:
    if session_id:
        session = await ChatSession.get_or_none(id=session_id, user_id=user.id)
        if not session:
            raise ValueError("会话不存在或无权访问")
        return session
    return await ChatSession.create(user=user, session_name=make_session_title(question))


async def load_conversation_history(session: ChatSession) -> str:
    messages = await ChatMessage.filter(session=session).order_by("-timestamp").limit(MAX_HISTORY_MESSAGES)
    return format_chat_history(list(reversed(messages)))


def message_to_dict(message: ChatMessage) -> Dict[str, Any]:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "metadata": message.metadata,
        "timestamp": message.timestamp,
    }


def session_to_dict(session: ChatSession) -> Dict[str, Any]:
    return {
        "id": session.id,
        "session_name": session.session_name,
        "created_time": session.created_time,
        "last_active": session.last_active,
    }


async def save_chat_turn(
    session: ChatSession,
    question: str,
    answer: str,
    meta: Dict[str, Any],
) -> None:
    await ChatMessage.create(session=session, role="user", content=question)
    await ChatMessage.create(
        session=session,
        role="assistant",
        content=answer,
        metadata={
            "sources": meta.get("sources") or [],
            "react_steps": meta.get("react_steps"),
            "pattern": meta.get("pattern"),
            "error": meta.get("error"),
        },
    )
    await session.save()
