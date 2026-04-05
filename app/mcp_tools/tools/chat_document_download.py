# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from mcp_tools.mcp_bridge import ChatTaskExtra, chat_task_extra
from mcp_tools.sql_plugin import get_sql_pool

MAX_DOCUMENT_IDS = 10


class ChatDocumentToolsModule:
    """聊天下载文档来源注册 MCP 工具模块。"""

    TOOL_PROMPT_APPEND = """
【聊天下载】当用户需要下载已存在的知识库文档时：
1. 先用 execute_sql 查询 document 表确认 id（勿一次查出大量行）。
2. 再调用工具 register_chat_document_sources，参数示例：{"document_ids":[15]} 或 {"ids":[15,16]}。
3. 单次最多 """ + str(
        MAX_DOCUMENT_IDS
    ) + """ 个 id；只填真实存在的 id。"""

    def __init__(self, extra: Optional[ChatTaskExtra] = None) -> None:
        self._extra = extra or chat_task_extra

    async def _register_impl(
        self,
        document_ids: Optional[List[int]],
        ids: Optional[List[int]],
    ) -> str:
        pool = await get_sql_pool()
        bucket = self._extra.current()

        raw = document_ids if document_ids is not None else ids
        if raw is None:
            return "请提供 document_ids 或 ids（JSON 整数数组）。"
        if not isinstance(raw, list):
            return "document_ids / ids 须为数组。"

        id_list: List[int] = []
        for x in raw[:MAX_DOCUMENT_IDS]:
            try:
                id_list.append(int(x))
            except (TypeError, ValueError):
                continue
        id_list = list(dict.fromkeys(id_list))
        if not id_list:
            return "没有有效的整数文档 id。"

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, original_filename, file_type
                FROM document
                WHERE id = ANY($1::int[])
                """,
                id_list,
            )

        if not rows:
            bucket[ChatTaskExtra.SOURCES_EXTRA_KEY] = []
            return "未找到任何对应文档，已清空界面下载列表。"

        row_by_id: Dict[int, Any] = {int(r["id"]): r for r in rows}
        sources: List[Dict[str, Any]] = []
        for i in id_list:
            r = row_by_id.get(i)
            if r is None:
                continue
            orig = (r["original_filename"] or "").strip()
            if not orig:
                continue
            ft = (r["file_type"] or "pdf")
            if isinstance(ft, str):
                ft = ft.lower() or "pdf"
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

        bucket[ChatTaskExtra.SOURCES_EXTRA_KEY] = sources
        preview = ", ".join(s["original_filename"] for s in sources[:5])
        tail = f" 等共 {len(sources)} 个" if len(sources) > 5 else ""
        return f"已为聊天界面注册 {len(sources)} 个可下载文档：{preview}{tail}。"

    def register(self, app: FastMCP) -> None:
        @app.tool()
        async def register_chat_document_sources(
            document_ids: Optional[List[int]] = None,
            ids: Optional[List[int]] = None,
        ) -> str:
            """将知识库文档 id 注册到当前会话供前端下载；需先用 SQL 确认 id 存在。"""
            return await self._register_impl(document_ids, ids)
