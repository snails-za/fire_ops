# fire_ops

消安云管后端服务，基于 FastAPI 构建，负责账号认证、用户管理、设备管理、公告管理、文档解析、向量检索和智能问答。

新的 Web 后台已经拆分到 `fire-admin`。本项目中的 `static/*.html` 是旧版静态后台页面，暂时保留用于对照接口和历史逻辑，不再作为新后台的主要维护入口。

## 项目关系

```text
code/
├─ fire_ops/        # 后端服务，本项目
├─ fire-admin/      # Vue Web 后台管理端
└─ fire-equipment/  # UniApp 移动端前台
```

## 技术栈

- Python 3.10 到 3.12
- FastAPI
- Uvicorn / Gunicorn
- Tortoise ORM
- Aerich
- PostgreSQL
- Redis
- Celery
- LangChain / langchain-openai
- Qdrant 或 Chroma
- sentence-transformers
- PyMuPDF / unstructured / EasyOCR

## 功能范围

- 认证
  - 用户登录、后台登录、验证码、退出登录、Token 刷新
- 用户
  - 用户列表、详情、新增、编辑、删除、联系人和好友申请
- 设备
  - 设备列表、统计、详情、新增、编辑、删除、图片上传
- 公告
  - 公告列表、公开公告、详情、新增、编辑、发布、归档、删除
- 文档
  - 文档上传、解析、分块、向量化、下载、重新解析、删除、统计
- 智能问答
  - SSE 流式问答
  - ReAct 工具调用
  - SQL 查询工具
  - 文档检索工具
  - 会话存储和短期上下文记忆
- 公共能力
  - 健康检查
  - 系统资源监控

## 目录结构

```text
fire_ops/app/
├─ apps/
│  ├─ api/                 # FastAPI 路由
│  │  ├─ announcement/     # 公告接口
│  │  ├─ chat/             # 智能问答和会话接口
│  │  ├─ device/           # 设备接口
│  │  ├─ documents/        # 文档接口
│  │  ├─ event/            # 事件接口
│  │  └─ users/            # 认证、用户、联系人接口
│  ├─ dependencies/        # 鉴权依赖
│  ├─ form/                # 请求表单模型
│  ├─ models/              # 数据模型
│  └─ utils/               # 业务工具、RAG、Agent、MCP 工具
├─ celery_tasks/           # Celery 配置和异步任务
├─ data/                   # 上传文件和运行数据，通常不提交
├─ migrations/             # Aerich 迁移文件
├─ models/                 # 本地模型缓存，通常不提交
├─ static/                 # 旧版 HTML 后台页面
├─ asgi.py                 # FastAPI 应用入口
├─ config.py               # 全局配置
├─ pyproject.toml
└─ uv.lock
```

## 本地启动

以下命令在 `fire_ops/app` 目录执行。

### 1. 安装依赖

```bash
cd fire_ops/app
uv sync
```

如果没有安装 `uv`，先安装 `uv`，或按团队环境使用等价的 Python 虚拟环境管理方式。

### 2. 配置环境变量

项目通过 `starlette.config.Config()` 读取环境变量。常用配置如下：

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
export OPENAI_BASE_URL=https://api.openai.com/v1/

export VECTOR_DB_TYPE=qdrant
export QDRANT_HOST=localhost
export QDRANT_PORT=16333
export QDRANT_COLLECTION_NAME=documents
```

敏感信息不要提交到仓库。

### 3. 初始化或迁移数据库

首次初始化：

```bash
cd fire_ops/app
aerich init -t config.TORTOISE_ORM
aerich init-db
```

日常模型变更：

```bash
cd fire_ops/app
aerich migrate
aerich upgrade
```

### 4. 启动 API

```bash
cd fire_ops/app
uvicorn asgi:app --reload --host 0.0.0.0 --port 8000
```

访问：

```text
http://127.0.0.1:8000/docs
```

### 5. 启动 Celery Worker

文档解析等异步任务需要 Celery：

```bash
cd fire_ops/app
celery -A celery_tasks.app worker -l info --pool=solo
```

## 前后端入口

- API 文档：`http://127.0.0.1:8000/docs`
- 新后台：启动 `fire-admin` 后访问 `http://127.0.0.1:5174`
- 移动端：使用 HBuilderX 打开 `fire-equipment`
- 旧后台静态页：`http://127.0.0.1:8000/static/admin.html`

旧后台仅保留，不建议继续新增复杂交互。

## 认证和 Token

后端使用 JWT + Redis 存储登录态。

关键入口：

- 登录：`/api/v1/auth/login`、`/api/v1/auth/admin/login`
- 当前用户：`/api/v1/auth/info`
- Token 刷新：`/api/v1/auth/refresh_token`

Token 机制说明：

- access token 默认有效期由 `MAX_AGE` 控制，当前为 1 小时。
- Redis 中还有一个短刷新窗口，由 `REFRESH_MAX_AGE` 控制。
- 受保护接口可能返回 `403` 表示需要刷新 Token。
- 前端收到 `403` 后应调用 `/api/v1/auth/refresh_token`，成功后重试原请求。

`fire-admin` 和 `fire-equipment` 都应走各自统一的请求封装，避免重复实现 Token 逻辑。

## 智能问答和会话记忆

核心入口：

```text
POST /api/v1/chat/ask/stream
字段：question、session_id
```

该接口返回 SSE 流。新会话会先返回 `session` 事件，回答过程中返回推理、工具调用、正文、来源和完成事件。

主要事件类型：

- `session`：当前会话信息，新会话会在开始时返回
- `thought`：模型推理过程
- `action`：工具调用
- `content`：回答正文
- `sources`：相关文档来源
- `error`：错误信息
- `done`：本轮结束

会话管理保留三个关键入口：

- `POST /api/v1/chat/sessions`
- `GET /api/v1/chat/sessions`
- `GET /api/v1/chat/sessions/{session_id}/messages`

会话逻辑：

- 不传 `session_id` 时自动创建会话。
- 会话标题由首个问题生成，过长会截断。
- 每轮问答会保存用户问题、助手回答和元数据。
- 后续同一会话会加载最近若干条消息作为短期上下文。

相关代码：

- `apps/api/chat/chat.py`
- `apps/utils/chat_session.py`
- `apps/utils/react_agent.py`
- `apps/utils/react_sse.py`

## 文档解析和向量检索

文档能力包括上传、解析、分块、向量化、检索和下载。

文档解析任务依赖 Celery Worker。向量检索根据配置使用 Qdrant 或 Chroma。具体接口以 `/docs` 实际暴露为准，前后台只需要通过统一 API 封装调用，不建议在 README 中维护接口清单。

## 数据和模型文件

以下内容通常不应该提交：

- `data/`
- `models/`
- `.venv/`
- `.ruff_cache/`
- `__pycache__/`
- 大模型权重、向量库数据、上传文件

如果本地模型过大，建议放在独立模型目录，通过环境变量或配置指向，不要直接提交到 Git。

## 开发约定

- 新增接口放在 `apps/api/<module>/`，并在 API 初始化处注册路由。
- 请求参数模型放在 `apps/form/`。
- 数据模型放在 `apps/models/`，变更后生成 Aerich 迁移。
- 通用业务逻辑放在 `apps/utils/`，不要堆在路由函数里。
- 智能问答工具调用相关逻辑集中在 `apps/utils/mcp_tools/` 和 `react_agent.py`。
- 旧版静态 HTML 不再承接新后台复杂需求，新后台改 `fire-admin`。

## 排查问题

### 登录后很快失效

这是后端刷新机制触发。前端收到 `403` 后需要调用 `/api/v1/auth/refresh_token` 并重试原请求。

### 文档上传后一直处理中

检查 Celery Worker 是否启动，Redis 是否可用，文档解析日志是否报错。

### 问答没有历史上下文

确认请求是否传入正确 `session_id`，并检查 `ChatSession`、`ChatMessage` 表是否正常写入。

### 向量检索没有结果

检查文档是否解析完成、向量库是否启动、集合名是否一致、嵌入模型是否可用。
