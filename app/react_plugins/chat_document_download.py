# -*- coding: utf-8 -*-
"""
聊天下载：模型在确认文档 id 后调用 register_chat_document_sources，
将条目写入 Agent 的 sql_ctx.extra，结束时进入 meta["sources"]，前端显示下载按钮。

依赖业务表 document（id, original_filename, file_type）。不需要可删除本文件或移出 REACT_PLUGINS_DIR。
"""
from __future__ import annotations

from typing import Any, Dict, List

from apps.utils.react_agent import PLUGIN_STATE_META_SOURCES_EXTRA_KEY

# 工具写入 sql_ctx.extra 的桶；REACT_PLUGIN_STATE 告知 Agent 从哪个 extra 键同步到 meta["sources"]
_SOURCES_EXTRA_BUCKET = "_react_chat_document_sources"

REACT_PLUGIN_STATE = {
    PLUGIN_STATE_META_SOURCES_EXTRA_KEY: _SOURCES_EXTRA_BUCKET,
}

MAX_DOCUMENT_IDS = 10

REACT_SYSTEM_PROMPT_APPEND = """
【聊天下载】当用户需要下载已存在的知识库文档时：
1. 先用 execute_sql 查询 document 表确认 id（勿一次查出大量行）。
2. 再调用工具 register_chat_document_sources，action_input 示例：{"document_ids":[15]} 或 {"ids":[15,16]}。
3. 单次最多 """ + str(MAX_DOCUMENT_IDS) + """ 个 id；只填真实存在的 id。"""


async def register_chat_document_sources(**kw: Any) -> str:
    ctx = kw.get("_tool_context")
    if ctx is None:
        return "错误：缺少工具上下文。"
    pool = getattr(ctx, "pool", None)
    if pool is None:
        return "错误：无数据库连接。"

    raw = kw.get("document_ids")
    if raw is None:
        raw = kw.get("ids")
    if raw is None:
        return "请提供 document_ids 或 ids（JSON 整数数组）。"
    if not isinstance(raw, list):
        return "document_ids / ids 须为数组。"

    ids: List[int] = []
    for x in raw[:MAX_DOCUMENT_IDS]:
        try:
            ids.append(int(x))
        except (TypeError, ValueError):
            continue
    ids = list(dict.fromkeys(ids))
    if not ids:
        return "没有有效的整数文档 id。"

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, original_filename, file_type
            FROM document
            WHERE id = ANY($1::int[])
            """,
            ids,
        )

    if not rows:
        ctx.extra[_SOURCES_EXTRA_BUCKET] = []
        return "未找到任何对应文档，已清空界面下载列表。"

    row_by_id: Dict[int, Any] = {int(r["id"]): r for r in rows}
    sources: List[Dict[str, Any]] = []
    for i in ids:
        r = row_by_id.get(i)
        if r is None:
            continue
        orig = (r["original_filename"] or "").strip()
        if not orig:
            continue
        ft = (r["file_type"] or "pdf")
        if isinstance(ft, str):
            ft = (ft.lower() or "pdf")
        else:
            ft = "pdf"
        sources.append(
            {
                "document_id": i,
                "document_name": orig,
                "original_filename": orig,
                "file_type": ft,
                "similarity": 1.0,
                "chunk_id": 0,
                "from_sql_react": True,
            }
        )

    ctx.extra[_SOURCES_EXTRA_BUCKET] = sources
    preview = ", ".join(s["original_filename"] for s in sources[:5])
    tail = f" 等共 {len(sources)} 个" if len(sources) > 5 else ""
    return f"已为聊天界面注册 {len(sources)} 个可下载文档：{preview}{tail}。"


REACT_TOOLS = {
    "register_chat_document_sources": register_chat_document_sources,
}
