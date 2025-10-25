# 消安云管系统

基于FastAPI的智能设备管理系统，集成RAG智能问答功能。

## ✨ 核心功能

- **设备管理** - 设备信息管理、图片上传、状态跟踪
- **智能问答** - 基于文档的RAG问答系统
- **文档处理** - 支持PDF、Word、Excel等格式的智能解析
- **公告管理** - 系统公告发布和管理
- **用户管理** - 用户注册、登录、权限控制

## 🏗️ 技术栈

- **后端**: FastAPI + Tortoise-ORM + PostgreSQL
- **缓存**: Redis
- **向量数据库**: ChromaDB / Qdrant
- **AI模型**: Sentence Transformers + OpenAI
- **前端**: HTML5 + CSS3 + JavaScript

## 🚀 快速开始

### 1. 环境要求
- Python 3.10+
- PostgreSQL
- Redis

### 2. 安装依赖
```bash
uv sync
```

### 3. 配置环境
编辑 `config.py` 文件，配置数据库连接信息。

### 4. 数据库迁移
```bash
# 初始化Aerich配置
aerich init -t config.TORTOISE_ORM

# 首次迁移（仅第一次执行）
aerich init-db

# 生成迁移文件
aerich migrate

# 更新数据库
aerich upgrade
```

### 5. 启动应用

```bash
# 开发环境
fastapi dev asgi.py

# 生产环境
fastapi run asgi.py

# 使用uvicorn启动
uvicorn asgi:app --reload --host 0.0.0.0 --port 8000

# 启动异步任务
celery -A celery_tasks.app worker -l info --pool=solo
```

### 6. 访问系统
- **管理后台**: http://localhost:8000
- **API文档**: http://localhost:8000/docs

## 📖 使用指南

### 设备管理
1. 登录系统后进入设备管理
2. 添加设备信息（名称、地址、状态等）
3. 上传设备图片
4. 查看和管理设备列表

### 智能问答
1. 上传文档（PDF、Word、Excel等）
2. 等待文档处理完成
3. 进入智能问答页面
4. 基于文档内容进行问答

### 公告管理
1. 创建公告（标题、内容、发布时间）
2. 发布公告
3. 管理公告状态（草稿、已发布、已归档）

## 🔧 主要API

### 认证
- `POST /api/v1/auth/login` - 用户登录
- `GET /api/v1/auth/info` - 获取用户信息

### 设备管理
- `GET /api/v1/device/list` - 设备列表
- `POST /api/v1/device/create` - 创建设备
- `PUT /api/v1/device/{id}` - 更新设备
- `DELETE /api/v1/device/{id}` - 删除设备

### 文档管理
- `POST /api/v1/documents/upload` - 上传文档
- `GET /api/v1/documents/list` - 文档列表
- `GET /api/v1/documents/{id}/download` - 下载文档

### 智能问答
- `POST /api/v1/chat/sessions` - 创建会话
- `POST /api/v1/chat/sessions/{id}/ask` - 智能问答
- `GET /api/v1/chat/search` - 搜索文档

### 公告管理
- `GET /api/v1/announcement/list` - 公告列表
- `POST /api/v1/announcement/create` - 创建公告
- `PUT /api/v1/announcement/{id}` - 更新公告
- `POST /api/v1/announcement/{id}/publish` - 发布公告

## ⚙️ 配置说明

### 数据库配置
```python
# PostgreSQL
POSTGRES_HOST = "localhost"
POSTGRES_PORT = 15432
POSTGRES_USER = "postgres"
POSTGRES_PASSWORD = "your_password"
POSTGRES_DB = "fire_ops"

# Redis
REDIS_HOST = "localhost"
REDIS_PORT = 16379
```

### 向量数据库配置
```python
# ChromaDB (默认)
VECTOR_DB_TYPE = "chroma"

# Qdrant
VECTOR_DB_TYPE = "qdrant"
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
```

### AI模型配置
```python
# 嵌入模型
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"

# OpenAI配置
OPENAI_API_KEY = "your_key"
OPENAI_BASE_URL = "https://api.zhizengzeng.com/v1/"
```

## 🐛 故障排除

### 常见问题
1. **数据库连接失败** - 检查PostgreSQL服务状态
2. **Redis连接失败** - 检查Redis服务状态
3. **文档处理失败** - 检查文件格式和大小
4. **向量搜索不准确** - 调整相似度阈值

### 日志查看
```bash
# 查看应用日志
tail -f logs/app.log

# 查看Celery任务日志
tail -f logs/celery.log
```

## 📈 性能优化

- 为向量字段创建索引
- 配置Redis缓存
- 优化文档分块大小
- 使用更高效的向量数据库

## 🔮 未来规划

- [ ] 集成更多LLM模型
- [ ] 支持更多文档格式
- [ ] 添加文档分类功能
- [ ] 实现文档版本管理
- [ ] 添加多语言支持

---

**注意**: 这是一个集成了设备管理、RAG智能问答、OCR识别和多种向量数据库支持的完整系统。