# fire_ops（消安云管）

一个以 **FastAPI** 为核心的消防/设备运营平台，集成：

- 设备、事件、公告、用户等业务管理
- 文档上传、解析、向量检索（Chroma / Qdrant）
- 流式智能问答（SSE）：`ReAct + SQL + 文档检索插件`

---

## 1. 项目结构（仓库级）

```text
fire_ops/
├─ app/        # 后端应用主目录（FastAPI + Tortoise + Celery + RAG）
├─ conf/       # 运行/部署配置（按环境维护）
└─ docker/     # 容器化相关文件
```

后端代码与文档主要在 `app/`。

---

## 2. 核心能力

- **业务管理**：设备、事件、公告、用户与权限
- **文档知识库**：上传后分块入库并写入向量库
- **智能问答（流式）**：
  - ReAct 循环（function calling）
  - SQL 工具（库结构查看、只读查询）
  - 可插拔工具（如向量检索、文档下载来源注册）
- **统一来源输出**：问答结束输出 `meta["sources"]`，便于 Web/移动端展示证据和下载入口

---

## 3. 技术栈

- **Python**: 3.10 ~ 3.12（`>=3.10,<3.13`）
- **Web**: FastAPI, Uvicorn, Gunicorn
- **ORM**: Tortoise ORM + Aerich
- **数据库**: PostgreSQL
- **缓存/队列**: Redis + Celery
- **RAG/LLM**: LangChain, langchain-openai, sentence-transformers
- **向量库**: Chroma / Qdrant（默认 Qdrant）
- **OCR/文档解析**: EasyOCR, PyMuPDF, unstructured 等

---

## 4. 快速启动（本地开发）

以下命令在 `app/` 目录执行。

### 4.1 安装依赖

```bash
cd app
uv sync
```

### 4.2 配置环境变量

项目使用 `starlette.config.Config()` 读取环境变量。  
优先建议在运行环境中设置变量，不要直接提交敏感值到仓库。

常用变量示例：

```bash
export POSTGRES_HOST=localhost
export POSTGRES_PORT=15432
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=your_password
export POSTGRES_DB=fire_ops

export REDIS_HOST=localhost
export REDIS_PORT=16379

export OPENAI_API_KEY=your_api_key
export OPENAI_BASE_URL=https://api.openai.com/v1/

export VECTOR_DB_TYPE=qdrant
export QDRANT_HOST=localhost
export QDRANT_PORT=16333
export QDRANT_COLLECTION_NAME=documents

# 工具在 import mcp_tools.tools 时注册；问答需配置 DATABASE_URL（SQL 插件懒加载连接池）
```

### 4.3 初始化/迁移数据库

```bash
cd app
# 1) 模型有变更时，先生成迁移文件
aerich migrate

# 2) 应用迁移到数据库
aerich upgrade
```

若是首次接入空库，可按需执行：

```bash
cd app
aerich init -t config.TORTOISE_ORM
aerich init-db
```

说明：

- 日常开发最常用的是 `aerich migrate && aerich upgrade`
- 仅当首次初始化项目时才需要 `init / init-db`

### 4.4 启动服务

```bash
cd app
uvicorn asgi:app --reload --host 0.0.0.0 --port 8000
```

可选：启动 Celery worker（文档处理等异步任务）

```bash
cd app
celery -A celery_tasks.app worker -l info --pool=solo
```

### 4.5 访问入口

- API 文档：`http://localhost:8000/docs`
- 管理页面：`http://localhost:8000/static/admin.html`

---

## 5. 智能问答（ReAct）说明

### 5.1 流式问答接口

- `POST /api/v1/chat/ask/stream`
- 鉴权：需要登录
- 请求：`multipart/form-data`，字段 `question`
- 响应：SSE（`text/event-stream`）

SSE 事件类型（`data` 的 `type`）：

- `thought`：推理过程（累积）
- `content`：回答正文（累积）
- `action`：工具调用提示
- `error`：错误信息
- `sources`：来源列表（证据/下载信息）
- `done`：本轮结束

### 5.2 ReAct 工具与插件

内置工具：

- `get_database_schema`
- `execute_sql`（只读校验）

插件工具（`import mcp_tools.tools` 注册到 `plugin_mcp`）：

- 例如 `search_uploaded_documents`（向量检索）
- 例如 `register_chat_document_sources`（注册下载来源）

来源聚合：文档/下载类工具写入 `chat_extra()[SOURCES_EXTRA_KEY]`（`mcp_tools.mcp_bridge`），Agent 同步到 `meta["sources"]`。

数据库访问（连接池、SQL 方言、换库）集中在 `mcp_tools` 插件内实现；`react_agent` 只负责 LLM 与工具调用协议，换数据库或复用到其他项目时核心推理逻辑可保持不变。

---

## 6. 常用 API（节选）

- 认证
  - `POST /api/v1/auth/login`
  - `GET /api/v1/auth/info`
- 文档
  - `POST /api/v1/documents/upload`
  - `GET /api/v1/documents/list`
  - `GET /api/v1/documents/{document_id}/download`
- 聊天
  - `POST /api/v1/chat/ask/stream`
  - `GET /api/v1/chat/search`
  - `POST /api/v1/chat/analyze`

以 `/docs` 实际暴露为准。

---

## 7. 生产部署建议

- 使用 Gunicorn + Uvicorn worker 承载 API
- Redis 与 PostgreSQL 独立部署并启用监控
- 向量库（Qdrant/Chroma）持久化卷独立管理
- 将 `OPENAI_API_KEY`、数据库密码等放入密钥管理系统
- 为 `mcp_tools/tools/` 变更建立审核（插件即执行代码）

---

## 8. 常见问题

- **问：SSE 没有返回 `sources`？**  
  确认插件是否写入 `chat_extra()[SOURCES_EXTRA_KEY]`，以及模型是否调用了对应工具。

- **问：向量检索效果不稳定？**  
  调整 `SIMILARITY_THRESHOLD`、分块策略（`CHUNK_SIZE/CHUNK_OVERLAP`）、以及检索 `top_k`。

- **问：数据库迁移报错？**  
  先确认连接参数与权限，再执行 `aerich upgrade`；跨版本变更建议在测试库先验证。

---

## 9. 代码与文档入口

- 后端入口：`app/asgi.py`
- 全局配置：`app/config.py`
- ReAct 核心：`app/apps/utils/react_agent.py`
- SSE 转换：`app/apps/utils/react_sse.py`
- MCP 与 LangChain 衔接：`app/mcp_tools/mcp_bridge.py`；SQL 插件：`app/mcp_tools/sql_plugin.py`
- 工具实现：`app/mcp_tools/tools/`（`tools/__init__.py` 注册到 `plugin_mcp`）

