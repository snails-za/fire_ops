# -*- coding: utf-8 -*-
"""聊天场景：FastMCP 宿主、与 LangChain 的衔接。

会话数据（user_id、sources 等）存在「当前 asyncio 任务 id → dict」里：
一次流式问答整条链路在同一条 Task 里 await，工具也在该 Task 里执行；
两个用户同时问 = 两个不同 Task = 两份数据，不会串。结束时 reset 删掉。"""
import asyncio
import json
import traceback
from typing import Any, Dict, List, Optional, Sequence, cast

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ContentBlock, TextContent, Tool as MCPTool


class ChatTaskExtra:
    """当前 asyncio 任务上的聊天附加上下文（供 MCP 工具读写）。"""

    SOURCES_EXTRA_KEY = "_react_sources"

    def __init__(self) -> None:
        self._task_extras: Dict[int, Dict[str, Any]] = {}

    def set(self, initial: Dict[str, Any]) -> int:
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("ChatTaskExtra.set 须在 async 协程内调用")
        tid = id(task)
        self._task_extras[tid] = dict(initial)
        return tid

    def reset(self, token: int) -> None:
        self._task_extras.pop(token, None)

    def current(self) -> Dict[str, Any]:
        task = asyncio.current_task()
        if task is None:
            return {}
        return self._task_extras.get(id(task), {})


class LangChainMcpBridge:
    """FastMCP 工具列表 ↔ OpenAI function schema、call_tool 封装。"""

    def __init__(self) -> None:
        self._openai_tools_cache: Dict[int, tuple[List[Dict[str, Any]], List[str]]] = {}

    @staticmethod
    def tools_to_openai(tools: List[MCPTool]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for t in sorted(tools, key=lambda x: x.name):
            desc = (t.description or "").strip() or t.name
            out.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": desc,
                        "parameters": t.inputSchema,
                    },
                }
            )
        return out

    async def openai_tools_bundle(
        self, app: FastMCP
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        aid = id(app)
        hit = self._openai_tools_cache.get(aid)
        if hit is not None:
            return hit
        listed = await app.list_tools()
        bundle = (self.tools_to_openai(listed), sorted(t.name for t in listed))
        self._openai_tools_cache[aid] = bundle
        return bundle

    @staticmethod
    def _tool_result_to_str(result: Any) -> str:
        if result is None:
            return ""
        if isinstance(result, str):
            return result
        if isinstance(result, tuple) and result:
            return LangChainMcpBridge._tool_result_to_str(result[0])
        if isinstance(result, dict):
            return json.dumps(result, ensure_ascii=False)
        seq = cast(Sequence[ContentBlock], result)
        parts: List[str] = []
        for block in seq:
            if isinstance(block, TextContent):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "".join(parts)

    async def run_tool(
        self,
        app: FastMCP,
        name: str,
        arguments: Optional[Dict[str, Any]],
    ) -> str:
        n = (name or "").strip()
        try:
            raw = await app.call_tool(n, arguments or {})
            return self._tool_result_to_str(raw)
        except ToolError as e:
            err = str(e)
            if err.startswith("Unknown tool:"):
                hit = self._openai_tools_cache.get(id(app))
                if hit:
                    err = f"{err}。已注册: {', '.join(hit[1])}"
                else:
                    try:
                        listed = await app.list_tools()
                        err = f"{err}。已注册: {', '.join(sorted(t.name for t in listed))}"
                    except Exception:
                        pass
            return err
        except Exception:
            traceback.print_exc()
            return f"工具执行异常 {n}"


class McpChatHost:
    """聊天用 FastMCP 宿主（进程内单例）。"""

    def __init__(self, name: str = "mcp_tools") -> None:
        self._app = FastMCP(name)

    @property
    def app(self) -> FastMCP:
        return self._app


chat_task_extra = ChatTaskExtra()
SOURCES_EXTRA_KEY = ChatTaskExtra.SOURCES_EXTRA_KEY

langchain_mcp_bridge = LangChainMcpBridge()

mcp_chat_host = McpChatHost()
mcp_server_app = mcp_chat_host.app
