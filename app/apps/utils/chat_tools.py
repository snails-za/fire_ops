"""ReAct 工具：文档检索、设备统计、事件列表。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from tortoise.expressions import Q

from apps.models.event import Event
from apps.models.user import User
from apps.utils.device_helper import format_device_context, get_all_devices_by_permission
from apps.utils.vector_db_selector import vector_search
from config import SIMILARITY_THRESHOLD

MAX_TOOL_CHARS = 12000


def _truncate(text: str, max_len: int = MAX_TOOL_CHARS) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 20] + "\n...(内容已截断)"


@dataclass
class ChatToolContext:
    doc_raw_results: List[Any] = field(default_factory=list)
    device_data: Optional[dict] = None


def _is_privileged(user: User) -> bool:
    return user.role in ("admin", "leader")


async def search_uploaded_documents_impl(
    query: str,
    top_k: int,
    ctx: ChatToolContext,
) -> str:
    k = max(1, min(int(top_k), 10))
    results = await vector_search.search_similar_documents(
        query=query.strip(),
        top_k=k,
        use_threshold=True,
    )
    ctx.doc_raw_results = list(results)
    if not results:
        return "未检索到与问题相关的已上传文档片段（可能尚未上传文档或相似度不足）。"
    lines: List[str] = []
    for i, r in enumerate(results, 1):
        doc = r.get("document")
        chunk = r.get("chunk")
        text = (chunk.content if chunk else "") or ""
        name = doc.filename if doc else "未知文档"
        sim = r.get("similarity", 0)
        flag = "高" if r.get("above_threshold", True) else "低"
        lines.append(
            f"[{i}] 《{name}》 相似度≈{float(sim):.3f}({flag}相关)\n{text.strip()[:2000]}"
        )
    return _truncate("\n\n".join(lines))


async def get_device_statistics_impl(user: User, ctx: ChatToolContext) -> str:
    data = await get_all_devices_by_permission(
        user_id=user.id,
        is_admin=_is_privileged(user),
    )
    ctx.device_data = data
    if not data or data.get("total", 0) == 0:
        return "当前没有可访问的设备数据。"
    return _truncate(format_device_context(data))


async def list_recent_events_impl(user: User, limit: Any) -> str:
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = 10
    n = max(1, min(n, 25))
    if user.role == "maintainer":
        qs = Event.filter(
            Q(device__created_by_user_id=user.id) | Q(device__maintainer_user_id=user.id)
        )
    else:
        qs = Event.all()
    events = await qs.prefetch_related("device").order_by("-created_at").limit(n)
    if not events:
        return "没有查询到事件记录。"
    lines: List[str] = []
    for e in events:
        d = e.device
        dname = d.name if d else "-"
        lines.append(
            f"- ID={e.id} | {e.title} | 状态={e.status} | 等级={e.level} | 设备={dname} | 创建={e.created_at}"
        )
    return _truncate("\n".join(lines))


async def dispatch_react_action(
    action: str,
    action_input: Any,
    user: User,
    ctx: ChatToolContext,
    default_top_k: int,
) -> str:
    """执行 ReAct 的 Action，返回 Observation 文本。"""
    name = (action or "").strip().lower().replace(" ", "_")
    aliases = {
        "search_documents": "search_uploaded_documents",
        "document_search": "search_uploaded_documents",
        "search": "search_uploaded_documents",
        "devices": "get_device_statistics",
        "device_statistics": "get_device_statistics",
        "events": "list_recent_events",
        "recent_events": "list_recent_events",
    }
    name = aliases.get(name, name)

    if name == "search_uploaded_documents":
        if not isinstance(action_input, dict):
            return "Observation 格式错误：Action Input 须为 JSON 对象，含 query 字符串，可选 top_k 整数。"
        q = (action_input.get("query") or action_input.get("q") or "").strip()
        if not q:
            return "缺少 query：请在 Action Input 中提供 {\"query\":\"检索语句\"}。"
        tk = action_input.get("top_k", default_top_k)
        return await search_uploaded_documents_impl(q, int(tk), ctx)

    if name == "get_device_statistics":
        return await get_device_statistics_impl(user, ctx)

    if name == "list_recent_events":
        lim = 10
        if isinstance(action_input, dict):
            lim = action_input.get("limit", lim)
        return await list_recent_events_impl(user, lim)

    return (
        f"未知或不支持的 Action「{action}」。"
        f"仅允许：search_uploaded_documents、get_device_statistics、list_recent_events。"
    )


def build_sources_from_doc_results(results: List[Any]) -> List[dict]:
    sources = []
    for result in results or []:
        document = result.get("document")
        chunk = result.get("chunk")
        chunk_content = chunk.content if chunk else ""
        sources.append(
            {
                "document_name": document.filename if document else "未知文档",
                "original_filename": document.original_filename if document else None,
                "file_type": document.file_type if document else None,
                "chunk_text": chunk_content,
                "content_preview": chunk_content[:200] + "..." if len(chunk_content) > 200 else chunk_content,
                "similarity": round(result.get("similarity", 0), 4),
                "document_id": document.id if document else None,
                "chunk_id": chunk.id if chunk else None,
                "chunk_index": chunk.chunk_index if chunk else 0,
                "above_threshold": result.get("above_threshold", True),
            }
        )
    return sources
