# -*- coding: utf-8 -*-
"""
ReAct 向量检索插件：用于把非结构化文档证据纳入 ReAct 推理链路。

工具会把本轮检索命中的来源写入 sql_ctx.extra，共享给 Agent 的 meta["sources"]。
"""
from __future__ import annotations

from typing import Any, Dict, List

from apps.utils.react_agent import PLUGIN_STATE_META_SOURCES_EXTRA_KEY
from apps.utils.vector_db_selector import vector_search

_SOURCES_EXTRA_BUCKET = "_react_sources"
_MAX_TOP_K = 8
_MAX_SNIPPET = 1200

REACT_PLUGIN_STATE = {
    PLUGIN_STATE_META_SOURCES_EXTRA_KEY: _SOURCES_EXTRA_BUCKET,
}

REACT_SYSTEM_PROMPT_APPEND = """
【文档语义检索（高优先级）】
当问题涉及制度说明、操作步骤、原因解释、总结建议等非结构化知识时，优先调用：
- search_uploaded_documents

调用规范：
1. action_input 使用 JSON：{"query":"检索语句","top_k":5}
2. top_k 建议 3~6；上限 8。
3. 若首轮无结果，可换关键词再检索一次；不要编造不存在的文档内容。
4. 最终回答应基于 Observation 的文档片段给出结论。
"""


def _normalize_top_k(v: Any) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = 5
    return max(1, min(n, _MAX_TOP_K))


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
                "content_preview": (chunk_text[:200] + "...") if len(chunk_text) > 200 else chunk_text,
                "similarity": round(float(item.get("similarity", 0.0)), 4),
                "document_id": document.id,
                "chunk_id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "above_threshold": bool(item.get("above_threshold", True)),
                "from_vector_search": True,
            }
        )
    return out


async def search_uploaded_documents(**kw: Any) -> str:
    ctx = kw.get("_tool_context")
    if ctx is None:
        return "错误：缺少工具上下文。"

    query = (kw.get("query") or kw.get("q") or "").strip()
    if not query:
        return "缺少 query：请在 action_input 中提供 {\"query\":\"检索语句\"}。"

    top_k = _normalize_top_k(kw.get("top_k", 5))
    results = await vector_search.search_similar_documents(
        query=query,
        top_k=top_k,
        use_threshold=True,
    )
    if not results:
        ctx.extra[_SOURCES_EXTRA_BUCKET] = []
        return "未检索到相关文档片段（可能未上传相关文档或相似度不足）。"

    sources = _build_sources(results)
    ctx.extra[_SOURCES_EXTRA_BUCKET] = sources

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


REACT_TOOLS = {
    "search_uploaded_documents": search_uploaded_documents,
}
