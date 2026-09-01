"""智能问答 API（流式问答与会话管理）。"""

import traceback
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Form, Depends
from fastapi.responses import StreamingResponse

from apps.utils import response
from apps.utils.react_agent import ReactAgent, ReactAgentConfig
from apps.utils.react_sse import iter_sse_from_agent_streaming, sse_data_line
from apps.dependencies.auth import get_current_user
from apps.models.document import ChatMessage, ChatSession
from apps.models.user import User
from apps.utils.chat_session import (
    get_or_create_session,
    load_conversation_history,
    message_to_dict,
    save_chat_turn,
    session_to_dict,
)
from apps.utils.mcp_tools.mcp_bridge import mcp_server_app
from config import OPENAI_API_KEY, OPENAI_BASE_URL

router = APIRouter(prefix="/chat", tags=["智能问答"])


@router.post(
    "/ask/stream",
    summary="流式智能问答",
    description="XML ReAct + FastMCP 工具（流式）",
    dependencies=[Depends(get_current_user)],
)
async def ask_question_stream(
    question: str = Form(..., description="用户问题 / 任务"),
    session_id: Optional[int] = Form(None, description="会话ID，不传则新建会话"),
    user: User = Depends(get_current_user),
):
    async def generate_stream():
        try:
            q = question.strip()
            session = await get_or_create_session(user, q, session_id)
            conversation_history = await load_conversation_history(session)
            agent = ReactAgent(
                openai_api_key=OPENAI_API_KEY,
                openai_base_url=OPENAI_BASE_URL or "https://api.openai.com/v1/",
                mcp_server_app=mcp_server_app,
                config=ReactAgentConfig(),
            )
            tool_context = {
                "user_id": user.id,
                "role": getattr(user, "role", None),
                "session_id": session.id,
            }
            yield sse_data_line(
                {"type": "session", "session": session_to_dict(session)}
            )

            async def save_turn(meta: Dict[str, Any]) -> None:
                try:
                    await save_chat_turn(
                        session, q, meta.get("final_answer") or "", meta
                    )
                except Exception as save_error:
                    print(f"保存聊天记录失败: {save_error}")
                    traceback.print_exc()

            async for line in iter_sse_from_agent_streaming(
                agent,
                q,
                tool_context=tool_context,
                conversation_history=conversation_history,
                on_done=save_turn,
            ):
                yield line
        except Exception as e:
            print(f"流式问答失败: {e}")
            traceback.print_exc()
            yield sse_data_line({"type": "error", "message": f"问答失败: {str(e)}"})

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive"}
    return StreamingResponse(
        generate_stream(), media_type="text/event-stream", headers=headers
    )


@router.get(
    "/sessions",
    summary="聊天会话列表",
    description="获取当前用户的聊天会话列表",
    dependencies=[Depends(get_current_user)],
)
async def list_chat_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
):
    query = ChatSession.filter(user_id=user.id).order_by("-last_active")
    total = await query.count()
    sessions = await query.offset((page - 1) * page_size).limit(page_size)
    return response(
        data={
            "items": [session_to_dict(session) for session in sessions],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        message="会话列表获取成功",
    )


@router.get(
    "/sessions/{session_id}/messages",
    summary="聊天消息列表",
    description="获取会话消息",
    dependencies=[Depends(get_current_user)],
)
async def list_chat_messages(
    session_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
):
    session = await ChatSession.get_or_none(id=session_id, user_id=user.id)
    if not session:
        return response(code=0, message="会话不存在或无权访问")
    query = ChatMessage.filter(session_id=session.id).order_by("timestamp")
    total = await query.count()
    messages = await query.offset((page - 1) * page_size).limit(page_size)
    return response(
        data={
            "session": session_to_dict(session),
            "items": [message_to_dict(message) for message in messages],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        message="消息列表获取成功",
    )


@router.delete(
    "/sessions/{session_id}",
    summary="删除聊天会话",
    description="删除当前用户的聊天会话及其全部消息",
    dependencies=[Depends(get_current_user)],
)
async def delete_chat_session(
    session_id: int,
    user: User = Depends(get_current_user),
):
    session = await ChatSession.get_or_none(id=session_id, user_id=user.id)
    if not session:
        return response(code=0, message="会话不存在或无权访问")
    await session.delete()
    return response(message="会话删除成功")
