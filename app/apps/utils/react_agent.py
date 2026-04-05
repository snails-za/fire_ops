# -*- coding: utf-8 -*-
"""ReAct：LangChain tool_calls；工具来自传入的 FastMCP 实例。"""
import traceback
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from mcp.server.fastmcp import FastMCP

from mcp_tools.mcp_bridge import (
    SOURCES_EXTRA_KEY,
    chat_extra,
    chat_extra_reset,
    chat_extra_set,
    openai_tools_bundle,
    run_tool,
)
from mcp_tools.tools import TOOL_PROMPTS


@dataclass
class ReactAgentConfig:
    model: str = "deepseek-chat"
    max_iterations: int = 10
    temperature: float = 0.1
    max_tokens: int = 2500


SYSTEM_PROMPT = """你是数据分析与运维助手。在需要事实数据时调用工具（function calling），根据工具返回结果推理；信息足够后直接用自然语言回复用户，勿再调用工具。

【流程建议】
- 工具返回即「观察结果」，不得臆造；若工具报错应如实说明并调整策略。

【安全（必须遵守）】
- 不得帮用户查询或推断密码、口令、token、密钥、盐值等凭据；用户索要密码时须明确拒绝并说明原因。
- 不要尝试查询含 password 等敏感列；系统会拦截，你应尊重拦截结果。

【输出】最终回答使用简洁、准确的中文；勿输出 XML 或虚构的工具返回。"""


def _chunk_text_for_sse(text: str, size: int = 160) -> List[str]:
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]


@dataclass
class ReactAgent:
    openai_api_key: str
    openai_base_url: str
    tool_mcp: FastMCP
    config: ReactAgentConfig = field(default_factory=ReactAgentConfig)

    def _tool_names_line(self, names: List[str]) -> str:
        return f"当前已注册工具名: {', '.join(names)}"

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

        tok = chat_extra_set(dict(tool_context or {}))
        try:
            openai_tools, names_sorted = await openai_tools_bundle(self.tool_mcp)

            llm = ChatOpenAI(
                api_key=self.openai_api_key,
                model=self.config.model,
                base_url=self.openai_base_url,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            llm_tools = llm.bind_tools(openai_tools, tool_choice="auto")
            system_prompt = (
                SYSTEM_PROMPT
                + TOOL_PROMPTS
                + "\n\n"
                + self._tool_names_line(names_sorted)
            )

            messages: List[BaseMessage] = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=task.strip()),
            ]
            trace: List[Dict[str, Any]] = []
            meta_finish: Dict[str, Any] = {
                "agent_used": True,
                "pattern": "react_mcp_tools",
                "react_trace": trace,
            }
            last_react_doc_sources: List[Dict[str, Any]] = []

            def _sync_sources() -> None:
                nonlocal last_react_doc_sources
                bucket = chat_extra().get(SOURCES_EXTRA_KEY)
                if isinstance(bucket, list) and bucket:
                    last_react_doc_sources = list(bucket)

            for step in range(self.config.max_iterations):
                yield {"event": "turn_start", "step": step + 1}
                ai_msg = await llm_tools.ainvoke(messages)
                if not isinstance(ai_msg, AIMessage):
                    ai_msg = AIMessage(content=str(ai_msg))

                messages.append(ai_msg)
                assistant_text = (ai_msg.content if isinstance(ai_msg.content, str) else "").strip()
                tcs = list(ai_msg.tool_calls or [])
                trace.append(
                    {
                        "step": step + 1,
                        "assistant": assistant_text,
                        "tool_calls": tcs,
                    }
                )

                if assistant_text:
                    ev = "thought_delta" if tcs else "final_answer_delta"
                    for piece in _chunk_text_for_sse(assistant_text):
                        yield {"event": ev, "text": piece}

                if not tcs:
                    final = assistant_text or "抱歉，未能生成有效回答。"
                    meta_finish["final_answer"] = final
                    meta_finish["react_steps"] = len(trace)
                    meta_finish["sources"] = last_react_doc_sources
                    yield {"event": "done", "meta": meta_finish}
                    return

                for tc in tcs:
                    name = (tc.get("name") or "").strip()
                    tid = tc.get("id") or ""
                    args = tc.get("args")
                    payload: Dict[str, Any] = args if isinstance(args, dict) else {}
                    if name.lower().replace(" ", "_") == "get_database_schema" and not payload:
                        payload = {}
                    yield {"event": "tool_start", "name": name or None}
                    observation = await run_tool(self.tool_mcp, name, payload)
                    trace[-1].setdefault("observations", []).append(
                        {name: (observation[:800] if observation else "")}
                    )
                    messages.append(ToolMessage(content=observation, tool_call_id=tid))
                    _sync_sources()
                    yield {
                        "event": "tool_end",
                        "name": name or None,
                        "ok": True,
                        "preview": (observation or "")[:300],
                    }

            yield {"event": "turn_start", "step": "final"}
            messages.append(
                HumanMessage(
                    content="（系统提示）推理步数已达上限，请仅根据当前对话中的工具结果，"
                    "用中文直接给出最终结论，不要再调用任何工具。"
                )
            )
            final_ai = await llm.ainvoke(messages)
            fc = getattr(final_ai, "content", final_ai)
            final_text = (fc if isinstance(fc, str) else "").strip()
            if not final_text:
                final_text = "抱歉，推理步数已用尽，请缩小问题范围后重试。"
            for piece in _chunk_text_for_sse(final_text):
                yield {"event": "final_answer_delta", "text": piece}
            trace.append({"step": "final", "assistant": final_text, "tool_calls": []})
            meta_finish["final_answer"] = final_text
            meta_finish["react_steps"] = len(trace)
            meta_finish["sources"] = last_react_doc_sources
            yield {"event": "done", "meta": meta_finish}

        except Exception as e:
            traceback.print_exc()
            yield {"event": "error", "message": str(e)}
            yield {"event": "done", "meta": {"error": str(e), "agent_used": False}}
        finally:
            chat_extra_reset(tok)
