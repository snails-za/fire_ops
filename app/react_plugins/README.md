# ReAct 插件说明（`REACT_PLUGINS_DIR`）

本目录用于给 `ReactAgent` 注入可扩展工具、补充系统提示、以及跨插件共享状态。

Agent 会扫描目录下所有 `*.py` 文件（排除 `_` 前缀和 `__init__.py`），并按文件名排序依次加载。

## 插件导出约定

每个插件模块可导出以下变量：

- `REACT_TOOLS`（必选，若要提供工具）
  - 类型：`dict[str, Callable]`
  - 约定：异步函数，签名建议 `async def tool(**kwargs) -> str`
  - 运行时会注入 `_tool_context`（`SqlToolContext`），可用于访问数据库连接池与 `extra` 容器。

- `REACT_SYSTEM_PROMPT_APPEND`（可选）
  - 类型：`str`
  - 用途：拼接到 Agent 默认系统提示后，用于约束工具调用策略与回答风格。

- `REACT_PLUGIN_STATE`（可选）
  - 类型：`dict[str, Any]`
  - 用途：插件向核心声明“状态约定”。
  - 合并规则：按加载顺序 `update`，同 key 后加载覆盖先加载。

## 与核心的通用约定：`meta["sources"]`

核心支持一个通用状态键：`meta_sources_extra_key`  
（常量：`apps.utils.react_agent.PLUGIN_STATE_META_SOURCES_EXTRA_KEY`）。

当 `REACT_PLUGIN_STATE` 中设置：

```python
REACT_PLUGIN_STATE = {
    PLUGIN_STATE_META_SOURCES_EXTRA_KEY: "_react_sources",
}
```

则每轮工具执行后，Agent 会尝试读取 `sql_ctx.extra["_react_sources"]`（需为 `list`）并同步到本轮 `meta["sources"]`。  
这使 SSE 下游（Web/移动端）可以统一展示“证据来源/可下载文档”。

## 推荐实践

- 多个插件共享同一个 `sources` 桶（例如 `_react_sources`），避免来源被互相覆盖。
- 工具返回字符串尽量简洁，保留必要结构信息（如 `document_id`、`chunk_id`、相似度）。
- 当无结果时，明确返回“未命中”，不要伪造 Observation。
- `REACT_SYSTEM_PROMPT_APPEND` 中写清何时优先调用哪个工具（如解释类问题先向量检索）。

## 最小模板

```python
from apps.utils.react_agent import PLUGIN_STATE_META_SOURCES_EXTRA_KEY

REACT_PLUGIN_STATE = {
    PLUGIN_STATE_META_SOURCES_EXTRA_KEY: "_react_sources",
}

REACT_SYSTEM_PROMPT_APPEND = "当问题需要文档证据时优先调用 my_search_tool。"

async def my_search_tool(**kw):
    ctx = kw.get("_tool_context")
    query = (kw.get("query") or "").strip()
    if not query:
        return "缺少 query。"
    # ... 执行检索
    ctx.extra["_react_sources"] = [
        {
            "document_id": 1,
            "chunk_id": 10,
            "document_name": "示例文档",
            "content_preview": "片段预览",
            "similarity": 0.92,
        }
    ]
    return "已检索到 1 条文档片段。"

REACT_TOOLS = {
    "my_search_tool": my_search_tool,
}
```

## 当前示例插件

- `vector_document_search.py`：向量检索文档片段并写入 `sources`。
- `chat_document_download.py`：注册可下载文档来源并写入 `sources`。
