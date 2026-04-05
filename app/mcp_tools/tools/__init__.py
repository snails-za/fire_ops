# -*- coding: utf-8 -*-
from mcp_tools.mcp_bridge import plugin_mcp

from . import builtin_sql
from . import chat_document_download
from . import vector_document_search

_MODS = (builtin_sql, vector_document_search, chat_document_download)


def _register_all() -> None:
    builtin_sql.register_sql_tools(plugin_mcp)
    vector_document_search.register_vector_tools(plugin_mcp)
    chat_document_download.register_chat_doc_tools(plugin_mcp)


_register_all()


def collect_tool_prompts() -> str:
    parts: list[str] = []
    for mod in _MODS:
        frag = getattr(mod, "TOOL_PROMPT_APPEND", None)
        if isinstance(frag, str) and frag.strip():
            parts.append("\n\n" + frag.strip())
    return "".join(parts)

TOOL_PROMPTS = collect_tool_prompts()