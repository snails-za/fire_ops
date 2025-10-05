# 消安云管系统 (Fire Operations Management System)

基于FastAPI的智能设备管理系统，集成RAG智能问答功能，支持设备管理和文档智能问答。

## ✨ 功能特性

### 🔧 设备管理
- 设备信息管理（增删改查）
- 设备图片上传
- 设备状态跟踪
- 设备位置管理

### 🤖 RAG智能问答
- **文档上传**: 支持PDF、DOCX、Excel、TXT等多种格式
- **智能解析**: 自动提取文档内容并分块处理
- **向量搜索**: 基于语义相似度的智能检索
- **智能问答**: 基于上传文档的准确回答
- **会话管理**: 多会话支持和历史记录
- **OCR识别**: 支持图片和PDF中的文字识别

### 🗄️ 向量数据库支持
- **ChromaDB**: 轻量级本地向量数据库（默认）
- **Qdrant**: 高性能分布式向量数据库
- **无缝切换**: 通过配置轻松切换数据库类型
- **自动回退**: 连接失败时自动回退到备用数据库

## 🏗️ 技术架构

### 核心技术栈
- **后端框架**: FastAPI 0.115.5
- **数据库**: PostgreSQL
- **ORM**: Tortoise-ORM
- **缓存**: Redis
- **认证**: JWT Token
- **文档处理**: LangChain, PyPDF, python-docx, openpyxl
- **向量化**: Sentence Transformers
- **向量数据库**: ChromaDB / Qdrant
- **OCR引擎**: EasyOCR
- **前端**: HTML5 + CSS3 + JavaScript

### 项目结构
```
fire_ops/app/
├── apps/
│   ├── api/                    # API接口层
│   │   ├── users/             # 用户管理API
│   │   ├── device/            # 设备管理API
│   │   ├── documents/         # 文档管理API
│   │   └── chat/              # 智能问答API
│   ├── models/                # 数据模型层
│   │   ├── user.py           # 用户模型
│   │   ├── device.py         # 设备模型
│   │   └── document.py        # 文档模型
│   ├── utils/                 # 工具类
│   │   ├── rag_helper.py     # RAG工具类
│   │   ├── vector_db_selector.py # 向量数据库选择器
│   │   ├── document_parser.py # 文档解析器
│   │   └── ocr_engines.py    # OCR引擎
│   ├── form/                  # 表单验证
│   └── dependencies/          # 依赖注入
├── static/                    # 静态资源
│   ├── chat.html             # 智能问答页面
│   ├── login.html            # 登录页面
│   ├── upload.html           # 文档上传页面
│   └── css/, js/, images/    # 样式、脚本、图片
├── data/                      # 数据目录
│   ├── documents/            # 文档存储
│   └── vector_db/            # 向量数据库存储
├── celery_tasks/              # 异步任务
├── migrations/                # 数据库迁移
├── models/                    # 预训练模型
├── config.py                 # 配置文件
├── asgi.py                   # ASGI应用入口
└── README.md                 # 项目说明
```

## 🚀 快速开始

### 环境要求
- Python 3.10+
- PostgreSQL
- Redis
- Qdrant (可选，如使用Qdrant向量数据库)

### 1. 安装依赖

#### 使用uv安装（推荐）
```bash
uv sync
```

#### 使用pip安装
```bash
uv sync
```

### 2. 配置环境变量

配置 `conf.py` 文件

```bash
# 数据库配置
POSTGRES_HOST=localhost
POSTGRES_PORT=15432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=fire_ops

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=16379
REDIS_PASSWORD=

# 向量数据库配置
VECTOR_DB_TYPE=chroma  # 可选: chroma, qdrant
QDRANT_HOST=localhost  # Qdrant配置
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=documents

# RAG配置
OPENAI_API_KEY=your_openai_key  # 可选，用于智能问答
OPENAI_BASE_URL=https://api.zhizengzeng.com/v1/
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5  # 中文优化模型
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
SIMILARITY_THRESHOLD=0.6
DEFAULT_TOP_K=5

# 文件处理配置
MAX_FILE_SIZE=52428800  # 50MB
ALLOWED_FILE_TYPES=pdf,docx,doc,xlsx,xls,txt

# OCR配置
OCR_ENABLED=true
OCR_USE_GPU=true  # 是否启用GPU加速

# 安全配置
SECRET_KEY=your_secret_key
AES_KEY=your_aes_key
```


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

#### 开发环境
```bash
fastapi dev asgi.py
```

#### 生产环境
```bash
fastapi run asgi.py
```

#### 使用uvicorn启动
```bash
uvicorn asgi:app --reload --host 0.0.0.0 --port 8000
```

#### 使用gunicorn启动
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker asgi:app
```

### 6. 启动Celery Worker (异步任务)
```bash
启动定时任务
celery -A celery_tasks.app beat -l info
启动worker【单进程】
celery -A celery_tasks.app worker -l info --pool=solo
Windows启动worker【单进程】
celery -A celery_tasks.app worker -l info --pool=solo
```

### 7. 访问系统
- **主页**: http://localhost:8000
- **智能问答**: http://localhost:8000/static/chat.html
- **文档上传**: http://localhost:8000/static/upload.html
- **API文档**: http://localhost:8000/docs
- **登录账号**: admin / 123456

## 📖 使用指南

### 设备管理
1. 登录系统后，使用设备管理API
2. 上传设备图片
3. 添加设备信息（名称、地址、状态等）
4. 查看和管理设备列表

### 文档管理
1. **上传文档**
   - 进入文档上传页面
   - 选择支持的文档格式（PDF、Word、Excel、TXT）
   - 等待文档处理完成
   - 查看文档列表和状态

2. **文档处理流程**
   - 文档解析：提取文本内容
   - OCR识别：识别图片中的文字
   - 文本分块：将长文档分割成小块
   - 向量化：将文本转换为向量
   - 存储：保存到向量数据库

### RAG智能问答
1. **开始问答**
   - 进入智能问答页面
   - 创建新的对话会话
   - 在输入框中输入问题
   - 系统基于上传的文档提供准确答案
   - 查看参考文档和相似度信息

2. **会话管理**
   - 支持多个对话会话
   - 查看历史对话记录
   - 删除不需要的会话

3. **问答模式**
   - **智能模式**：配置OpenAI API后，使用LLM生成结构化回答
   - **简单模式**：基于关键词匹配和文档内容展示

## 🔧 API接口

### 用户认证
- `POST /api/v1/auth/login` - 用户登录
- `GET /api/v1/auth/info` - 获取用户信息
- `GET /api/v1/auth/logout` - 用户登出

### 设备管理
- `GET /api/v1/device/list` - 获取设备列表
- `POST /api/v1/device/create` - 创建设备
- `POST /api/v1/device/upload/image` - 上传设备图片
- `PUT /api/v1/device/{id}` - 更新设备信息
- `DELETE /api/v1/device/{id}` - 删除设备

### 文档管理
- `POST /api/v1/documents/upload` - 上传文档
- `GET /api/v1/documents/list` - 获取文档列表
- `GET /api/v1/documents/{id}` - 获取文档详情
- `DELETE /api/v1/documents/{id}` - 删除文档
- `GET /api/v1/documents/{id}/download` - 下载文档

### 智能问答
- `POST /api/v1/chat/sessions` - 创建聊天会话
- `GET /api/v1/chat/sessions` - 获取会话列表
- `POST /api/v1/chat/sessions/{id}/ask` - 智能问答
- `GET /api/v1/chat/search` - 搜索文档
- `DELETE /api/v1/chat/sessions/{id}` - 删除会话

## ⚙️ 配置详解

### 向量数据库配置

#### ChromaDB (默认)
```python
# 配置参数
VECTOR_DB_TYPE = "chroma"
CHROMA_PERSIST_DIRECTORY = "./data/vector_db/chroma"
CHROMA_COLLECTION = "documents"
```

#### Qdrant
```python
# 配置参数
VECTOR_DB_TYPE = "qdrant"
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
QDRANT_COLLECTION_NAME = "documents"
```

#### 切换向量数据库
```bash
# 切换到Qdrant
export VECTOR_DB_TYPE=qdrant

# 切换回ChromaDB
export VECTOR_DB_TYPE=chroma
```

### 嵌入模型配置
```python
# 中文优化模型（推荐）
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"

# 多语言模型
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# 高精度模型
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
```

### RAG系统配置
```python
# 文本分块配置
CHUNK_SIZE = 1000          # 每个文档块的大小
CHUNK_OVERLAP = 200        # 文档块之间的重叠

# 搜索配置
SIMILARITY_THRESHOLD = 0.6  # 相似度阈值
DEFAULT_TOP_K = 5          # 默认返回结果数量

# OpenAI配置
OPENAI_API_KEY = "your_key"
OPENAI_BASE_URL = "https://api.zhizengzeng.com/v1/"
```

### OCR配置
```python
# OCR功能开关
OCR_ENABLED = True
OCR_USE_GPU = True  # GPU加速
```

## 🔒 安全特性

- **JWT认证**: 基于Token的用户认证
- **权限控制**: 用户级别的数据隔离
- **文件验证**: 文件类型和大小限制
- **数据加密**: 敏感数据加密存储
- **会话管理**: 安全的会话状态管理
- **输入验证**: 严格的输入参数验证
- **SQL注入防护**: 使用ORM防止SQL注入

## 🐛 故障排除

### 常见问题

1. **依赖安装失败**
   ```bash
   # 清理环境重新安装
   uv venv --recreate
   uv sync
   ```

2. **数据库连接失败**
   - 检查PostgreSQL服务状态
   - 验证数据库配置信息
   - 确认数据库用户权限

3. **向量数据库连接失败**
   - ChromaDB: 检查存储目录权限
   - Qdrant: 确认Qdrant服务运行状态
   - 查看自动回退日志

4. **文档处理失败**
   - 检查文件格式是否支持
   - 确认文件大小未超限
   - 查看OCR引擎状态
   - 检查模型下载情况

5. **向量搜索不准确**
   - 调整相似度阈值
   - 检查文档分块大小
   - 重新处理文档
   - 验证嵌入模型

### 日志查看
```bash
# 查看应用日志
tail -f logs/app.log

# 查看Celery任务日志
tail -f logs/celery.log

# 查看数据库日志
tail -f logs/db.log
```

### 性能监控
```bash
# 查看系统资源使用
htop

# 查看数据库连接
psql -h localhost -p 15432 -U postgres -d fire_ops -c "SELECT * FROM pg_stat_activity;"

# 查看Redis状态
redis-cli -h localhost -p 16379 info
```

## 📈 性能优化

### 数据库优化
- 为向量字段创建索引
- 优化查询语句
- 配置连接池
- 定期清理过期数据

### 缓存策略
- Redis会话缓存
- 向量结果缓存
- 文档内容缓存
- 模型加载缓存

### 文件存储优化
- 静态文件CDN
- 文档分片存储
- 定期清理机制
- 压缩存储

### 向量搜索优化
- 调整分块大小
- 优化相似度阈值
- 使用更高效的向量数据库
- 批量处理文档

## 🔮 未来规划

- [x] 集成Qdrant向量数据库
- [x] 支持OCR文字识别
- [x] 异步任务处理
- [ ] 集成更多LLM模型
- [ ] 支持更多文档格式
- [ ] 添加文档分类功能
- [ ] 实现文档版本管理
- [ ] 添加多语言支持
- [ ] 优化向量搜索性能
- [ ] 添加实时协作功能
- [ ] 支持API限流和监控

## 📞 技术支持

### 系统要求检查清单
- [ ] Python 3.10+ 已安装
- [ ] PostgreSQL 服务运行正常
- [ ] Redis 服务运行正常
- [ ] 向量数据库连接正常
- [ ] 必要的Python包已安装
- [ ] 环境变量配置正确
- [ ] 数据库迁移已完成
- [ ] 文件存储权限正确

### 获取帮助
1. 检查系统日志文件
2. 验证所有服务状态
3. 确认配置文件正确
4. 查看API文档和示例

### 贡献指南
1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

---

**注意**: 这是一个集成了设备管理、RAG智能问答、OCR识别和多种向量数据库支持的完整系统。系统具有良好的扩展性和可维护性，支持多种部署方式。