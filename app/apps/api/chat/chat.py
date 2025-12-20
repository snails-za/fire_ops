"""
智能问答API模块

提供基于RAG的智能问答服务，包括：
1. 智能问答 - 基于文档内容的AI问答
2. 文档搜索 - 语义相似度搜索
3. 问题分析 - LLM问题理解和优化

集成了LangChain和OpenAI，支持问题优化和搜索增强。
"""

import json
import traceback

from fastapi import APIRouter, Query, Form, Depends
from fastapi.responses import StreamingResponse

from apps.utils import response
from apps.utils.llm_optimizers import get_question_optimizer, get_search_optimizer, optimize_question
from apps.utils.rag_helper import rag_generator
from apps.utils.vector_db_selector import vector_search
from apps.utils.device_helper import format_device_context, get_all_devices_by_permission
from apps.dependencies.auth import get_current_user
from apps.models.user import User
from config import SIMILARITY_THRESHOLD

# 智能问答API路由
router = APIRouter(prefix="/chat", tags=["智能问答"])


@router.post("/ask/stream", summary="流式智能问答", description="基于LLM的流式智能文档和设备问答", dependencies=[Depends(get_current_user)])
async def ask_question_stream(
    question: str = Form(..., description="用户问题"),
    top_k: int = Form(5, ge=1, le=10, description="检索相关文档数量"),
    user: User = Depends(get_current_user)
):
    """
    流式智能问答 - 实时输出回答内容（包含设备信息）
    """
    async def generate_stream():
        try:
            # 1. 问题理解和优化
            question_analysis = None
            optimized_query = question
            
            question_optimizer = get_question_optimizer()
            search_optimizer = get_search_optimizer()
            
            if question_optimizer:
                try:
                    analysis_result = optimize_question(question)
                    if analysis_result:
                        question_analysis = analysis_result
                        optimized_query = analysis_result.get("optimized_query", question)
                    else:
                        # 如果问题分析失败，使用搜索优化器
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
            print("问题优化结果：", optimized_query)
            
            # 发送搜索状态
            yield f"data: {json.dumps({'type': 'status', 'message': '🔍 正在获取数据...'}, ensure_ascii=False)}\n\n"
            
            # 2. 同时获取设备数据和文档数据，不进行任何规则判断
            # 获取设备数据（统计信息 + 设备列表摘要）
            print("获取设备数据...")
            device_data = await get_all_devices_by_permission(
                user_id=user.id, 
                is_admin=(user.role == "admin")
            )
            device_list = device_data.get("devices", []) if device_data else []
            print(f"设备总数: {device_data.get('total', 0) if device_data else 0}, 返回详情数量: {len(device_list)}, 用户: {user.role}")
            
            # 格式化设备上下文
            device_context = format_device_context(device_data) if device_data else ""
            print(f"设备信息格式化后长度: {len(device_context) if device_context else 0}")
            
            # 同时搜索相关文档
            print("搜索相关文档...")
            search_results = await vector_search.search_similar_documents(
                query=optimized_query,
                top_k=top_k,
                use_threshold=True
            )
            print(f"搜索到文档数量: {len(search_results)}")
            
            if not search_results and not device_context:
                yield f"data: {json.dumps({'type': 'content', 'message': '抱歉，我没有找到相关的文档内容或设备信息来回答您的问题。'}, ensure_ascii=False)}\n\n"
                return
            
            # 发送文档信息
            high_quality_results = [r for r in search_results if r.get('above_threshold', True)]
            low_quality_results = [r for r in search_results if not r.get('above_threshold', True)]
            
            # 构建源信息
            sources = []
            for result in search_results:
                document = result.get("document")
                chunk = result.get("chunk")
                chunk_content = chunk.content if chunk else ""
                sources.append({
                    "document_name": document.filename if document else "未知文档",
                    "original_filename": document.original_filename if document else None,
                    "file_type": document.file_type if document else None,
                    "chunk_text": chunk_content,
                    "content_preview": chunk_content[:200] + "..." if len(chunk_content) > 200 else chunk_content,
                    "similarity": round(result.get("similarity", 0), 4),
                    "document_id": document.id if document else None,
                    "chunk_id": chunk.id if chunk else None,
                    "chunk_index": chunk.chunk_index if chunk else 0,
                    "above_threshold": result.get("above_threshold", True)
                })
            
            # 发送搜索结果信息
            search_info = {
                "search_count": len(search_results),
                "high_quality_count": len(high_quality_results),
                "low_quality_count": len(low_quality_results),
                "similarity_threshold": SIMILARITY_THRESHOLD,
                "result_quality": "high" if high_quality_results else ("low" if low_quality_results else "none"),
                "optimized_query": optimized_query,
                "question_analysis": question_analysis,
                "device_count": len(device_list)  # 添加设备数量
            }

            # 添加问题分析的关键词信息
            keywords = []
            if question_analysis and 'keywords' in question_analysis:
                keywords = question_analysis['keywords']
            elif optimized_query and optimized_query != question:
                # 如果没有关键词但有优化查询，使用优化查询作为关键词
                keywords = [optimized_query]
            
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'search_info': search_info, 'keywords': keywords, 'devices': device_list}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'message': '🤖 正在生成回答...'}, ensure_ascii=False)}\n\n"
            
            # 4. 生成真正的流式回答
            current_text = ""
            
            # 使用RAG生成器的流式方法（包含设备信息）
            async for chunk in rag_generator.generate_answer_stream(
                query=question,
                context_chunks=search_results,
                device_context=device_context
            ):
                if chunk:
                    current_text += chunk
                    yield f"data: {json.dumps({'type': 'content', 'content': current_text}, ensure_ascii=False)}\n\n"
            
            # 根据结果质量添加提示
            if low_quality_results:
                additional_tip = "\n\n💡 提示：以上回答基于相似度较低的文档内容，可能不够准确。建议您：\n• 尝试更具体的问题描述\n• 使用不同的关键词重新提问"
                current_text += additional_tip
                yield f"data: {json.dumps({'type': 'content', 'content': current_text}, ensure_ascii=False)}\n\n"
            
            # 发送完成信号
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            print(f"流式问答失败: {e}")
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': f'问答失败: {str(e)}'}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        }
    )


@router.post("/ask", summary="智能问答", description="基于LLM的智能文档和设备问答", dependencies=[Depends(get_current_user)])
async def ask_question_anonymous(
    question: str = Form(..., description="用户问题"),
    top_k: int = Form(5, ge=1, le=10, description="检索相关文档数量"),
    user: User = Depends(get_current_user)
):
    """
    智能问答 - 集成LLM问题理解和搜索优化，支持设备信息查询
    
    Args:
        question: 用户问题
        top_k: 检索相关文档数量
        user: 当前登录用户
        
    Returns:
        智能问答结果，包含答案、相关文档、设备信息和问题分析
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
                # 使用新的结构化输出
                analysis_result = optimize_question(question)
                
                if analysis_result:
                    question_analysis = analysis_result
                    optimized_query = analysis_result.get("optimized_query", question)
                else:
                    # 如果问题分析失败，使用搜索优化器
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
        
        # 2. 同时获取设备数据和文档数据，不进行任何规则判断
        # 获取设备数据（统计信息 + 设备列表摘要）
        print("获取设备数据...")
        device_data = await get_all_devices_by_permission(
            user_id=user.id, 
            is_admin=(user.role == "admin")
        )
        device_list = device_data.get("devices", []) if device_data else []
        print(f"设备总数: {device_data.get('total', 0) if device_data else 0}, 返回详情数量: {len(device_list)}, 用户: {user.role}")
        
        # 格式化设备上下文
        device_context = format_device_context(device_data) if device_data else ""
        print(f"设备信息格式化后长度: {len(device_context) if device_context else 0}")
        
        # 同时搜索相关文档
        print("搜索相关文档...")
        search_results = await vector_search.search_similar_documents(
            query=optimized_query,
            top_k=top_k,
            use_threshold=True
        )
        print(f"搜索到文档数量: {len(search_results)}")
        
        if not search_results and not device_context:
            return response(
                data={
                    "answer": "抱歉，我没有找到相关的文档内容或设备信息来回答您的问题。请尝试：\n1. 重新表述问题\n2. 使用更具体的关键词\n3. 确保相关文档已上传或设备信息已添加",
                    "sources": [],
                    "devices": [],
                    "question_analysis": question_analysis,
                    "optimized_query": optimized_query,
                    "search_count": 0,
                    "device_count": 0,
                    "similarity_threshold": SIMILARITY_THRESHOLD
                },
                message="未找到相关信息"
            )
        
        # 4. 分析搜索结果质量并生成智能回答
        high_quality_results = [r for r in search_results if r.get('above_threshold', True)]
        low_quality_results = [r for r in search_results if not r.get('above_threshold', True)]
        
        # 生成基础回答（包含设备信息）
        answer = await rag_generator.generate_answer(
            query=question,
            context_chunks=search_results,
            device_context=device_context
        )
        
        # 根据结果质量调整回答
        if low_quality_results:
            # 只有低质量结果，添加提示
            answer = f"{answer}\n\n💡 提示：以上回答基于相似度较低的文档内容，可能不够准确。建议您：\n• 尝试更具体的问题描述\n• 使用不同的关键词重新提问"
        
        # 4. 构建源信息
        sources = []
        for result in search_results:
            # 从result中提取document和chunk对象
            document = result.get("document")
            chunk = result.get("chunk")
            
            chunk_content = chunk.content if chunk else ""
            sources.append({
                "document_name": document.filename if document else "未知文档",
                "original_filename": document.original_filename if document else None,
                "file_type": document.file_type if document else None,
                "chunk_text": chunk_content,
                "content_preview": chunk_content[:200] + "..." if len(chunk_content) > 200 else chunk_content,
                "similarity": round(result.get("similarity", 0), 4),
                "document_id": document.id if document else None,
                "chunk_id": chunk.id if chunk else None,
                "chunk_index": chunk.chunk_index if chunk else 0
            })
        
        return response(
            data={
                "answer": answer,
                "sources": sources,
                "devices": device_list,
                "question_analysis": question_analysis,
                "optimized_query": optimized_query,
                "search_count": len(search_results),
                "device_count": len(device_list),
                "high_quality_count": len(high_quality_results),
                "low_quality_count": len(low_quality_results),
                "similarity_threshold": SIMILARITY_THRESHOLD,
                "result_quality": "high" if high_quality_results else ("low" if low_quality_results else "none")
            },
            message="问答成功"
        )
        
    except Exception as e:
        print(f"智能问答失败: {e}")
        traceback.print_exc()
        return response(code=0, message=f"问答失败: {str(e)}")


@router.get("/search", summary="文档搜索", description="基于LLM优化的文档搜索", dependencies=[Depends(get_current_user)])
async def search_documents(
    query: str,
    top_k: int = Query(5, ge=1, le=20, description="返回结果数量"),
    user: User = Depends(get_current_user)
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
            lambda_param=0.7
        )
        
        # 如果优化查询无结果，尝试原查询
        if not search_results and search_query != original_query:
            search_results = await vector_search.search_similar_documents(
                query=original_query, 
                top_k=top_k,
                use_threshold=False,  # 不使用阈值过滤，返回所有找到的结果
                lambda_param=0.7
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


@router.post("/analyze", summary="问题分析", description="使用LLM分析问题意图和关键词", dependencies=[Depends(get_current_user)])
async def analyze_question(
    question: str = Form(..., description="用户问题"),
    user: User = Depends(get_current_user)
):
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