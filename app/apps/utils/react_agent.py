# -*- coding: utf-8 -*-
"""XML ReAct + SQL Agent（LLM astream，按 <thought>/<final_answer> 增量解析）。

阅读顺序（自上而下 = 调用链从外到内）：
  ReactAgent → ActionDispatcher / build_tool_registry → 内置工具 → SQL 校验与脱敏
  → XmlStepParser → 流式标签解析（stream_tag_content_deltas）

依赖: langchain-openai, langchain-core, asyncpg。
"""

from __future__ import annotations

import importlib.util
import json
import re
import traceback
import xml.sax.saxutils as xml_esc
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)

import asyncpg
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

ToolFn = Callable[..., Awaitable[str]]

REDACT_PLACEHOLDER = "[已隐藏·敏感字段]"

# ReAct 聊天区「可下载文档」：避免一次 SQL 扫全表列出上百个文件
REACT_SQL_DOC_SOURCE_MAX = 5
REACT_SQL_DOC_MAX_DATA_ROWS = 12  # 超过此行数认为是大范围探测，不自动挂下载


# ---------------------------------------------------------------------------
# 配置与系统提示
# ---------------------------------------------------------------------------


@dataclass
class ReactAgentConfig:
    model: str = "deepseek-chat"
    max_iterations: int = 10
    temperature: float = 0.1
    max_tokens: int = 2500
    sql_readonly: bool = True
    sql_max_rows: int = 500
    sql_statement_timeout_sec: int = 30
    sql_redact_sensitive: bool = True


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

【内置工具】
- get_database_schema — 查看当前库中表与列（模型应先调用以写 SQL）。action_input 用 {}
- execute_sql — 执行 SQL。action_input：{"sql":"..."}。仅允许只读 SELECT/WITH 查询（由系统校验）。

【安全（必须遵守）】
- 不得帮用户查询或推断密码、口令、token、密钥、盐值等凭据；用户索要密码时须在 final_answer 中明确拒绝并说明原因。
- 不要尝试 SELECT 含 password 等敏感列；系统会拦截，你应尊重拦截结果。

【禁止】
- 不要自己编造 <observation>，系统会在你输出后追加。
- 不要臆造查询结果；以 Observation 为准。

【文档下载（界面会列出可下载文件）】
- 仅当你用 execute_sql 查询 **document** 表且一次返回 **很少行**（建议 ≤10 行）时，系统才会在回答下方显示下载入口。
- 若用户只要某一文件，请用 WHERE 条件限定 id 或文件名，不要 SELECT 全表。"""


# ---------------------------------------------------------------------------
# 入口：ReAct 循环 + 流式事件
# ---------------------------------------------------------------------------


@dataclass
class ReactAgent:
    openai_api_key: str
    openai_base_url: str
    database_url: str
    config: ReactAgentConfig = field(default_factory=ReactAgentConfig)
    extra_tools: Optional[Dict[str, ToolFn]] = None
    plugin_dirs: Optional[List[Union[str, Path]]] = None

    def _tool_names_line(self, registry: Dict[str, ToolFn]) -> str:
        return f"当前已注册工具名: {', '.join(sorted(registry.keys()))}"

    def _session_xml(self, task: str, history_xml: str, instruction: str) -> str:
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

    def _history_append(
            self, history: str, step_idx: int, model_xml: str, observation: str
    ) -> str:
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

    async def _iter_llm_turn_stream(
            self, llm: ChatOpenAI, system_prompt: str, human_xml: str
    ) -> AsyncIterator[Dict[str, Any]]:
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=human_xml)]
        buf = ""
        te = 0
        fe = 0
        async for chunk in llm.astream(messages):
            piece = _lc_text_content(chunk)
            if not piece:
                continue
            buf += piece
            td, te, _ = stream_tag_content_deltas(buf, "thought", te)
            for d in td:
                yield {"event": "thought_delta", "text": d}
            fd, fe, _ = stream_tag_content_deltas(buf, "final_answer", fe)
            for d in fd:
                yield {"event": "final_answer_delta", "text": d}
        yield {"event": "llm_turn_done", "raw": buf.strip()}

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

        pool: Optional[asyncpg.Pool] = None
        try:
            pool = await asyncpg.create_pool(
                dsn=_normalize_pg_dsn(self.database_url),
                min_size=1,
                max_size=3,
                statement_cache_size=0,
            )
            sql_ctx = SqlToolContext(pool, self.config)
            if tool_context:
                sql_ctx.extra.update(tool_context)

            registry = build_tool_registry(sql_ctx, self.extra_tools, self.plugin_dirs)
            dispatcher = ActionDispatcher(registry, sql_ctx)

            llm = ChatOpenAI(
                api_key=self.openai_api_key,
                base_url=self.openai_base_url,
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            system_prompt = SYSTEM_PROMPT + "\n\n" + self._tool_names_line(registry)

            history_xml = ""
            trace: List[Dict[str, Any]] = []
            meta_finish: Dict[str, Any] = {
                "agent_used": True,
                "pattern": "react_xml_sql",
                "react_trace": trace,
            }
            last_react_doc_sources: List[Dict[str, Any]] = []

            for step in range(self.config.max_iterations):
                inst = (
                    "根据 <task> 与 <history> 输出下一轮：仅一个 <step>。"
                    "需要访问数据库时，先 get_database_schema 再 execute_sql；"
                    "信息足够则输出 final_answer。"
                )
                human = self._session_xml(task, history_xml, inst)
                raw = ""
                yield {"event": "turn_start", "step": step + 1}
                async for ev in self._iter_llm_turn_stream(llm, system_prompt, human):
                    if ev.get("event") == "llm_turn_done":
                        raw = ev.get("raw") or ""
                    else:
                        yield ev

                trace.append({"step": step + 1, "raw": raw})
                inner = XmlStepParser.step_inner(raw)
                trace[-1]["step_inner"] = inner

                final = XmlStepParser.parse_final_answer(inner)
                if final is not None:
                    meta_finish["final_answer"] = final
                    meta_finish["react_steps"] = len(trace)
                    meta_finish["sources"] = last_react_doc_sources
                    yield {"event": "done", "meta": meta_finish}
                    return

                action, payload = XmlStepParser.parse_action(inner)
                if not action:
                    obs = "解析失败：需要 <action> 与 <action_input>（单行 JSON），或 <final_answer>。"
                    history_xml = self._history_append(history_xml, step + 1, raw, obs)
                    trace[-1]["observation"] = obs
                    yield {
                        "event": "tool_end",
                        "name": None,
                        "ok": False,
                        "preview": obs[:200],
                    }
                    continue

                if (
                        action.strip().lower().replace(" ", "_") == "get_database_schema"
                        and payload is None
                ):
                    payload = {}

                if payload is None:
                    obs = "解析失败：<action_input> 须为合法 JSON。"
                    history_xml = self._history_append(history_xml, step + 1, raw, obs)
                    trace[-1]["observation"] = obs
                    yield {
                        "event": "tool_end",
                        "name": action,
                        "ok": False,
                        "preview": obs[:200],
                    }
                    continue

                trace[-1]["action"] = action
                trace[-1]["action_input"] = payload
                yield {"event": "tool_start", "name": action}
                observation = await dispatcher.run(action, payload)
                trace[-1]["observation"] = observation[:800]
                history_xml = self._history_append(history_xml, step + 1, raw, observation)
                an = action.strip().lower().replace(" ", "_")
                if an == "execute_sql" and isinstance(payload, dict):
                    sql_q = str(payload.get("sql") or "")
                    batch = extract_react_document_sources_from_sql(observation, sql_q)
                    if batch:
                        last_react_doc_sources = batch
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
            human = self._session_xml(task, history_xml, inst)
            raw = ""
            yield {"event": "turn_start", "step": "final"}
            async for ev in self._iter_llm_turn_stream(llm, system_prompt, human):
                if ev.get("event") == "llm_turn_done":
                    raw = ev.get("raw") or ""
                else:
                    yield ev
            trace.append({"step": "final", "raw": raw})
            inner = XmlStepParser.step_inner(raw)
            final = (
                    XmlStepParser.parse_final_answer(inner)
                    or "抱歉，推理步数已用尽，请缩小问题范围后重试。"
            )
            meta_finish["final_answer"] = final
            meta_finish["react_steps"] = len(trace)
            meta_finish["sources"] = last_react_doc_sources
            yield {"event": "done", "meta": meta_finish}

        except Exception as e:
            traceback.print_exc()
            yield {"event": "error", "message": str(e)}
            yield {"event": "done", "meta": {"error": str(e), "agent_used": False}}
        finally:
            if pool is not None:
                await pool.close()

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


# ---------------------------------------------------------------------------
# 工具分发与注册表
# ---------------------------------------------------------------------------


class ActionDispatcher:
    def __init__(self, registry: Dict[str, ToolFn], sql_ctx: SqlToolContext) -> None:
        self._registry = registry
        self._sql_ctx = sql_ctx

    async def run(self, action_name: str, payload: Optional[Dict[str, Any]]) -> str:
        name = (action_name or "").strip()
        fn = self._registry.get(name)
        if not fn:
            return f"未知工具「{name}」。已注册: {', '.join(sorted(self._registry.keys()))}"
        args = {**(payload or {}), "_tool_context": self._sql_ctx}
        try:
            return await fn(**args)
        except TypeError as e:
            return f"工具参数不匹配 {name}: {e!s}"
        except Exception:
            traceback.print_exc()
            return f"工具执行异常 {name}"


def load_tools_from_directory(dir_path: Union[str, Path]) -> Dict[str, ToolFn]:
    out: Dict[str, ToolFn] = {}
    p = Path(dir_path)
    if not p.is_dir():
        return out
    for fp in sorted(p.glob("*.py")):
        if fp.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(fp.stem, fp)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            traceback.print_exc()
            continue
        tools = getattr(mod, "REACT_TOOLS", None)
        if isinstance(tools, dict):
            for name, fn in tools.items():
                if callable(fn):
                    out[str(name)] = fn  # type: ignore[assignment]
    return out


def build_tool_registry(
        sql_ctx: SqlToolContext,
        extra: Optional[Dict[str, ToolFn]] = None,
        plugin_dirs: Optional[List[Union[str, Path]]] = None,
) -> Dict[str, ToolFn]:
    async def _schema(**kw: Any) -> str:
        return await builtin_get_database_schema(sql_ctx, **kw)

    async def _sql(**kw: Any) -> str:
        return await builtin_execute_sql(sql_ctx, **kw)

    reg: Dict[str, ToolFn] = {
        "get_database_schema": _schema,
        "execute_sql": _sql,
    }
    if extra:
        reg.update(extra)
    if plugin_dirs:
        for d in plugin_dirs:
            reg.update(load_tools_from_directory(d))
    return reg


# ---------------------------------------------------------------------------
# 数据库上下文与内置工具（execute_sql → SQL 校验）
# ---------------------------------------------------------------------------


class SqlToolContext:
    def __init__(self, pool: asyncpg.Pool, cfg: ReactAgentConfig) -> None:
        self.pool = pool
        self.cfg = cfg
        self.extra: Dict[str, Any] = {}


def _normalize_pg_dsn(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


def _strip_sql_string_literals(sql: str) -> str:
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def _is_sensitive_column_name(name: str) -> bool:
    n = name.lower().strip().strip('"').strip("'")
    exact = frozenset(
        {
            "password",
            "passwd",
            "pwd",
            "salt",
            "secret",
            "api_key",
            "access_token",
            "refresh_token",
            "private_key",
            "credential",
            "credentials",
            "hashed_password",
            "password_hash",
            "pass_hash",
            "secret_key",
            "auth_token",
            "jwt",
            "token",
        }
    )
    if n in exact:
        return True
    for frag in (
            "password",
            "passwd",
            "secret_key",
            "api_key",
            "_token",
            "private_key",
            "credential",
            "pass_hash",
    ):
        if frag in n:
            return True
    return False


def _sql_mentions_sensitive_identifier(sql: str) -> Optional[str]:
    """去掉字符串字面量后，若仍出现敏感标识符则拒绝执行。"""
    body = _strip_sql_string_literals(sql).lower()
    patterns = (
        r"\bpassword\b",
        r"\bpasswd\b",
        r"\bhashed_password\b",
        r"\bpassword_hash\b",
        r"\bpass_hash\b",
        r"\bsecret_key\b",
        r"\bapi_key\b",
        r"\baccess_token\b",
        r"\brefresh_token\b",
        r"\bprivate_key\b",
        r"\bauth_token\b",
        r"\bcredentials?\b",
        r"\.password\b",
        r"\.passwd\b",
    )
    for pat in patterns:
        if re.search(pat, body):
            return (
                "该 SQL 涉及敏感字段（password/token/密钥等），已禁止执行。"
                "请向用户说明：无法提供密码或凭据，可引导其使用「忘记密码」或联系管理员重置。"
            )
    return None


def _validate_execute_sql(sql: str, cfg: ReactAgentConfig) -> Optional[str]:
    s = sql.strip()
    if not s:
        return "SQL 为空"
    lines = []
    for line in s.splitlines():
        c = line.split("--")[0].strip()
        if c:
            lines.append(c)
    s = " ".join(lines).strip()
    if not s:
        return "SQL 无有效内容"
    if ";" in s.rstrip(";"):
        return "禁止多语句，请只写一条 SQL"
    s_one = s.rstrip().rstrip(";")
    up = s_one.upper()

    if cfg.sql_readonly:
        if not (up.startswith("SELECT") or up.startswith("WITH")):
            return "只读模式下仅允许 SELECT 或 WITH 查询"
        forbidden = (
            "INSERT ",
            "UPDATE ",
            "DELETE ",
            "DROP ",
            "CREATE ",
            "ALTER ",
            "TRUNCATE ",
            "GRANT ",
            "REVOKE ",
            "COPY ",
            "EXECUTE ",
            "CALL ",
        )
        u2 = " " + up + " "
        for w in forbidden:
            if w in u2:
                return f"禁止关键字: {w.strip()}"

    if cfg.sql_redact_sensitive:
        no_lit = _strip_sql_string_literals(s_one).upper()
        if re.search(r"\bSELECT\b\s+(?:DISTINCT\s+)?\*\s+FROM\b", no_lit):
            return (
                "禁止使用 SELECT *（无法对敏感列脱敏），请只列出允许展示的非敏感列名。"
            )
        sens = _sql_mentions_sensitive_identifier(s_one)
        if sens:
            return sens

    return None


def _sql_cell_str(v: Any) -> str:
    if v is None:
        return "NULL"
    s = str(v)
    return s.replace("\t", " ").replace("\n", " ")[:500]


async def builtin_get_database_schema(ctx: SqlToolContext, **_kw: Any) -> str:
    q = """
        SELECT table_name, column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position; \
        """
    async with ctx.pool.acquire() as conn:
        rows = await conn.fetch(q)
    if not rows:
        return "未查到 public schema 下的表结构（可能为空库或无权访问 information_schema）。"
    lines: List[str] = []
    cur_table = ""
    redact = ctx.cfg.sql_redact_sensitive
    for r in rows:
        t, c, dt, nul = r["table_name"], r["column_name"], r["data_type"], r["is_nullable"]
        if redact and _is_sensitive_column_name(c):
            continue
        if t != cur_table:
            cur_table = t
            lines.append(f"\n表 {t}:")
        lines.append(f"  - {c}  {dt}  nullable={nul}")
    text = "\n".join(lines)
    if len(text) > 12000:
        return text[:12000] + "\n...(已截断)"
    return text


async def builtin_execute_sql(ctx: SqlToolContext, **kw: Any) -> str:
    sql = (kw.get("sql") or "").strip()
    err = _validate_execute_sql(sql, ctx.cfg)
    if err:
        return f"SQL 校验失败: {err}"
    try:
        async with ctx.pool.acquire() as conn:
            await conn.execute(f"SET statement_timeout = '{ctx.cfg.sql_statement_timeout_sec}s'")
            rows = await conn.fetch(sql.rstrip(";"))
    except Exception as e:
        return f"执行失败: {e!s}"
    if not rows:
        return "(查询成功，0 行)"
    keys = list(rows[0].keys())
    max_r = ctx.cfg.sql_max_rows
    slice_rows = rows[:max_r]
    redact = ctx.cfg.sql_redact_sensitive

    def cell(k: str, v: Any) -> str:
        if redact and _is_sensitive_column_name(k):
            return REDACT_PLACEHOLDER
        return _sql_cell_str(v)

    out_lines = ["\t".join(keys)]
    for r in slice_rows:
        out_lines.append("\t".join(cell(k, r[k]) for k in keys))
    msg = "\n".join(out_lines)
    if len(rows) > max_r:
        msg += f"\n...(仅显示前 {max_r} 行，共 {len(rows)} 行)"
    if len(msg) > 14000:
        return msg[:14000] + "\n...(结果已截断)"
    return msg


def _sql_targets_document_table(sql: str) -> bool:
    """仅当 SQL 显式查询 document 表时才尝试挂下载，避免 JOIN 其它大表误匹配。"""
    body = _strip_sql_string_literals((sql or "").strip()).lower()
    body = re.sub(r"--[^\n]*", " ", body)
    return bool(
        re.search(r"\bfrom\s+(?:public\.)?(?:\"document\"|document)\b", body)
    ) or bool(
        re.search(r"\bjoin\s+(?:public\.)?(?:\"document\"|document)\b", body)
    )


def extract_react_document_sources_from_sql(
    observation: str, sql: str
) -> List[Dict[str, Any]]:
    """
    从 execute_sql 的 TSV 结果解析可下载文档，供聊天 sources 使用。
    条件：SQL 须针对 document 表；数据行数不超过 REACT_SQL_DOC_MAX_DATA_ROWS；
    最多返回 REACT_SQL_DOC_SOURCE_MAX 条（按出现顺序去重 id）。
    """
    if not _sql_targets_document_table(sql):
        return []
    text = (observation or "").strip()
    if not text or text.startswith(("SQL 校验失败", "执行失败", "(查询成功，0 行)")):
        return []
    lines = [
        ln
        for ln in text.split("\n")
        if ln.strip() and not ln.strip().startswith("...(")
    ]
    if len(lines) < 2:
        return []
    data_lines = lines[1:]
    if len(data_lines) > REACT_SQL_DOC_MAX_DATA_ROWS:
        return []

    header_cells = lines[0].split("\t")
    h = [c.strip().strip('"').lower() for c in header_cells]

    def col(name: str) -> Optional[int]:
        try:
            return h.index(name)
        except ValueError:
            return None

    i_id = col("id")
    i_orig = col("original_filename")
    if i_id is None or i_orig is None:
        return []
    if (
        col("filename") is None
        and col("file_type") is None
        and col("file_path") is None
    ):
        return []

    i_fn = col("filename")
    i_ft = col("file_type")
    out: List[Dict[str, Any]] = []
    seen: set[int] = set()
    for line in data_lines:
        if len(out) >= REACT_SQL_DOC_SOURCE_MAX:
            break
        cells = line.split("\t")
        idxs = [i_id, i_orig]
        if i_fn is not None:
            idxs.append(i_fn)
        if i_ft is not None:
            idxs.append(i_ft)
        need = max(idxs) + 1
        if len(cells) < need:
            continue
        try:
            doc_id = int(str(cells[i_id]).strip())
        except ValueError:
            continue
        if doc_id in seen:
            continue
        orig = cells[i_orig].strip() if i_orig < len(cells) else ""
        if not orig:
            continue
        seen.add(doc_id)
        ft = "pdf"
        if i_ft is not None and i_ft < len(cells):
            ft = (cells[i_ft].strip() or "pdf").lower() or "pdf"
        out.append(
            {
                "document_id": doc_id,
                "document_name": orig,
                "original_filename": orig,
                "file_type": ft,
                "similarity": 1.0,
                "chunk_id": 0,
                "from_sql_react": True,
            }
        )
    return out


# ---------------------------------------------------------------------------
# XML 一步解析（与 LLM 原始输出对接）
# ---------------------------------------------------------------------------


class XmlStepParser:
    @staticmethod
    def strip_fence(text: str) -> str:
        s = text.strip()
        if not s.startswith("```"):
            return s
        s = re.sub(r"^```[a-zA-Z0-9]*\s*\n?", "", s)
        s = re.sub(r"\n?```\s*$", "", s)
        return s.strip()

    @staticmethod
    def extract_tag(text: str, tag: str) -> Optional[str]:
        pat = rf"<{tag}\s*>(.*?)</{tag}\s*>"
        m = re.search(pat, text, flags=re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else None

    @classmethod
    def step_inner(cls, raw: str) -> str:
        raw = cls.strip_fence(raw)
        inner = cls.extract_tag(raw, "step")
        return inner if inner is not None else raw

    @classmethod
    def parse_final_answer(cls, step_inner: str) -> Optional[str]:
        fa = cls.extract_tag(step_inner, "final_answer")
        if not fa or not fa.strip():
            return None
        return xml_esc.unescape(fa.strip()) or None

    @classmethod
    def parse_action(cls, step_inner: str) -> Tuple[Optional[str], Optional[Any]]:
        act = cls.extract_tag(step_inner, "action")
        if not act:
            return None, None
        name = act.strip()
        if re.match(r"(?i)^final_answer$", name):
            return None, None
        raw_j = cls.extract_tag(step_inner, "action_input")
        if raw_j is None:
            return name, None
        try:
            return name, json.loads(raw_j.strip())
        except json.JSONDecodeError:
            return name, None


# ---------------------------------------------------------------------------
# LLM chunk → 标签内增量（供 astream）
# ---------------------------------------------------------------------------


def _lc_text_content(msg: Any) -> str:
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


def _strip_incomplete_close_tag_suffix(tag: str, text: str) -> str:
    """
    流式时 `</tag>` 可能尚未收齐（缺 `>`），正则无法判定结束位，尾部会混入 `</tag` 片段。
    若当前文本以 `</tag` 的任意非空前缀结尾，则从该前缀起截断，避免把闭合标签打进正文增量。
    """
    close = f"</{tag}>"
    if len(text) < 2:
        return text
    for k in range(len(close) - 1, 1, -1):
        suf = close[:k]
        if len(text) >= k and text[-k:].lower() == suf.lower():
            return text[:-k]
    return text


def stream_tag_content_deltas(
        buffer: str, tag: str, emitted_length: int
) -> Tuple[List[str], int, bool]:
    start, end, _ = _tag_bounds(buffer, tag)
    if start is None:
        return [], emitted_length, False
    chunk = buffer[start:] if end is None else buffer[start:end]
    if end is None:
        chunk = _strip_incomplete_close_tag_suffix(tag, chunk)
    if len(chunk) <= emitted_length:
        return [], emitted_length, end is not None
    new_part = chunk[emitted_length:]
    new_len = len(chunk)
    return ([new_part] if new_part else []), new_len, end is not None
