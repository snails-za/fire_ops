# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from apps.utils.vector_db_selector import vector_search
from apps.utils.mcp_tools.mcp_bridge import ChatTaskExtra, chat_task_extra

_MAX_TOP_K = 8
_MAX_SNIPPET = 1200


class VectorSearchToolsModule:
    """知识库向量检索 MCP 工具模块。"""

    TOOL_PROMPT_APPEND = """
【文档语义检索（高优先级）】
当问题涉及制度说明、操作步骤、原因解释、总结建议等非结构化知识时，优先调用：
- search_uploaded_documents

调用规范：
1. 使用工具参数：{"query":"检索语句","top_k":5}
2. top_k 建议 3~6；上限 8。
3. 若首轮无结果，可换关键词再检索一次；不要编造不存在的文档内容。
4. 最终回答应基于工具返回的文档片段给出结论。
"""

    def __init__(self, extra: Optional[ChatTaskExtra] = None) -> None:
        self._extra = extra or chat_task_extra

    @staticmethod
    def _normalize_top_k(v: Any) -> int:
        try:
            n = int(v)
        except (TypeError, ValueError):
            n = 5
        return max(1, min(n, _MAX_TOP_K))

    @staticmethod
    def _build_sources(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for item in results or []:
            document = item.get("document")
            chunk = item.get("chunk")
            if not document or not chunk:
                continue
            chunk_text = (chunk.content or "").strip()
            out.append(
                {
                    "document_name": document.filename,
                    "original_filename": document.original_filename,
                    "file_type": document.file_type,
                    "chunk_text": chunk_text,
                    "content_preview": (chunk_text[:200] + "...")
                    if len(chunk_text) > 200
                    else chunk_text,
                    "similarity": round(float(item.get("similarity", 0.0)), 4),
                    "document_id": document.id,
                    "chunk_id": chunk.id,
                    "chunk_index": chunk.chunk_index,
                    "above_threshold": bool(item.get("above_threshold", True)),
                    "from_vector_search": True,
                }
            )
        return out

    async def _search_impl(self, query: str, top_k: int) -> str:
        q = (query or "").strip()
        if not q:
            return "缺少 query：请提供工具参数 {\"query\":\"检索语句\"}。"

        results = await vector_search.search_similar_documents(
            query=q,
            top_k=top_k,
            use_threshold=True,
        )
        bucket = self._extra.current()
        if not results:
            bucket[ChatTaskExtra.SOURCES_EXTRA_KEY] = []
            return "未检索到相关文档片段（可能未上传相关文档或相似度不足）。"

        sources = self._build_sources(results)
        bucket[ChatTaskExtra.SOURCES_EXTRA_KEY] = sources

        lines: List[str] = []
        for i, s in enumerate(sources, 1):
            sim = s.get("similarity", 0.0)
            flag = "高相关" if s.get("above_threshold", True) else "低相关"
            snippet = (s.get("chunk_text") or "")[:_MAX_SNIPPET]
            lines.append(
                f"[{i}] 《{s.get('document_name') or '未知文档'}》"
                f" doc_id={s.get('document_id')} chunk_id={s.get('chunk_id')} "
                f"相似度≈{float(sim):.3f}（{flag}）\n{snippet}"
            )
        joined = "\n\n".join(lines)
        if len(joined) > 12000:
            joined = joined[:11980] + "\n...(检索结果已截断)"
        return joined

    def register(self, app: FastMCP) -> None:
        @app.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
        async def search_uploaded_documents(query: str, top_k: int = 5) -> str:
            """在已上传知识库文档中做语义检索，获取与问题相关的片段。"""
            return await self._search_impl(query, self._normalize_top_k(top_k))
