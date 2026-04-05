# -*- coding: utf-8 -*-
"""XML ReAct：会话 XML 拼装、<step> 解析、流式 <thought>/<final_answer> 增量。

与 MCP / LangChain 解耦；仅处理文本结构与 LangChain 消息块取字。"""
from __future__ import annotations

import json
import re
import xml.sax.saxutils as xml_esc
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


class XmlReactSession:
    """ReAct 一轮对话里与 XML 相关的纯逻辑（无 IO）。"""

    @staticmethod
    def build_human_xml(task: str, history_xml: str, instruction: str) -> str:
        te = xml_esc.escape(task.strip(), entities={'"': "&quot;", "'": "&apos;"})
        inst = xml_esc.escape(instruction, entities={'"': "&quot;", "'": "&apos;"})
        hist = history_xml.strip()
        return (
            f"<react_session>\n"
            f"  <task>{te}</task>\n"
            f"  <history>\n{hist}\n  </history>\n"
            f"  <instruction>{inst}</instruction>\n"
            f"</react_session>"
        )

    @staticmethod
    def append_history(history: str, step_idx: int, model_xml: str, observation: str) -> str:
        ent = {chr(34): "&quot;", chr(39): "&apos;"}
        m = xml_esc.escape(model_xml, entities=ent)
        o = xml_esc.escape(observation, entities=ent)
        return (
            history
            + f'<turn index="{step_idx}">\n'
            + f"  <model>{m}</model>\n"
            + f"  <observation>{o}</observation>\n"
            + f"</turn>\n"
        )

    @staticmethod
    def _strip_fence(text: str) -> str:
        s = text.strip()
        if not s.startswith("```"):
            return s
        s = re.sub(r"^```[a-zA-Z0-9]*\s*\n?", "", s)
        s = re.sub(r"\n?```\s*$", "", s)
        return s.strip()

    @staticmethod
    def _extract_tag(text: str, tag: str) -> Optional[str]:
        pat = rf"<{tag}\s*>(.*?)</{tag}\s*>"
        m = re.search(pat, text, flags=re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else None

    @classmethod
    def step_inner(cls, raw: str) -> str:
        raw = cls._strip_fence(raw)
        inner = cls._extract_tag(raw, "step")
        return inner if inner is not None else raw

    @classmethod
    def parse_final_answer(cls, step_inner: str) -> Optional[str]:
        fa = cls._extract_tag(step_inner, "final_answer")
        if not fa or not fa.strip():
            return None
        return xml_esc.unescape(fa.strip()) or None

    @classmethod
    def parse_action(cls, step_inner: str) -> Tuple[Optional[str], Optional[Any]]:
        act = cls._extract_tag(step_inner, "action")
        if not act:
            return None, None
        name = act.strip()
        if re.match(r"(?i)^final_answer$", name):
            return None, None
        raw_j = cls._extract_tag(step_inner, "action_input")
        if raw_j is None:
            return name, None
        try:
            return name, json.loads(raw_j.strip())
        except json.JSONDecodeError:
            return name, None

    @staticmethod
    def langchain_chunk_text(msg: Any) -> str:
        c = getattr(msg, "content", msg)
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            parts: List[str] = []
            for b in c:
                if isinstance(b, dict) and b.get("type") == "text":
                    parts.append(str(b.get("text", "")))
                elif isinstance(b, str):
                    parts.append(b)
            return "".join(parts)
        return str(c or "")

    @staticmethod
    def _tag_bounds(buf: str, tag: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        open_pat = re.compile(rf"<{tag}\s*>", re.IGNORECASE)
        close_pat = re.compile(rf"</{tag}\s*>", re.IGNORECASE)
        mo = open_pat.search(buf)
        if not mo:
            return None, None, None
        start = mo.end()
        mc = close_pat.search(buf, start)
        if not mc:
            return start, None, None
        return start, mc.start(), mc.end()

    @staticmethod
    def _strip_incomplete_close_tag_suffix(tag: str, text: str) -> str:
        close = f"</{tag}>"
        if len(text) < 2:
            return text
        for k in range(len(close) - 1, 1, -1):
            suf = close[:k]
            if len(text) >= k and text[-k:].lower() == suf.lower():
                return text[:-k]
        return text

    @classmethod
    def stream_tag_content_deltas(
        cls, buffer: str, tag: str, emitted_length: int
    ) -> Tuple[List[str], int, bool]:
        start, end, _ = cls._tag_bounds(buffer, tag)
        if start is None:
            return [], emitted_length, False
        chunk = buffer[start:] if end is None else buffer[start:end]
        if end is None:
            chunk = cls._strip_incomplete_close_tag_suffix(tag, chunk)
        if len(chunk) <= emitted_length:
            return [], emitted_length, end is not None
        new_part = chunk[emitted_length:]
        new_len = len(chunk)
        return ([new_part] if new_part else []), new_len, end is not None

    @classmethod
    async def stream_llm_turn(
        cls,
        llm: ChatOpenAI,
        system_prompt: str,
        human_xml: str,
    ) -> AsyncIterator[Dict[str, Any]]:
        """LLM astream → thought_delta / final_answer_delta / llm_turn_done。"""
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=human_xml)]
        buf = ""
        te = 0
        fe = 0
        async for chunk in llm.astream(messages):
            piece = cls.langchain_chunk_text(chunk)
            if not piece:
                continue
            buf += piece
            td, te, _ = cls.stream_tag_content_deltas(buf, "thought", te)
            for d in td:
                yield {"event": "thought_delta", "text": d}
            fd, fe, _ = cls.stream_tag_content_deltas(buf, "final_answer", fe)
            for d in fd:
                yield {"event": "final_answer_delta", "text": d}
        yield {"event": "llm_turn_done", "raw": buf.strip()}
