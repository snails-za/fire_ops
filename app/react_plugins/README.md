# ReAct 插件目录（`REACT_PLUGINS_DIR`）

每个 `*.py`（不含 `_` 前缀、`__init__.py`）可导出：

- **`REACT_TOOLS`**: `dict[str, Callable]`，异步工具函数，签名为 `(**kwargs) -> str`，其中会注入 `_tool_context`（`SqlToolContext`）。
- **`REACT_SYSTEM_PROMPT_APPEND`**（可选）: 字符串，会拼到默认系统提示后。
- **`REACT_PLUGIN_STATE`**（可选）: `dict`，会按目录、按文件顺序 **merge** 进 `sql_ctx.plugin_state`（同 key 后加载覆盖先加载）；多个 `plugin_dirs` 时按目录顺序继续 `update`。

### 与 Agent 核心的约定（可选）

若 `sql_ctx.plugin_state` 中含有键 **`meta_sources_extra_key`**（与 `apps.utils.react_agent.PLUGIN_STATE_META_SOURCES_EXTRA_KEY` 相同），值为 **字符串**，则每轮工具执行后 Agent 会从 `sql_ctx.extra[该字符串]` 读取 **list**（若有），用于更新本轮结束时的 `meta["sources"]`（SSE 聊天下游可用）。其它业务可自行约定更多 `REACT_PLUGIN_STATE` 键并在工具里读写 `sql_ctx.extra` / 扩展消费逻辑。

示例见 `chat_document_download.py`。
