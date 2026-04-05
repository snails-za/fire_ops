# -*- coding: utf-8 -*-
from apps.utils.mcp_tools.mcp_bridge import mcp_chat_host

from .builtin_sql import SqlToolsModule
from .chat_document_download import ChatDocumentToolsModule
from .vector_document_search import VectorSearchToolsModule

_TOOL_MODULES = (
    SqlToolsModule(),
    VectorSearchToolsModule(),
    ChatDocumentToolsModule(),
)


def _register_all() -> None:
    app = mcp_chat_host.app
    for mod in _TOOL_MODULES:
        mod.register(app)


_register_all()


def collect_tool_prompts() -> str:
    parts: list[str] = []
    for mod in _TOOL_MODULES:
        frag = getattr(mod, "TOOL_PROMPT_APPEND", None)
        if isinstance(frag, str) and frag.strip():
            parts.append("\n\n" + frag.strip())
    return "".join(parts)


TOOL_PROMPTS = collect_tool_prompts()
