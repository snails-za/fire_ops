"""
智能问答API模块

提供基于RAG的智能问答服务，包括：
1. 智能问答 - 基于文档内容的AI问答
2. 文档搜索 - 语义相似度搜索
3. 问题分析 - LLM问题理解和优化

集成了LangChain和OpenAI，支持问题优化和搜索增强。
"""

import traceback
from typing import Optional

from fastapi import APIRouter, Query, Form

from apps.utils import response
from apps.utils.rag_helper import vector_search, rag_generator
from apps.utils.llm_optimizers import get_question_optimizer, get_search_optimizer, optimize_question

# 智能问答API路由
router = APIRouter(prefix="/chat", tags=["智能问答"])


@router.post("/ask", summary="智能问答(匿名)", description="基于LLM的智能文档问答（无需登录）")
async def ask_question_anonymous(
    question: str = Form(..., description="用户问题"),
    top_k: int = Form(5, ge=1, le=10, description="检索相关文档数量"),
):
    """
    匿名智能问答 - 集成LLM问题理解和搜索优化
    
    Args:
        question: 用户问题
        top_k: 检索相关文档数量
        
    Returns:
        智能问答结果，包含答案、相关文档和问题分析
    """
    try:
        # 1. 问题理解和优化
        question_analysis = None
        optimized_query = question
        
        # 使用新的优化器模块
        question_optimizer = get_question_optimizer()
        search_optimizer = get_search_optimizer()
        
        if question_optimizer:
            try:
                question_analysis = optimize_question(question)
                
                # 尝试解析JSON格式的分析结果
                import json
                try:
                    analysis_data = json.loads(question_analysis)
                    optimized_query = analysis_data.get("optimized_query", question)
                except:
                    # 如果不是JSON格式，使用搜索优化器
                    if search_optimizer:
                        try:
                            optimized_query = search_optimizer.invoke({"question": question})
                            optimized_query = optimized_query.strip()
                            if not optimized_query:
                                optimized_query = question
                        except Exception as e:
                            print(f"搜索优化失败: {e}")
                            optimized_query = question
                    
            except Exception as e:
                print(f"问题优化失败: {e}")
                optimized_query = question
        
        # 2. 向量搜索相关文档
        search_results = vector_search.search_similar_chunks(
            query=optimized_query,
            top_k=top_k
        )
        
        if not search_results:
            return response.success(
                data={
                    "answer": "抱歉，我没有找到相关的文档内容来回答您的问题。请尝试：\n1. 重新表述问题\n2. 使用更具体的关键词\n3. 确保相关文档已上传",
                    "sources": [],
                    "question_analysis": question_analysis,
                    "optimized_query": optimized_query,
                    "search_count": 0
                },
                message="未找到相关文档"
            )
        
        # 3. 生成智能回答
        answer = rag_generator.generate_answer(
            question=question,
            search_results=search_results
        )
        
        # 4. 构建源信息
        sources = []
        for result in search_results:
            sources.append({
                "document_name": result.get("document_name", "未知文档"),
                "chunk_text": result.get("chunk_text", ""),
                "similarity": round(result.get("similarity", 0), 4),
                "document_id": result.get("document_id")
            })
        
        return response.success(
            data={
                "answer": answer,
                "sources": sources,
                "question_analysis": question_analysis,
                "optimized_query": optimized_query,
                "search_count": len(search_results)
            },
            message="问答成功"
        )
        
    except Exception as e:
        print(f"智能问答失败: {e}")
        traceback.print_exc()
        return response.error(message=f"问答失败: {str(e)}")


@router.get("/search", summary="文档搜索(匿名)", description="基于LLM优化的文档搜索（无需登录）")
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
        search_results = vector_search.search_similar_chunks(search_query, top_k)
        
        # 如果优化查询无结果，尝试原查询
        if not search_results and search_query != original_query:
            search_results = vector_search.search_similar_chunks(original_query, top_k)
        
        results = []
        for result in search_results:
            results.append({
                "document_id": result.get("document_id"),
                "document_name": result.get("document_name", "未知文档"),
                "chunk_content": result.get("chunk_text", ""),
                "similarity": round(result.get("similarity", 0), 4),
                "chunk_index": result.get("chunk_index", 0)
            })
        
        return response.success(
            data={
                "query": original_query,
                "search_query": search_query,
                "results": results,
                "total": len(results),
                "llm_enhanced": search_optimizer is not None
            },
            message="搜索成功"
        )
        
    except Exception as e:
        print(f"搜索失败: {e}")
        traceback.print_exc()
        return response.error(message=f"搜索失败: {str(e)}")


@router.post("/analyze", summary="问题分析(匿名)", description="使用LLM分析问题意图和关键词（无需登录）")
async def analyze_question(
    question: str = Form(..., description="用户问题"),
):
    """问题分析 - 展示LLM的问题理解能力"""
    try:
        # 使用新的优化器模块
        question_optimizer = get_question_optimizer()
        
        if not question_optimizer:
            return response.success(
                data={
                    "question": question,
                    "analysis": "LLM未配置，无法进行深度分析",
                    "llm_available": False
                },
                message="LLM未配置"
            )
        
        # 使用LLM分析问题
        analysis_result = optimize_question(question)
        
        return response.success(
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
        return response.error(message=f"问题分析失败: {str(e)}")