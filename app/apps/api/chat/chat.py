import traceback
from typing import Optional

from fastapi import APIRouter, Query, Form

from apps.utils import response
from apps.utils.rag_helper import vector_search, rag_generator

router = APIRouter(prefix="/chat", tags=["智能问答"])


@router.post("/ask", summary="智能问答(匿名)", description="基于文档的智能问答（无需登录）")
async def ask_question_anonymous(
    question: str = Form(..., description="用户问题"),
    top_k: int = Form(5, ge=1, le=10, description="检索相关文档数量"),
):
    """匿名智能问答"""
    try:
        # 搜索相关文档
        similar_chunks = await vector_search.search_similar_chunks(question, top_k)
        
        # 生成答案
        answer = await rag_generator.generate_answer(question, similar_chunks)
        
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
            ]
        })
        
    except Exception as e:
        traceback.print_exc()
        return response(code=500, message=f"问答失败: {str(e)}")


@router.get("/search", summary="文档搜索(匿名)", description="搜索相关文档内容（无需登录）")
async def search_documents(
    query: str,
    top_k: int = Query(5, ge=1, le=20, description="返回结果数量"),
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