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
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from apps.utils import response
from apps.utils.rag_helper import vector_search, rag_generator
from config import OPENAI_API_KEY, OPENAI_BASE_URL

# 智能问答API路由

router = APIRouter(prefix="/chat", tags=["智能问答"])

# 初始化LLM用于问题理解和优化
question_optimizer = None
search_optimizer = None

def initialize_question_optimizers():
    """
    初始化问题理解和搜索优化LLM
    
    Returns:
        tuple: (question_optimizer, search_optimizer)
    """
    global question_optimizer, search_optimizer
    
    if not OPENAI_API_KEY or not OPENAI_API_KEY.strip():
        return None, None
    
    try:
        # 创建OpenAI客户端
        question_llm = ChatOpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            temperature=0.1,
            model="gpt-3.5-turbo",
            max_tokens=500  # 限制输出长度
        )
        
        # 问题理解和优化提示模板
        question_template = """你是一个问题理解助手。请分析用户的问题，提取关键信息并优化搜索策略。

任务：
1. 理解问题的核心意图和关键概念
2. 识别问题类型（事实查询、操作指导、概念解释等）
3. 提取最重要的搜索关键词
4. 如果问题模糊，推测可能的具体含义

用户问题：{question}

请用以下JSON格式回答：
{{
    "intent": "问题意图描述",
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "question_type": "问题类型",
    "optimized_query": "优化后的搜索查询"
}}"""
        
        # 搜索查询优化模板
        search_template = """你是一个搜索查询优化专家。请将用户问题转换为最适合文档搜索的查询语句。

要求：
1. 提取核心关键词和概念
2. 去除无关的语气词和修饰词
3. 保持查询的准确性和完整性
4. 适合向量相似度搜索
5. 保持中文输出

原问题：{question}

优化后的搜索查询（只输出查询语句）："""
        
        # 创建处理链
        question_prompt = ChatPromptTemplate.from_template(question_template)
        search_prompt = ChatPromptTemplate.from_template(search_template)
        output_parser = StrOutputParser()
        
        question_optimizer = question_prompt | question_llm | output_parser
        search_optimizer = search_prompt | question_llm | output_parser
        
        return question_optimizer, search_optimizer
        
    except Exception:
        return None, None

# 初始化优化器
question_optimizer, search_optimizer = initialize_question_optimizers()


@router.post("/ask", summary="智能问答(匿名)", description="基于LLM的智能文档问答（无需登录）")
async def ask_question_anonymous(
    question: str = Form(..., description="用户问题"),
    top_k: int = Form(5, ge=1, le=10, description="检索相关文档数量"),
):
    """
    匿名智能问答 - 集成LLM问题理解和搜索优化
    
    处理流程：
    1. 问题预处理和验证
    2. LLM搜索查询优化（可选）
    3. 向量相似度搜索
    4. LLM智能回答生成
    5. 构建结构化响应
    
    Args:
        question: 用户问题
        top_k: 检索相关文档数量
        
    Returns:
        包含答案、来源和搜索信息的响应
    """
    try:
        # 1. 问题预处理
        original_question = question.strip()
        if not original_question:
            return response(code=400, message="问题不能为空")
        
        if len(original_question) > 500:
            return response(code=400, message="问题长度不能超过500字符")
        
        search_query = original_question
        
        # 2. LLM搜索查询优化（如果可用）
        if search_optimizer and len(original_question) > 2:
            try:
                # 优化搜索查询
                optimized_query = await search_optimizer.ainvoke({
                    "question": original_question
                })
                optimized_query = optimized_query.strip()
                
                # 验证优化结果的合理性
                if (len(optimized_query) >= 2 and 
                    len(optimized_query) <= len(original_question) * 2 and
                    optimized_query != original_question):
                    search_query = optimized_query
                    
            except Exception:
                search_query = original_question
        
        # 3. 向量相似度搜索
        similar_chunks = await vector_search.search_similar_chunks(search_query, top_k)
        
        # 如果优化查询没有结果，尝试原问题
        if not similar_chunks and search_query != original_question:
            similar_chunks = await vector_search.search_similar_chunks(original_question, top_k)
        
        # 4. LLM智能回答生成
        answer = await rag_generator.generate_answer(original_question, similar_chunks)
        
        # 5. 构建结构化响应
        response_data = {
            "question": original_question,
            "answer": answer,
            "sources": [
                {
                    "document_id": chunk["document"].id,
                    "document_name": chunk["document"].filename,
                    "original_filename": chunk["document"].original_filename,
                    "file_type": chunk["document"].file_type,
                    "chunk_id": chunk["chunk"].id,
                    "chunk_index": chunk["chunk"].chunk_index,
                    "similarity": chunk["similarity"],
                    "content_preview": (
                        chunk["chunk"].content[:200] + "..." 
                        if len(chunk["chunk"].content) > 200 
                        else chunk["chunk"].content
                    ),
                    "full_content": chunk["chunk"].content,
                    "download_url": f"/api/v1/documents/{chunk['document'].id}/download",
                    "view_url": f"/api/v1/documents/{chunk['document'].id}/view?chunk_id={chunk['chunk'].id}",
                    "highlight_url": f"/api/v1/documents/{chunk['document'].id}/view?chunk_id={chunk['chunk'].id}&highlight="
                }
                for chunk in similar_chunks
            ],
            "search_info": {
                "original_query": original_question,
                "search_query": search_query,
                "results_count": len(similar_chunks),
                "llm_enhanced": search_optimizer is not None,
                "query_optimized": search_query != original_question
            }
        }
        
        return response(data=response_data)
        
    except Exception as e:
        traceback.print_exc()
        return response(code=500, message=f"问答失败: {str(e)}")


@router.get("/search", summary="文档搜索(匿名)", description="基于LLM优化的文档搜索（无需登录）")
async def search_documents(
    query: str,
    top_k: int = Query(5, ge=1, le=20, description="返回结果数量"),
):
    """搜索相关文档 - 集成LLM查询优化"""
    try:
        original_query = query.strip()
        search_query = original_query
        
        # LLM优化搜索查询
        if search_optimizer and len(original_query) > 2:
            try:
                optimized_query = await search_optimizer.ainvoke({
                    "question": original_query
                })
                optimized_query = optimized_query.strip()
                
                if len(optimized_query) >= 2 and len(optimized_query) <= len(original_query) * 2:
                    search_query = optimized_query
                    
            except Exception as e:
                print(f"搜索优化失败: {e}")
        
        # 执行搜索
        similar_chunks = await vector_search.search_similar_chunks(search_query, top_k)
        
        # 如果优化查询无结果，尝试原查询
        if not similar_chunks and search_query != original_query:
            similar_chunks = await vector_search.search_similar_chunks(original_query, top_k)
        
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
            "query": original_query,
            "search_query": search_query,
            "results": results,
            "total": len(results),
            "llm_enhanced": search_optimizer is not None
        })
        
    except Exception as e:
        traceback.print_exc()
        return response(code=500, message=f"搜索失败: {str(e)}")


@router.post("/analyze", summary="问题分析(匿名)", description="使用LLM分析问题意图和关键词（无需登录）")
async def analyze_question(
    question: str = Form(..., description="用户问题"),
):
    """问题分析 - 展示LLM的问题理解能力"""
    try:
        if not question_optimizer:
            return response(data={
                "question": question,
                "analysis": "LLM未配置，无法进行深度分析",
                "llm_available": False
            })
        
        # 使用LLM分析问题
        analysis_result = await question_optimizer.ainvoke({
            "question": question
        })
        
        return response(data={
            "question": question,
            "analysis": analysis_result,
            "llm_available": True
        })
        
    except Exception as e:
        traceback.print_exc()
        return response(code=500, message=f"问题分析失败: {str(e)}")