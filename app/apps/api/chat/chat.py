"""智能问答 API（流式问答 + 搜索/分析/配置）。"""

import traceback

from fastapi import APIRouter, Query, Form, Depends
from fastapi.responses import StreamingResponse

from apps.utils import response
from apps.utils.llm_optimizers import get_question_optimizer, get_search_optimizer, optimize_question
from apps.utils.vector_db_selector import vector_search
from apps.utils.react_agent import ReactAgent, ReactAgentConfig
from apps.utils.react_sse import iter_sse_from_agent_streaming, sse_data_line
from apps.dependencies.auth import get_current_user
from apps.models.user import User
from apps.utils.mcp_tools.mcp_bridge import mcp_server_app
from config import OPENAI_API_KEY, OPENAI_BASE_URL, SIMILARITY_THRESHOLD

router = APIRouter(prefix="/chat", tags=["智能问答"])


@router.post("/ask/stream", summary="流式智能问答", description="XML ReAct + FastMCP 工具（流式）",
             dependencies=[Depends(get_current_user)])
async def ask_question_stream(
        question: str = Form(..., description="用户问题 / 任务"),
        user: User = Depends(get_current_user),
):
    async def generate_stream():
        try:
            agent = ReactAgent(
                openai_api_key=OPENAI_API_KEY,
                openai_base_url=OPENAI_BASE_URL or "https://api.openai.com/v1/",
                mcp_server_app=mcp_server_app,
                config=ReactAgentConfig(),
            )
            tool_context = {"user_id": user.id, "role": getattr(user, "role", None)}
            async for line in iter_sse_from_agent_streaming(
                    agent, question.strip(), tool_context=tool_context
            ):
                yield line
        except Exception as e:
            print(f"流式问答失败: {e}")
            traceback.print_exc()
            yield sse_data_line({"type": "error", "message": f"问答失败: {str(e)}"})

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive", "Content-Type": "text/event-stream"}
    return StreamingResponse(generate_stream(), media_type="text/plain", headers=headers)


@router.get("/search", summary="文档搜索", description="基于LLM优化的文档搜索",
            dependencies=[Depends(get_current_user)])
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


@router.post("/analyze", summary="问题分析", description="使用LLM分析问题意图和关键词",
             dependencies=[Depends(get_current_user)])
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