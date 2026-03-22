"""ReAct 问答结果 → SSE 文本行（data: ...\\n\\n）。与 Agent、HTTP 路由解耦，仅做展示协议。"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional


def sse_data_line(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _chunk_text(text: str, chunk_size: int) -> List[str]:
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def _tool_status_payloads(meta: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    for t in meta.get("react_trace") or []:
        name = t.get("action")
        ob = t.get("observation")
        if name:
            yield {"type": "status", "message": f"🔧 工具: {name}"}
        if ob is not None:
            ok = not str(ob).startswith("解析失败")
            label = name or "?"
            pre = str(ob)[:120]
            yield {
                "type": "status",
                "message": f"{'✓' if ok else '✗'} {label}: {pre}...",
            }


def iter_react_chat_sse_lines(
    answer: Optional[str],
    meta: Dict[str, Any],
    *,
    chunk_size: int = 48,
    pattern: str = "react_xml_sql",
) -> Iterator[str]:
    """
    将 (answer, meta) 转为 SSE 行序列：error | status* | sources | content* | done。
    answer 为 None 时只输出 error（取自 meta.error）。
    """
    if answer is None:
        yield sse_data_line(
            {"type": "error", "message": meta.get("error") or "问答失败"}
        )
        return

    for p in _tool_status_payloads(meta):
        yield sse_data_line(p)

    search_info = {
        "pattern": meta.get("pattern", pattern),
        "react_steps": meta.get("react_steps"),
    }
    yield sse_data_line(
        {
            "type": "sources",
            "sources": [],
            "search_info": search_info,
            "keywords": [],
            "devices": [],
        }
    )

    current = ""
    for part in _chunk_text(answer, chunk_size):
        current += part
        yield sse_data_line({"type": "content", "content": current})

    yield sse_data_line({"type": "done"})


async def iter_sse_from_agent_streaming(
    agent: Any,
    task: str,
    tool_context: Optional[Dict[str, Any]] = None,
) -> AsyncIterator[str]:
    """
    将 ReactSqlAgent.run_streaming() 的事件转为 SSE 行：
    thought（累积）| content（累积）| status | error | sources | done。
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
            yield sse_data_line({"type": "status", "message": f"🔧 工具: {ev.get('name')}"})
        elif et == "tool_end":
            ok = ev.get("ok")
            preview = str(ev.get("preview") or "")
            label = ev.get("name") or "?"
            sym = "✓" if ok else "✗"
            yield sse_data_line(
                {"type": "status", "message": f"{sym} {label}: {preview[:120]}..."}
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
                    "sources": [],
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


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "text/event-stream",
}
