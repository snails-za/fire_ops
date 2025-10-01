# 消安云管系统

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

## 🏗️ 技术架构

### 核心技术栈
- **后端框架**: FastAPI 0.115.5
- **数据库**: PostgreSQL
- **ORM**: Tortoise-ORM
- **缓存**: Redis
- **认证**: JWT Token
- **文档处理**: LangChain, PyPDF, python-docx, openpyxl
- **向量化**: Sentence Transformers
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
│   │   └── rag_helper.py     # RAG工具类
│   └── dependencies/          # 依赖注入
├── static/                    # 静态资源
│   ├── chat.html             # 智能问答页面
│   ├── login.html            # 登录页面
│   └── ...
├── config.py                 # 配置文件
├── asgi.py                   # ASGI应用入口
├── init_rag.py              # RAG系统初始化脚本
└── README.md                 # 项目说明
```

## 🚀 快速开始

### 环境要求
- Python 3.10+
- PostgreSQL
- Redis

### 1. 安装依赖

#### 使用uv安装（推荐）
```bash
uv sync
```

#### 使用pip安装
```bash
pip install -r requirements.txt
```

### 2. 初始化系统
```bash
# 运行RAG系统初始化脚本
python init_rag.py
```

### 3. 数据库迁移
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

### 4. 启动服务

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
uvicorn asgi:app --reload
```

#### 使用gunicorn启动
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker asgi:app
```

### 5. 访问系统
- **主页**: http://localhost:8000
- **智能问答**: http://localhost:8000/static/chat.html
- **API文档**: http://localhost:8000/docs
- **登录账号**: admin / 123456

## 📖 使用指南

### 设备管理
1. 登录系统后，使用设备管理API
2. 上传设备图片
3. 添加设备信息（名称、地址、状态等）
4. 查看和管理设备列表

### RAG智能问答
1. **上传文档**
   - 进入智能问答页面
   - 点击"上传文档"按钮
   - 选择支持的文档格式（PDF、Word、Excel、TXT）
   - 等待文档处理完成

2. **开始问答**
   - 创建新的对话会话
   - 在输入框中输入问题
   - 系统基于上传的文档提供准确答案
   - 查看参考文档和相似度信息

3. **会话管理**
   - 支持多个对话会话
   - 查看历史对话记录
   - 删除不需要的会话

## 🔧 API接口

### 用户认证
- `POST /api/v1/auth/login` - 用户登录
- `GET /api/v1/auth/info` - 获取用户信息
- `GET /api/v1/auth/logout` - 用户登出

### 设备管理
- `GET /api/v1/device/list` - 获取设备列表
- `POST /api/v1/device/create` - 创建设备
- `POST /api/v1/device/upload/image` - 上传设备图片

### 文档管理
- `POST /api/v1/documents/upload` - 上传文档
- `GET /api/v1/documents/list` - 获取文档列表
- `GET /api/v1/documents/{id}` - 获取文档详情
- `DELETE /api/v1/documents/{id}` - 删除文档

### 智能问答
- `POST /api/v1/chat/sessions` - 创建聊天会话
- `GET /api/v1/chat/sessions` - 获取会话列表
- `POST /api/v1/chat/sessions/{id}/ask` - 智能问答
- `GET /api/v1/chat/search` - 搜索文档

## ⚙️ 配置说明

### 环境变量
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

# RAG配置
OPENAI_API_KEY=your_openai_key  # 可选
MAX_FILE_SIZE=52428800          # 50MB
CHUNK_SIZE=1000
DEFAULT_TOP_K=5
```

### 数据库表结构
- `user` - 用户表
- `device` - 设备表
- `document` - 文档表
- `document_chunk` - 文档分块表
- `vector_store` - 向量存储表
- `chat_session` - 聊天会话表
- `chat_message` - 聊天消息表

## 🐳 部署

### Docker部署
```bash
# 构建镜像
sh build.sh

# 运行容器
docker run -p 8000:8000 your-image
```

### Docker Swarm部署
参考部署仓库：[docker-swarm-deploy](https://github.com/snails-za/fire_ops_deploy)

## 🔒 安全特性

- **JWT认证**: 基于Token的用户认证
- **权限控制**: 用户级别的数据隔离
- **文件验证**: 文件类型和大小限制
- **数据加密**: 敏感数据加密存储
- **会话管理**: 安全的会话状态管理

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

3. **文档处理失败**
   - 检查文件格式是否支持
   - 确认文件大小未超限
   - 查看错误日志

4. **向量搜索不准确**
   - 调整相似度阈值
   - 检查文档分块大小
   - 重新处理文档

### 日志查看
```bash
# 查看应用日志
tail -f logs/app.log

# 查看数据库日志
tail -f logs/db.log
```

## 📈 性能优化

### 数据库优化
- 为向量字段创建索引
- 优化查询语句
- 配置连接池

### 缓存策略
- Redis会话缓存
- 向量结果缓存
- 文档内容缓存

### 文件存储
- 静态文件CDN
- 文档分片存储
- 定期清理机制

## 🔮 未来规划

- [ ] 集成OpenAI GPT模型
- [ ] 支持更多文档格式
- [ ] 添加文档分类功能
- [ ] 实现文档版本管理
- [ ] 添加多语言支持
- [ ] 优化向量搜索性能

## 📞 技术支持

如有问题，请检查：
1. 系统日志文件
2. 数据库连接状态
3. Redis服务状态
4. 文档处理状态

---

**注意**: 这是一个集成了设备管理和RAG智能问答的完整系统，保持了原有功能的完整性，同时新增了强大的智能问答能力。