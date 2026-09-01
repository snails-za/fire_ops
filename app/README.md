# fire_ops 后端服务

`fire_ops/app` 是消安云管系统的后端服务，基于 FastAPI 构建，负责用户认证、后台管理、设备事件、好友通讯、公告、文档解析、向量检索和智能问答。

新的 Web 后台在同级项目 `fire-admin` 中维护；本项目 `static/` 仅保留 API 文档等后端静态资源。

## 项目位置

```text
code/
├── fire_ops/        # 后端服务，本 README 所在项目
├── fire-admin/      # Vue Web 后台管理端
└── fire-equipment/  # UniApp 移动端前台
```

## 技术栈

- Python：`>=3.10,<3.13`
- Web：FastAPI、Uvicorn、Gunicorn
- ORM / 迁移：Tortoise ORM、Aerich
- 数据库：PostgreSQL
- 缓存和任务队列：Redis
- 异步任务：Celery
- 文档解析：Document Process（DP，`pipeline` / `hybrid`）
- 向量检索：Qdrant
- 大模型调用：LangChain OpenAI 兼容接口
- 智能问答：XML ReAct + FastMCP 工具

## 当前目录

```text
fire_ops/app/
├── apps/
│   ├── api/                 # FastAPI 路由模块，自动挂载到 /api/v1
│   │   ├── announcement/     # 公告接口
│   │   ├── chat/             # 智能问答与会话管理
│   │   ├── communication/    # 好友一对一通讯
│   │   ├── device/           # 设备接口
│   │   ├── documents/        # 文档上传、解析、下载、预览
│   │   ├── event/            # 事件和事件消息
│   │   ├── users/            # 认证、用户、联系人
│   │   └── common.py         # 健康检查和系统资源
│   ├── dependencies/         # 登录鉴权、角色权限
│   ├── form/                 # 请求参数模型
│   ├── models/               # Tortoise ORM 数据模型
│   └── utils/                # 通用工具、RAG、ReAct、MCP、Redis、Token
├── celery_tasks/             # Celery 实例和文档处理任务
├── data/                     # 运行期数据：上传文件、头像、设备图片
├── docs/                     # 项目说明文档
├── models/                   # 本地离线模型缓存
├── static/                   # 静态资源和历史页面
├── asgi.py                   # FastAPI 应用入口
├── config.py                 # 全局配置
├── pyproject.toml            # Python 项目和依赖配置
└── uv.lock
```

说明：

- `migrations/` 是 Aerich 配置的迁移目录，当前仓库里不一定已经生成。
- `data/`、`models/` 通常包含运行期数据或模型缓存，提交前要确认是否需要纳入版本管理。

## 应用启动流程

入口是 `asgi.py`。

```text
asgi.py
  -> create_app(lifespan=lifespan)
  -> init_static()
  -> init_cors()
  -> init_routes()
  -> Tortoise.init()
  -> ensure_initial_admin()
  -> RedisManager.init()
```

路由注册在 `apps/__init__.py` 中自动完成：扫描 `apps/api` 下的 `.py` 文件，发现模块里有 `router` 就挂载到 `/api/v1`。

## 主要 API 前缀

所有接口默认有 `/api/v1` 前缀。

| 模块 | 前缀 | 文件 |
| --- | --- | --- |
| 用户认证 | `/auth` | `apps/api/users/auth.py` |
| 用户和联系人 | `/admin` | `apps/api/users/admin.py` |
| 设备管理 | `/device` | `apps/api/device/device.py` |
| 事件管理 | `/event` | `apps/api/event/event.py` |
| 公告管理 | `/announcement` | `apps/api/announcement/announcement.py` |
| 好友通讯 | `/direct` | `apps/api/communication/direct.py` |
| 文档管理 | `/documents` | `apps/api/documents/document.py` |
| 智能问答 | `/chat` | `apps/api/chat/chat.py` |
| 公共接口 | `/common` | `apps/api/common.py` |

完整接口以启动后的 `/docs` 为准。

## 本地启动

以下命令在 `fire_ops/app` 目录执行。

### 1. 安装依赖

```bash
uv sync
```

如果没有 `uv`，可按团队环境使用等价虚拟环境方式安装 `pyproject.toml` 中的依赖。

### 2. 配置环境变量

项目使用 `starlette.config.Config()` 读取环境变量。常用配置：

```bash
export POSTGRES_HOST=localhost
export POSTGRES_PORT=15432
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=your_password
export POSTGRES_DB=fire_ops

export REDIS_HOST=localhost
export REDIS_PORT=16379
export REDIS_PASSWORD=
export REDIS_DB=0

export OPENAI_API_KEY=your_api_key
export OPENAI_BASE_URL=https://api.deepseek.com

export VECTOR_DB_TYPE=qdrant
export QDRANT_HOST=localhost
export QDRANT_PORT=16333
export QDRANT_COLLECTION_NAME=documents
```

敏感信息不要提交到仓库。

### 3. 初始化或迁移数据库

首次初始化：

```bash
aerich init -t config.TORTOISE_ORM
aerich init-db
```

日常模型变更：

```bash
aerich migrate
aerich upgrade
```

### 4. 启动 API

```bash
uvicorn asgi:app --reload --host 0.0.0.0 --port 8000
```

访问：

```text
http://127.0.0.1:8000/docs
```

### 5. 启动 Celery Worker

文档解析和向量化依赖 Celery Worker：

```bash
celery -A celery_tasks.app worker -l info --pool=solo
```

## 核心业务链路

### 登录鉴权

```text
前端 Bearer Token
  -> decode_token()
  -> Redis 校验 token
  -> Redis 校验 refresh_token 窗口
  -> 查询 User
```

相关文件：

- `apps/api/users/auth.py`
- `apps/dependencies/auth.py`
- `apps/utils/token_.py`
- `apps/utils/redis_.py`

### 设备和事件

设备状态支持：

```text
告警 / 异常 / 离线 / 正常
```

设备创建或更新为 `告警`、`异常`、`离线` 时，会自动创建或复用未关闭事件，并追加系统消息。设备恢复 `正常` 时，会关闭该设备待处理或处理中的事件。

相关文件：

- `apps/api/device/device.py`
- `apps/api/event/event.py`
- `apps/models/device.py`
- `apps/models/event.py`

### 文档处理

```text
上传文档
  -> 保存原文件
  -> 创建 Document，状态 queued
  -> Celery 后台解析
  -> 写入 Document.content
  -> 拆分 DocumentChunk
  -> 写入向量库
```

相关文件：

- `apps/api/documents/document.py`
- `celery_tasks/task.py`
- `apps/utils/document_parser.py`
- `apps/utils/vector_db_selector.py`

### 智能问答

```text
POST /api/v1/chat/ask/stream
  -> 创建或获取 ChatSession
  -> 加载最近历史消息
  -> ReactAgent 生成 XML step
  -> MCP 工具执行 SQL 或文档检索
  -> SSE 返回 session/thought/action/content/sources/done
  -> 保存 ChatMessage
```

相关文件：

- `apps/api/chat/chat.py`
- `apps/utils/react_agent.py`
- `apps/utils/xml_react.py`
- `apps/utils/react_sse.py`
- `apps/utils/chat_session.py`
- `apps/utils/mcp_tools/`

## 更多文档

详细结构、全局关系图、模型关系、排查入口见：

```text
docs/技术说明文档.md
```

## 常见排查

### 登录后很快失效

这是刷新窗口触发。前端收到 `403` 后需要调用 `/api/v1/auth/refresh_token`，成功后重试原请求。

### 文档上传后一直处理中

检查：

- Celery Worker 是否启动。
- Redis 是否可用。
- PostgreSQL 是否可用。
- Qdrant / Chroma 是否可用。
- `apps/utils/document_parser.py` 是否解析报错。

### 问答没有流式输出

检查：

- `/api/v1/chat/ask/stream` 是否返回 `text/event-stream`。
- LLM 是否输出合法 XML。
- `apps/utils/react_sse.py` 是否发送 `content` 事件。
- 前端是否正确消费 SSE。

### 相关文档不能下载

检查：

- `sources` 中是否包含 `document_id`。
- `/api/v1/documents/{document_id}/download` 是否能访问原文件。
- `data/documents` 下文件是否存在。
