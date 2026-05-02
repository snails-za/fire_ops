# -*- coding: utf-8 -*-
"""XML ReAct + FastMCP 工具执行（`langchain_mcp_bridge.run_tool`）。

XML 拼装与解析见 `xml_react.XmlReactSession`。
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from langchain_openai import ChatOpenAI
from mcp.server.fastmcp import FastMCP
from pydantic import SecretStr

from apps.utils.xml_react import XmlReactSession
from apps.utils.mcp_tools.mcp_bridge import SOURCES_EXTRA_KEY, chat_task_extra, langchain_mcp_bridge
from apps.utils.mcp_tools.tools import TOOL_PROMPTS


@dataclass
class ReactAgentConfig:
    model: str = "deepseek-chat"
    max_iterations: int = 10
    temperature: float = 0.1
    max_tokens: int = 2500


SYSTEM_PROMPT = """你是数据分析助手，必须用 ReAct：思考 →（如需）行动 → 观察 → 再思考，直到能回答用户。

【XML 输出规则】每一轮只输出一个根元素 <step>，根外不要任何文字、不要用 markdown 代码块。

结构一（需要工具）：
<step>
  <thought>中文推理：为什么要调用工具、期望得到什么</thought>
  <action>工具名称（须与下列注册名完全一致）</action>
  <action_input>单行 JSON，作为工具参数对象</action_input>
</step>

结构二（可以作答）：
<step>
  <thought>中文：如何根据已有 Observation 得出结论</thought>
  <final_answer>给用户的完整中文回答；特殊字符请用 &amp; &lt; &gt;</final_answer>
</step>

【对用户可见内容】仅指 <final_answer> 及其中的文字（业务用户会看到）：
- 不要写出真实数据库表名、视图名、字段/列名、索引名、约束名等技术标识（含英文蛇形命名、information_schema 等）；用业务语义概括，例如「近一周告警数量」「某类设备台账」。
- 不要逐字复述 SQL、工具返回里的表头行；结论用自然语言与数字/日期即可。
- <thought>、<action>、<action_input> 及 SQL 仍须使用真实库表与列名以便工具执行，但勿在 <final_answer> 中原样粘贴。

【工具调用】使用 <action> 与 <action_input>（单行 JSON）。能力说明见下文「工具说明」；名称必须与「当前已注册工具名」列表一致。

【安全（必须遵守）】
- 不得帮用户查询或推断密码、口令、token、密钥、盐值等凭据；用户索要密码时须在 final_answer 中明确拒绝并说明原因。
- 不要尝试查询含 password 等敏感列；系统会拦截，你应尊重拦截结果。

【禁止】
- 不要自己编造 <observation>，系统会在你输出后追加。
- 不要臆造查询结果；以 Observation 为准。"""


def _tool_names_line(names_sorted: List[str]) -> str:
    return f"当前已注册工具名: {', '.join(names_sorted)}"


class ReactAgent:
    def __init__(
        self,
        openai_api_key: str,
        openai_base_url: str,
        mcp_server_app: FastMCP,
        config: Optional[ReactAgentConfig] = None,
    ) -> None:
        self.openai_api_key = openai_api_key
        self.openai_base_url = openai_base_url
        self.mcp_server_app = mcp_server_app
        self.config = config or ReactAgentConfig()

    async def run_streaming(
        self,
        task: str,
        tool_context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        if not (self.openai_api_key or "").strip():
            yield {"event": "error", "message": "LLM 未配置 OPENAI_API_KEY"}
            yield {
                "event": "done",
                "meta": {"error": "LLM 未配置 OPENAI_API_KEY", "agent_used": False},
            }
            return

        extra_token = chat_task_extra.set(dict(tool_context or {}))
        try:
            _, names_sorted = await langchain_mcp_bridge.openai_tools_bundle(self.mcp_server_app)

            llm = ChatOpenAI(
                api_key=SecretStr(self.openai_api_key),
                base_url=self.openai_base_url,
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            system_prompt = (
                SYSTEM_PROMPT
                + TOOL_PROMPTS
                + "\n\n"
                + _tool_names_line(names_sorted)
            )

            history_xml = ""
            trace: List[Dict[str, Any]] = []
            meta_finish: Dict[str, Any] = {
                "agent_used": True,
                "pattern": "react_xml_sql",
                "react_trace": trace,
            }
            last_react_doc_sources: List[Dict[str, Any]] = []

            def _sync_sources() -> None:
                nonlocal last_react_doc_sources
                bucket = chat_task_extra.current().get(SOURCES_EXTRA_KEY)
                if isinstance(bucket, list) and bucket:
                    last_react_doc_sources = list(bucket)

            for step in range(self.config.max_iterations):
                inst = (
                    "根据 <task> 与 <history> 输出下一轮：仅一个 <step>。"
                    "若需外部信息，按系统提示中的工具说明与「当前已注册工具名」选择调用；"
                    "信息足够则输出 final_answer。"
                )
                human = XmlReactSession.build_human_xml(task, history_xml, inst)
                yield {"event": "turn_start", "step": step + 1}
                parsed_step = None
                async for ev in XmlReactSession.stream_react_step(llm, system_prompt, human):
                    if ev.get("event") == "react_step_done":
                        parsed_step = ev["step"]
                    else:
                        yield ev

                if parsed_step is None:
                    raise RuntimeError("LLM 输出解析失败：缺少 react_step_done")

                trace.append({
                    "step": step + 1,
                    "raw": parsed_step.raw_xml,
                    "step_inner": parsed_step.body_xml,
                    "thought": parsed_step.thought,
                })

                if parsed_step.is_final:
                    meta_finish["final_answer"] = parsed_step.final_answer
                    meta_finish["react_steps"] = len(trace)
                    meta_finish["sources"] = last_react_doc_sources
                    yield {"event": "done", "meta": meta_finish}
                    return

                if parsed_step.parse_error:
                    obs = parsed_step.parse_error
                    history_xml = XmlReactSession.append_history(history_xml, step + 1, parsed_step.raw_xml, obs)
                    trace[-1]["observation"] = obs
                    yield {
                        "event": "tool_end",
                        "name": parsed_step.action,
                        "ok": False,
                        "preview": obs[:200],
                    }
                    continue

                if not parsed_step.needs_tool:
                    obs = "解析失败：未得到可执行的工具调用。"
                    history_xml = XmlReactSession.append_history(history_xml, step + 1, parsed_step.raw_xml, obs)
                    trace[-1]["observation"] = obs
                    yield {
                        "event": "tool_end",
                        "name": parsed_step.action,
                        "ok": False,
                        "preview": obs[:200],
                    }
                    continue

                action = parsed_step.action
                action_input = parsed_step.action_input
                trace[-1]["action"] = action
                trace[-1]["action_input"] = action_input
                yield {"event": "tool_start", "name": action}
                observation = await langchain_mcp_bridge.run_tool(
                    self.mcp_server_app, action, action_input
                )
                trace[-1]["observation"] = observation[:800]
                history_xml = XmlReactSession.append_history(
                    history_xml, step + 1, parsed_step.raw_xml, observation
                )
                _sync_sources()
                yield {
                    "event": "tool_end",
                    "name": action,
                    "ok": True,
                    "preview": observation[:300],
                }

            inst = (
                "步数已达上限，请只输出 <step><thought>...</thought><final_answer>...</final_answer></step>，"
                "不要调用工具。"
            )
            human = XmlReactSession.build_human_xml(task, history_xml, inst)
            yield {"event": "turn_start", "step": "final"}
            parsed_step = None
            async for ev in XmlReactSession.stream_react_step(llm, system_prompt, human):
                if ev.get("event") == "react_step_done":
                    parsed_step = ev["step"]
                else:
                    yield ev

            if parsed_step is None:
                raise RuntimeError("LLM 输出解析失败：缺少 react_step_done")

            trace.append({
                "step": "final",
                "raw": parsed_step.raw_xml,
                "step_inner": parsed_step.body_xml,
                "thought": parsed_step.thought,
            })
            final_answer = (
                parsed_step.final_answer
                or "抱歉，推理步数已用尽，请缩小问题范围后重试。"
            )
            if not parsed_step.final_answer:
                yield {"event": "final_answer_delta", "text": final_answer}
            meta_finish["final_answer"] = final_answer
            meta_finish["react_steps"] = len(trace)
            meta_finish["sources"] = last_react_doc_sources
            yield {"event": "done", "meta": meta_finish}

        except Exception as e:
            traceback.print_exc()
            yield {"event": "error", "message": str(e)}
            yield {"event": "done", "meta": {"error": str(e), "agent_used": False}}
        finally:
            chat_task_extra.reset(extra_token)

    async def run(
        self,
        task: str,
        tool_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        last_meta: Dict[str, Any] = {}
        last_answer: Optional[str] = None
        async for ev in self.run_streaming(task, tool_context):
            if ev.get("event") == "done":
                last_meta = ev.get("meta") or {}
                last_answer = last_meta.get("final_answer")
        return last_answer, last_meta
