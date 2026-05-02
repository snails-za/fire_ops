"""智能问答 API（流式问答 + 搜索/分析/配置）。"""

import traceback
import xml.sax.saxutils as xml_esc
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Form, Depends
from fastapi.responses import StreamingResponse

from apps.utils import response
from apps.utils.llm_optimizers import get_question_optimizer, get_search_optimizer, optimize_question
from apps.utils.vector_db_selector import vector_search
from apps.utils.react_agent import ReactAgent, ReactAgentConfig
from apps.utils.react_sse import iter_sse_from_agent_streaming, sse_data_line
from apps.dependencies.auth import get_current_user
from apps.models.document import ChatMessage, ChatSession
from apps.models.user import User
from apps.utils.mcp_tools.mcp_bridge import mcp_server_app
from config import OPENAI_API_KEY, OPENAI_BASE_URL, SIMILARITY_THRESHOLD

router = APIRouter(prefix="/chat", tags=["智能问答"])
MAX_HISTORY_MESSAGES = 10


def _session_title(question: str) -> str:
    title = (question or "").strip().replace("\n", " ")
    return title[:30] or "新的对话"


def _escape_xml_text(text: str) -> str:
    return xml_esc.escape(text or "", entities={'"': "&quot;", "'": "&apos;"})


def _format_chat_history(messages: List[ChatMessage]) -> str:
    lines: List[str] = []
    for idx, message in enumerate(messages, 1):
        role = "user" if message.role == "user" else "assistant"
        content = _escape_xml_text(message.content)
        lines.append(f'<message index="{idx}" role="{role}">{content}</message>')
    return "\n".join(lines)


async def _get_or_create_session(
        user: User,
        question: str,
        session_id: Optional[int],
) -> ChatSession:
    if session_id:
        session = await ChatSession.get_or_none(id=session_id, user_id=user.id)
        if not session:
            raise ValueError("会话不存在或无权访问")
        return session
    return await ChatSession.create(user=user, session_name=_session_title(question))


async def _load_conversation_history(session: ChatSession) -> str:
    messages = await ChatMessage.filter(session=session).order_by("-timestamp").limit(MAX_HISTORY_MESSAGES)
    return _format_chat_history(list(reversed(messages)))


def _message_to_dict(message: ChatMessage) -> Dict[str, Any]:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "metadata": message.metadata,
        "timestamp": message.timestamp,
    }


def _session_to_dict(session: ChatSession) -> Dict[str, Any]:
    return {
        "id": session.id,
        "session_name": session.session_name,
        "created_time": session.created_time,
        "last_active": session.last_active,
    }


async def _save_chat_turn(
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


@router.post("/ask/stream", summary="流式智能问答", description="XML ReAct + FastMCP 工具（流式）",
             dependencies=[Depends(get_current_user)])
async def ask_question_stream(
        question: str = Form(..., description="用户问题 / 任务"),
        session_id: Optional[int] = Form(None, description="会话ID，不传则新建会话"),
        user: User = Depends(get_current_user),
):
    async def generate_stream():
        try:
            q = question.strip()
            session = await _get_or_create_session(user, q, session_id)
            conversation_history = await _load_conversation_history(session)
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
            yield sse_data_line({"type": "session", "session": _session_to_dict(session)})

            async def save_turn(meta: Dict[str, Any]) -> None:
                await _save_chat_turn(session, q, meta.get("final_answer") or "", meta)

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
    return StreamingResponse(generate_stream(), media_type="text/event-stream", headers=headers)


@router.post("/sessions", summary="创建聊天会话", description="创建一个空的聊天会话",
             dependencies=[Depends(get_current_user)])
async def create_chat_session(
        session_name: str = Form("新的对话", description="会话名称"),
        user: User = Depends(get_current_user),
):
    session = await ChatSession.create(user=user, session_name=(session_name or "新的对话")[:100])
    return response(data=_session_to_dict(session), message="会话创建成功")


@router.get("/sessions", summary="聊天会话列表", description="获取当前用户的聊天会话列表",
            dependencies=[Depends(get_current_user)])
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
            "items": [_session_to_dict(session) for session in sessions],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        message="会话列表获取成功",
    )


@router.get("/sessions/{session_id}/messages", summary="聊天消息列表", description="获取会话消息",
            dependencies=[Depends(get_current_user)])
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
            "session": _session_to_dict(session),
            "items": [_message_to_dict(message) for message in messages],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        message="消息列表获取成功",
    )


@router.get("/search", summary="文档搜索", description="基于LLM优化的文档搜索",
            dependencies=[Depends(get_current_user)])
async def search_documents(
        query: str,
        top_k: int = Query(5, ge=1, le=20, description="返回结果数量"),
):
    """搜索相关文档 - 集成LLM查询优化"""
    try:
        original_query = query.strip()
        search_query = original_query

        # 使用新的优化器模块
        search_optimizer = get_search_optimizer()

        # LLM优化搜索查询
        if search_optimizer and len(original_query) > 2:
            try:
                optimized_query = search_optimizer.invoke({"question": original_query})
                optimized_query = optimized_query.strip()

                if len(optimized_query) >= 2 and len(optimized_query) <= len(original_query) * 2:
                    search_query = optimized_query

            except Exception as e:
                print(f"搜索优化失败: {e}")

        # 执行搜索
        search_results = await vector_search.search_similar_documents(
            query=search_query,
            top_k=top_k,
            use_threshold=False,  # 不使用阈值过滤，返回所有找到的结果
        )

        # 如果优化查询无结果，尝试原查询
        if not search_results and search_query != original_query:
            search_results = await vector_search.search_similar_documents(
                query=original_query,
                top_k=top_k,
                use_threshold=False,  # 不使用阈值过滤，返回所有找到的结果
            )

        results = []
        for result in search_results:
            # 从result中提取document和chunk对象
            document = result.get("document")
            chunk = result.get("chunk")

            results.append({
                "document_id": document.id if document else None,
                "document_name": document.filename if document else "未知文档",
                "chunk_content": chunk.content if chunk else "",
                "similarity": round(result.get("similarity", 0), 4),
                "rerank_score": round(result["rerank_score"], 4) if "rerank_score" in result else None,
                "reranked": bool(result.get("reranked", False)),
                "chunk_index": chunk.chunk_index if chunk else 0
            })

        return response(
            data={
                "query": original_query,
                "search_query": search_query,
                "results": results,
                "total": len(results),
                "llm_enhanced": search_optimizer is not None,
                "similarity_threshold": SIMILARITY_THRESHOLD,
                "filtered_by_threshold": True
            },
            message="搜索成功"
        )

    except Exception as e:
        print(f"搜索失败: {e}")
        traceback.print_exc()
        return response(code=0, message=f"搜索失败: {str(e)}")


@router.get("/config", summary="获取配置信息", description="获取当前系统配置")
async def get_config():
    """获取系统配置信息"""
    return response(
        data={
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "threshold_description": f"相似度阈值 {SIMILARITY_THRESHOLD:.1%}，只显示相似度大于此值的文档"
        },
        message="配置获取成功"
    )


@router.post("/analyze", summary="问题分析", description="使用LLM分析问题意图和关键词",
             dependencies=[Depends(get_current_user)])
async def analyze_question(question: str = Form(..., description="用户问题")):
    """问题分析 - 展示LLM的问题理解能力"""
    try:
        # 使用新的优化器模块
        question_optimizer = get_question_optimizer()

        if not question_optimizer:
            return response(
                data={
                    "question": question,
                    "analysis": "LLM未配置，无法进行深度分析",
                    "llm_available": False
                },
                message="LLM未配置"
            )

        # 使用新的结构化输出
        analysis_result = optimize_question(question)

        return response(
            data={
                "question": question,
                "analysis": analysis_result,
                "llm_available": True
            },
            message="分析成功"
        )

    except Exception as e:
        print(f"问题分析失败: {e}")
        traceback.print_exc()
        return response(code=0, message=f"问题分析失败: {str(e)}")
