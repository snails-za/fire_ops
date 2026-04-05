# -*- coding: utf-8 -*-
"""SQL 插件：连接池（DATABASE_URL）与只读查询实现。"""
import asyncio
import os
import re
from dataclasses import dataclass
from typing import Any, List, Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None
_pool_lock = asyncio.Lock()

REDACT_PLACEHOLDER = "[已隐藏·敏感字段]"


def normalize_pg_dsn(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


def _resolve_database_url() -> str:
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if url:
        return url
    try:
        from config import DATABASE_URL as cfg_dsn

        return (cfg_dsn or "").strip()
    except ImportError:
        return ""


async def get_sql_pool() -> asyncpg.Pool:
    global _pool
    async with _pool_lock:
        if _pool is None:
            url = _resolve_database_url()
            if not url:
                raise RuntimeError(
                    "缺少数据库连接：请设置环境变量 DATABASE_URL，或在 .env 中配置 POSTGRES_*（见 config.py）。"
                )
            _pool = await asyncpg.create_pool(
                dsn=normalize_pg_dsn(url),
                min_size=1,
                max_size=3,
                statement_cache_size=0,
            )
        return _pool


@dataclass
class SqlToolConfig:
    readonly: bool = True
    max_rows: int = 500
    statement_timeout_sec: int = 30
    redact_sensitive: bool = True


class SqlToolContext:
    __slots__ = ("pool", "cfg")

    def __init__(self, pool: asyncpg.Pool, cfg: SqlToolConfig) -> None:
        self.pool = pool
        self.cfg = cfg


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


def _validate_execute_sql(sql: str, cfg: SqlToolConfig) -> Optional[str]:
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

    if cfg.readonly:
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

    if cfg.redact_sensitive:
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
    redact = ctx.cfg.redact_sensitive
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
            await conn.execute(
                f"SET statement_timeout = '{ctx.cfg.statement_timeout_sec}s'"
            )
            rows = await conn.fetch(sql.rstrip(";"))
    except Exception as e:
        return f"执行失败: {e!s}"
    if not rows:
        return "(查询成功，0 行)"
    keys = list(rows[0].keys())
    max_r = ctx.cfg.max_rows
    slice_rows = rows[:max_r]
    redact = ctx.cfg.redact_sensitive

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
