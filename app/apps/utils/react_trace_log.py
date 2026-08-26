# -*- coding: utf-8 -*-
"""ReAct 推理链路落盘，便于排查模型/工具行为。"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import REACT_TRACE_LOG_DIR, REACT_TRACE_LOG_ENABLED


def persist_react_trace(
    *,
    task: str,
    model: str,
    trace: List[Dict[str, Any]],
    meta: Optional[Dict[str, Any]] = None,
    tool_context: Optional[Dict[str, Any]] = None,
    conversation_history: str = "",
    error: Optional[str] = None,
) -> Optional[str]:
    """将完整 ReAct 步骤链写入 JSON 文件；未开启配置时返回 None。"""
    if not REACT_TRACE_LOG_ENABLED:
        return None
    if not trace and not error:
        return None

    os.makedirs(REACT_TRACE_LOG_DIR, exist_ok=True)
    ctx = dict(tool_context or {})
    session_id = ctx.get("session_id") or ctx.get("chat_session_id") or "unknown"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"react_{session_id}_{stamp}_{uuid.uuid4().hex[:8]}.json"
    path = os.path.join(REACT_TRACE_LOG_DIR, filename)

    payload = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "session_id": session_id,
        "task": task,
        "conversation_history": conversation_history,
        "trace": trace,
        "meta": meta or {},
        "error": error,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path
