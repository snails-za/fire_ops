"""ReAct 问答结果 → SSE 文本行（data: ...\\n\\n）。与 Agent、HTTP 路由解耦，仅做展示协议。"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, Optional


def sse_data_line(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def iter_sse_from_agent_streaming(
    agent: Any,
    task: str,
    tool_context: Optional[Dict[str, Any]] = None,
) -> AsyncIterator[str]:
    """
    将 ReactAgent.run_streaming() 的事件转为 SSE 行：
    thought（累积）| content（累积）| action（工具调用/结果摘要）| error | sources | done。
    """
    thought_buf = ""
    content_buf = ""
    async for ev in agent.run_streaming(task, tool_context):
        et = ev.get("event")
        if et == "turn_start":
            thought_buf = ""
            content_buf = ""
            continue
        if et == "thought_delta":
            thought_buf += ev.get("text") or ""
            yield sse_data_line({"type": "thought", "content": thought_buf})
        elif et == "final_answer_delta":
            content_buf += ev.get("text") or ""
            yield sse_data_line({"type": "content", "content": content_buf})
        elif et == "tool_start":
            yield sse_data_line({"type": "action", "message": f"🔧 工具: {ev.get('name')}"})
        elif et == "tool_end":
            ok = ev.get("ok")
            preview = str(ev.get("preview") or "")
            label = ev.get("name") or "?"
            sym = "✓" if ok else "✗"
            yield sse_data_line(
                {"type": "action", "message": f"{sym} {label}: {preview[:120]}..."}
            )
        elif et == "error":
            yield sse_data_line({"type": "error", "message": ev.get("message") or "错误"})
        elif et == "done":
            meta = ev.get("meta") or {}
            search_info = {
                "pattern": meta.get("pattern", "react_xml_sql"),
                "react_steps": meta.get("react_steps"),
            }
            yield sse_data_line(
                {
                    "type": "sources",
                    "sources": meta.get("sources") or [],
                    "search_info": search_info,
                    "keywords": [],
                    "devices": [],
                }
            )
            yield sse_data_line(
                {
                    "type": "done",
                    "error": meta.get("error"),
                }
            )

