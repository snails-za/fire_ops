# -*- coding: utf-8 -*-
"""XML ReAct：会话 XML 拼装、增量标签抽取、完整 <step> 解析。

与 MCP / LangChain 解耦；仅处理文本结构与 LangChain 消息块取字。"""
from __future__ import annotations

import json
import re
import xml.sax.saxutils as xml_esc
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


@dataclass
class ReactStep:
    """结构化后的模型单步输出，隔离 XML 细节。"""

    raw_xml: str
    body_xml: str
    thought: Optional[str] = None
    action: Optional[str] = None
    action_input: Optional[Any] = None
    final_answer: Optional[str] = None
    parse_error: Optional[str] = None

    @property
    def is_final(self) -> bool:
        return self.final_answer is not None

    @property
    def needs_tool(self) -> bool:
        return self.action is not None and self.action_input is not None


class XmlDeltaExtractor:
    """从流式 XML 文本中抽取指定标签的新增内容。"""

    _EVENT_BY_TAG = {
        "thought": "thought_delta",
        "final_answer": "final_answer_delta",
    }

    def __init__(self) -> None:
        self.buffer = ""
        self._emitted_lengths = {tag: 0 for tag in self._EVENT_BY_TAG}

    def feed(self, text: str) -> List[Dict[str, str]]:
        self.buffer += text
        events: List[Dict[str, str]] = []
        for tag, event_name in self._EVENT_BY_TAG.items():
            content = self._visible_tag_content(tag)
            emitted_length = self._emitted_lengths[tag]
            if len(content) <= emitted_length:
                continue
            delta = content[emitted_length:]
            self._emitted_lengths[tag] = len(content)
            if delta:
                events.append({"event": event_name, "text": delta})
        return events

    def raw_xml(self) -> str:
        return self.buffer.strip()

    def _visible_tag_content(self, tag: str) -> str:
        start, end = self._tag_content_bounds(tag)
        if start is None:
            return ""
        content = self.buffer[start:] if end is None else self.buffer[start:end]
        if end is None:
            content = self._strip_partial_close_tag(tag, content)
        return content

    def _tag_content_bounds(self, tag: str) -> Tuple[Optional[int], Optional[int]]:
        open_match = re.search(rf"<{tag}\s*>", self.buffer, flags=re.IGNORECASE)
        if not open_match:
            return None, None
        start = open_match.end()
        close_match = re.search(rf"</{tag}\s*>", self.buffer[start:], flags=re.IGNORECASE)
        if not close_match:
            return start, None
        return start, start + close_match.start()

    @staticmethod
    def _strip_partial_close_tag(tag: str, text: str) -> str:
        close_tag = f"</{tag}>"
        for length in range(len(close_tag) - 1, 1, -1):
            suffix = close_tag[:length]
            if text.lower().endswith(suffix.lower()):
                return text[:-length]
        return text


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
            + "</turn>\n"
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
    def _step_inner(cls, raw: str) -> str:
        raw = cls._strip_fence(raw)
        inner = cls._extract_tag(raw, "step")
        return inner if inner is not None else raw

    @classmethod
    def parse_step(cls, raw_xml: str) -> ReactStep:
        """把模型输出解析成结构化 step，调用方无需关心 XML 标签。"""
        body_xml = cls._step_inner(raw_xml)
        thought = cls._extract_tag(body_xml, "thought")
        final_answer = cls._extract_tag(body_xml, "final_answer")
        if final_answer is not None:
            return ReactStep(
                raw_xml=raw_xml,
                body_xml=body_xml,
                thought=xml_esc.unescape(thought.strip()) if thought else None,
                final_answer=xml_esc.unescape(final_answer.strip()) or None,
            )

        action = cls._extract_tag(body_xml, "action")
        if not action:
            return ReactStep(
                raw_xml=raw_xml,
                body_xml=body_xml,
                thought=xml_esc.unescape(thought.strip()) if thought else None,
                parse_error="解析失败：需要 <action> 与 <action_input>（单行 JSON），或 <final_answer>。",
            )

        action_name = action.strip()
        if re.match(r"(?i)^final_answer$", action_name):
            return ReactStep(
                raw_xml=raw_xml,
                body_xml=body_xml,
                thought=xml_esc.unescape(thought.strip()) if thought else None,
                parse_error="解析失败：final_answer 必须使用 <final_answer> 标签，而不是 <action>。",
            )

        raw_action_input = cls._extract_tag(body_xml, "action_input")
        if raw_action_input is None:
            return ReactStep(
                raw_xml=raw_xml,
                body_xml=body_xml,
                thought=xml_esc.unescape(thought.strip()) if thought else None,
                action=action_name,
                parse_error="解析失败：<action_input> 须为合法 JSON。",
            )

        try:
            action_input = json.loads(raw_action_input.strip())
        except json.JSONDecodeError:
            return ReactStep(
                raw_xml=raw_xml,
                body_xml=body_xml,
                thought=xml_esc.unescape(thought.strip()) if thought else None,
                action=action_name,
                parse_error="解析失败：<action_input> 须为合法 JSON。",
            )

        return ReactStep(
            raw_xml=raw_xml,
            body_xml=body_xml,
            thought=xml_esc.unescape(thought.strip()) if thought else None,
            action=action_name,
            action_input=action_input,
        )

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

    @classmethod
    async def stream_react_step(
        cls,
        llm: ChatOpenAI,
        system_prompt: str,
        human_xml: str,
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式返回可展示增量，并在结束时返回结构化 ReactStep。"""
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=human_xml)]
        extractor = XmlDeltaExtractor()
        async for chunk in llm.astream(messages):
            piece = cls.langchain_chunk_text(chunk)
            if not piece:
                continue
            for event in extractor.feed(piece):
                yield event
        yield {
            "event": "react_step_done",
            "step": cls.parse_step(extractor.raw_xml()),
        }
