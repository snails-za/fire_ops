from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from tortoise.contrib.pydantic import pydantic_model_creator

from apps.dependencies.auth import get_current_user
from apps.models.user import User
from apps.models.document import ChatSession, ChatMessage
from apps.utils import response
from apps.utils.rag_helper import vector_search, rag_generator

router = APIRouter(prefix="/chat", tags=["智能问答"])

# 创建Pydantic模型
ChatSession_Pydantic = pydantic_model_creator(ChatSession, name="ChatSession")
ChatMessage_Pydantic = pydantic_model_creator(ChatMessage, name="ChatMessage")


@router.post("/sessions", summary="创建聊天会话", description="创建新的聊天会话")
async def create_chat_session(
    session_name: str,
    user: User = Depends(get_current_user)
):
    """创建聊天会话"""
    try:
        session = await ChatSession.create(
            user_id=user.id,
            session_name=session_name
        )
        
        data = await ChatSession_Pydantic.from_tortoise_orm(session)
        return response(data=data.model_dump(), message="会话创建成功")
        
    except Exception as e:
        return response(code=500, message=f"创建会话失败: {str(e)}")


@router.get("/sessions", summary="获取聊天会话列表", description="获取用户的聊天会话列表")
async def get_chat_sessions(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    user: User = Depends(get_current_user)
):
    """获取聊天会话列表"""
    try:
        query = ChatSession.filter(user_id=user.id).order_by("-last_active")
        total = await query.count()
        
        sessions = await query.offset((page - 1) * page_size).limit(page_size)
        
        data = []
        for session in sessions:
            session_data = await ChatSession_Pydantic.from_tortoise_orm(session)
            # 获取会话消息数量
            message_count = await ChatMessage.filter(session_id=session.id).count()
            session_dict = session_data.model_dump()
            session_dict["message_count"] = message_count
            data.append(session_dict)
        
        return response(data={
            "sessions": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })
        
    except Exception as e:
        return response(code=500, message=f"获取会话列表失败: {str(e)}")


@router.get("/sessions/{session_id}", summary="获取会话详情", description="获取聊天会话详情")
async def get_chat_session(
    session_id: int,
    user: User = Depends(get_current_user)
):
    """获取聊天会话详情"""
    try:
        session = await ChatSession.get_or_none(id=session_id, user_id=user.id)
        if not session:
            return response(code=404, message="会话不存在")
        
        session_data = await ChatSession_Pydantic.from_tortoise_orm(session)
        return response(data=session_data.model_dump())
        
    except Exception as e:
        return response(code=500, message=f"获取会话详情失败: {str(e)}")


@router.delete("/sessions/{session_id}", summary="删除聊天会话", description="删除聊天会话及其消息")
async def delete_chat_session(
    session_id: int,
    user: User = Depends(get_current_user)
):
    """删除聊天会话"""
    try:
        session = await ChatSession.get_or_none(id=session_id, user_id=user.id)
        if not session:
            return response(code=404, message="会话不存在")
        
        # 删除会话（级联删除消息）
        await session.delete()
        
        return response(message="会话删除成功")
        
    except Exception as e:
        return response(code=500, message=f"删除会话失败: {str(e)}")


@router.get("/sessions/{session_id}/messages", summary="获取会话消息", description="获取聊天会话的消息列表")
async def get_chat_messages(
    session_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    user: User = Depends(get_current_user)
):
    """获取会话消息"""
    try:
        # 验证会话权限
        session = await ChatSession.get_or_none(id=session_id, user_id=user.id)
        if not session:
            return response(code=404, message="会话不存在")
        
        query = ChatMessage.filter(session_id=session_id).order_by("timestamp")
        total = await query.count()
        
        messages = await query.offset((page - 1) * page_size).limit(page_size)
        
        data = []
        for message in messages:
            message_data = await ChatMessage_Pydantic.from_tortoise_orm(message)
            data.append(message_data.model_dump())
        
        return response(data={
            "messages": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })
        
    except Exception as e:
        return response(code=500, message=f"获取消息列表失败: {str(e)}")


@router.post("/sessions/{session_id}/ask", summary="智能问答", description="向系统提问并获取基于文档的答案")
async def ask_question(
    session_id: int,
    question: str,
    top_k: int = Query(5, ge=1, le=10, description="检索相关文档数量"),
    user: User = Depends(get_current_user)
):
    """智能问答"""
    try:
        # 验证会话权限
        session = await ChatSession.get_or_none(id=session_id, user_id=user.id)
        if not session:
            return response(code=404, message="会话不存在")
        
        # 保存用户问题
        user_message = await ChatMessage.create(
            session_id=session_id,
            role="user",
            content=question
        )
        
        # 搜索相关文档
        similar_chunks = await vector_search.search_similar_chunks(question, top_k)
        
        # 生成答案
        answer = await rag_generator.generate_answer(question, similar_chunks)
        
        # 保存系统回答
        assistant_message = await ChatMessage.create(
            session_id=session_id,
            role="assistant",
            content=answer,
            metadata={
                "similar_chunks": [
                    {
                        "document": chunk["document"].filename,
                        "similarity": chunk["similarity"],
                        "content_preview": chunk["chunk"].content[:200] + "..." if len(chunk["chunk"].content) > 200 else chunk["chunk"].content
                    }
                    for chunk in similar_chunks
                ]
            }
        )
        
        # 更新会话活跃时间
        session.last_active = datetime.now()
        await session.save()
        
        return response(data={
            "question": question,
            "answer": answer,
            "sources": [
                {
                    "document": chunk["document"].filename,
                    "similarity": chunk["similarity"],
                    "content_preview": chunk["chunk"].content[:200] + "..." if len(chunk["chunk"].content) > 200 else chunk["chunk"].content
                }
                for chunk in similar_chunks
            ],
            "message_id": assistant_message.id
        })
        
    except Exception as e:
        return response(code=500, message=f"问答失败: {str(e)}")


@router.get("/search", summary="文档搜索", description="搜索相关文档内容")
async def search_documents(
    query: str,
    top_k: int = Query(5, ge=1, le=20, description="返回结果数量"),
    user: User = Depends(get_current_user)
):
    """搜索相关文档"""
    try:
        # 搜索相似文档块
        similar_chunks = await vector_search.search_similar_chunks(query, top_k)
        
        results = []
        for chunk in similar_chunks:
            results.append({
                "document_id": chunk["document"].id,
                "document_name": chunk["document"].filename,
                "chunk_content": chunk["chunk"].content,
                "similarity": chunk["similarity"],
                "chunk_index": chunk["chunk"].chunk_index
            })
        
        return response(data={
            "query": query,
            "results": results,
            "total": len(results)
        })
        
    except Exception as e:
        return response(code=500, message=f"搜索失败: {str(e)}")


@router.get("/stats", summary="聊天统计", description="获取聊天相关统计信息")
async def get_chat_stats(user: User = Depends(get_current_user)):
    """获取聊天统计信息"""
    try:
        # 用户会话统计
        total_sessions = await ChatSession.filter(user_id=user.id).count()
        total_messages = await ChatMessage.filter(session__user_id=user.id).count()
        
        # 最近活跃的会话
        recent_sessions = await ChatSession.filter(user_id=user.id).order_by("-last_active").limit(5)
        recent_sessions_data = []
        for session in recent_sessions:
            session_data = await ChatSession_Pydantic.from_tortoise_orm(session)
            recent_sessions_data.append(session_data.model_dump())
        
        return response(data={
            "sessions": {
                "total": total_sessions,
                "recent": recent_sessions_data
            },
            "messages": {
                "total": total_messages
            }
        })
        
    except Exception as e:
        return response(code=500, message=f"获取统计信息失败: {str(e)}")
