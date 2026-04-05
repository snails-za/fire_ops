# -*- coding: utf-8 -*-
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from mcp_tools.sql_plugin import (
    SqlToolConfig,
    SqlToolContext,
    builtin_execute_sql,
    builtin_get_database_schema,
    get_sql_pool,
)


class SqlToolsModule:
    """数据库只读 MCP 工具模块。"""

    TOOL_PROMPT_APPEND = """
【数据库查询】涉及库表与指标时：
- 先调用 get_database_schema 了解 public 表结构，再按需 execute_sql。
- 只读：单条 SELECT/WITH，禁止多语句与 DML；勿使用 SELECT *。
"""

    def __init__(self, cfg: Optional[SqlToolConfig] = None) -> None:
        self._cfg = cfg or SqlToolConfig()

    def register(self, app: FastMCP) -> None:
        cfg = self._cfg

        @app.tool(annotations=ToolAnnotations(readOnlyHint=True))
        async def get_database_schema() -> str:
            """列出 public schema 表与列（写 SQL 前应先调用）。"""
            pool = await get_sql_pool()
            return await builtin_get_database_schema(SqlToolContext(pool, cfg))

        @app.tool(annotations=ToolAnnotations(readOnlyHint=True))
        async def execute_sql(sql: str) -> str:
            """执行单条只读 SELECT/WITH；禁止多语句与 DML；勿使用 SELECT *。"""
            pool = await get_sql_pool()
            return await builtin_execute_sql(SqlToolContext(pool, cfg), sql=sql)
