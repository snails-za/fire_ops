# RAG系统技术文档

## 📋 目录

1. [系统概述](#系统概述)
2. [技术架构](#技术架构)
3. [核心组件](#核心组件)
4. [API接口](#api接口)
5. [前端界面](#前端界面)
6. [配置说明](#配置说明)
7. [部署指南](#部署指南)
8. [性能优化](#性能优化)
9. [故障排除](#故障排除)
10. [开发指南](#开发指南)

---

## 🎯 系统概述

### 什么是RAG系统？

RAG（Retrieval-Augmented Generation，检索增强生成）是一种结合了信息检索和文本生成的AI技术。本系统实现了一个完整的RAG解决方案，能够：

- **智能文档处理**：支持PDF、DOCX、Excel、TXT等多种格式
- **语义搜索**：基于向量相似度的智能检索
- **智能问答**：结合LLM的上下文感知回答
- **高亮显示**：智能关键词高亮和文档查看

### 核心特性

✅ **多格式文档支持** - PDF、DOCX、XLSX、TXT  
✅ **智能文本分块** - 保持语义完整性的文档分割  
✅ **向量化存储** - 基于Sentence Transformers的高质量嵌入  
✅ **语义搜索** - ChromaDB向量数据库支持  
✅ **LLM集成** - OpenAI GPT智能问答  
✅ **实时处理** - 异步文档处理和向量化  
✅ **用户友好** - 现代化Web界面和交互体验  

---

## 🏗️ 技术架构

### 整体架构图

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端界面      │    │   FastAPI后端   │    │   数据存储      │
│                 │    │                 │    │                 │
│ • 聊天界面      │◄──►│ • REST API      │◄──►│ • PostgreSQL    │
│ • 文档管理      │    │ • 异步处理      │    │ • ChromaDB      │
│ • 高亮显示      │    │ • 错误处理      │    │ • 文件系统      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   RAG核心组件   │
                       │                 │
                       │ • DocumentProcessor │
                       │ • VectorSearch  │
                       │ • RAGGenerator  │
                       └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   外部服务      │
                       │                 │
                       │ • OpenAI API    │
                       │ • HuggingFace   │
                       └─────────────────┘
```

### 技术栈

**后端框架**
- FastAPI 0.115.5 - 现代Python Web框架
- Tortoise-ORM - 异步ORM
- Pydantic - 数据验证

**AI/ML组件**
- LangChain - LLM应用框架
- Sentence Transformers - 文本向量化
- OpenAI GPT - 智能问答
- ChromaDB - 向量数据库

**文档处理**
- PyPDF - PDF文本提取
- python-docx - Word文档处理
- openpyxl - Excel文件处理

**数据存储**
- PostgreSQL - 关系型数据库
- Redis - 缓存和会话
- 本地文件系统 - 文档存储

---

## 🔧 核心组件

### 1. DocumentProcessor（文档处理器）

**功能职责**
- 多格式文档内容提取
- 智能文本分块
- 向量嵌入生成
- 数据库同步

**关键方法**
```python
class DocumentProcessor:
    async def process_document(self, document_id: int, file_path: str, file_type: str) -> bool
    async def _extract_content(self, file_path: str, file_type: str) -> str
    async def _extract_pdf_content(self, file_path: str) -> str
    async def _extract_docx_content(self, file_path: str) -> str
    async def _extract_excel_content(self, file_path: str) -> str
    async def _extract_txt_content(self, file_path: str) -> str
```

**处理流程**
1. **文档上传** → 保存到文件系统
2. **内容提取** → 根据文件类型提取文本
3. **文本分块** → 使用RecursiveCharacterTextSplitter
4. **向量化** → Sentence Transformers生成嵌入
5. **存储** → 保存到ChromaDB和PostgreSQL

**配置参数**
```python
# 文本分块配置
chunk_size = 1000      # 每个块的最大字符数
chunk_overlap = 200    # 块之间的重叠字符数

# 向量模型配置
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
```

### 2. VectorSearch（向量搜索引擎）

**功能职责**
- 语义相似度搜索
- 向量数据管理
- 搜索结果排序
- 数据库关联查询

**关键方法**
```python
class VectorSearch:
    async def search_similar_chunks(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]
    async def delete_document_vectors(self, document_id: int)
    async def count_vectors(self) -> int
```

**搜索流程**
1. **查询向量化** → 将用户问题转换为向量
2. **相似度计算** → ChromaDB余弦相似度搜索
3. **结果过滤** → 验证数据库中的记录
4. **排序返回** → 按相似度降序排列

**性能优化**
- 使用ChromaDB的HNSW索引
- 批量查询减少数据库访问
- 异步处理提高响应速度

### 3. RAGGenerator（RAG生成器）

**功能职责**
- 集成检索和生成
- LLM智能问答
- 上下文构建
- 回答质量控制

**关键方法**
```python
class RAGGenerator:
    async def generate_answer(self, query: str, context_chunks: List[Dict[str, Any]]) -> str
    async def _llm_answer(self, query: str, context: str) -> str
    def _simple_answer(self, query: str, context_chunks: List[Dict[str, Any]]) -> str
    def _build_sources_info(self, context_chunks: List[Dict[str, Any]]) -> str
```

**回答策略**
1. **智能模式** → 使用OpenAI GPT生成回答
2. **简单模式** → 基于关键词匹配的备用方案
3. **降级处理** → LLM失败时自动切换到简单模式

**提示工程**
```python
system_template = """你是一个专业的文档问答助手。请基于提供的文档内容准确回答用户的问题。

回答要求：
1. 严格基于提供的文档内容回答，不要添加文档中没有的信息
2. 如果文档中没有相关信息，请明确说明"根据提供的文档内容，无法找到相关信息"
3. 回答要准确、详细且有条理，使用清晰的段落结构
4. 可以引用具体的文档名称和关键内容片段
5. 如果有多个文档提供了相关信息，请综合分析
6. 用中文回答，语言要专业但易懂

提供的文档内容：
{context}"""
```

---

## 🌐 API接口

### 文档管理API

#### 1. 上传文档
```http
POST /api/v1/documents/upload
Content-Type: multipart/form-data

参数:
- file: 文档文件 (PDF/DOCX/XLSX/TXT)

响应:
{
    "code": 200,
    "message": "文档上传成功，正在处理中...",
    "data": {
        "id": 1,
        "filename": "document.pdf",
        "original_filename": "原始文档.pdf",
        "file_size": 1024000,
        "file_type": "pdf",
        "status": "processing"
    }
}
```

#### 2. 获取文档列表
```http
GET /api/v1/documents/list?page=1&page_size=10&status=completed

响应:
{
    "code": 200,
    "data": {
        "documents": [...],
        "total": 50,
        "page": 1,
        "page_size": 10,
        "total_pages": 5
    }
}
```

#### 3. 查看文档内容
```http
GET /api/v1/documents/{document_id}/view?chunk_id={chunk_id}&highlight={keywords}

响应:
{
    "code": 200,
    "data": {
        "document": {...},
        "content": "文档内容",
        "highlighted_content": "高亮后的内容",
        "highlight_text": "关键词",
        "has_highlight": true
    }
}
```

### 智能问答API

#### 1. 智能问答
```http
POST /api/v1/chat/ask
Content-Type: application/x-www-form-urlencoded

参数:
- question: 用户问题
- top_k: 检索文档数量 (默认5)

响应:
{
    "code": 200,
    "data": {
        "question": "用户问题",
        "answer": "AI生成的回答",
        "sources": [
            {
                "document_id": 1,
                "document_name": "文档名称",
                "similarity": 0.85,
                "content_preview": "内容预览...",
                "download_url": "/api/v1/documents/1/download",
                "view_url": "/api/v1/documents/1/view?chunk_id=1"
            }
        ],
        "search_info": {
            "original_query": "原始问题",
            "search_query": "优化后的搜索查询",
            "results_count": 3,
            "llm_enhanced": true
        }
    }
}
```

#### 2. 文档搜索
```http
GET /api/v1/chat/search?query=搜索关键词&top_k=5

响应:
{
    "code": 200,
    "data": {
        "query": "搜索关键词",
        "results": [...],
        "total": 3,
        "llm_enhanced": true
    }
}
```

---

## 🎨 前端界面

### 聊天界面 (chat.html)

**核心功能**
- 实时问答交互
- 消息历史记录
- 来源文档展示
- 智能高亮查看

**关键组件**
```javascript
// 发送消息
async function sendMessage()

// 智能高亮显示
async function viewWithSmartHighlight(documentId, chunkId, documentName)

// 关键词提取
function extractKeywords(text)

// 文档模态框
function showDocumentModal(title, content, isHighlighted, subtitle)
```

**用户体验优化**
- 响应式设计适配移动端
- 加载状态和错误提示
- 键盘快捷键支持
- 自动滚动到高亮位置

### 样式特性

**现代化设计**
- 渐变背景和阴影效果
- 平滑动画过渡
- 自定义滚动条
- 高亮文本动画

**交互反馈**
- 按钮悬停效果
- 模态框淡入动画
- 高亮脉冲效果
- 加载状态指示

---

## ⚙️ 配置说明

### 环境变量配置

```python
# config.py

# 数据库配置
DATABASE_URL = "postgresql://user:password@localhost/dbname"
REDIS_URL = "redis://localhost:6379"

# OpenAI配置
OPENAI_API_KEY = "sk-..."
OPENAI_BASE_URL = "https://api.openai.com/v1"

# 向量模型配置
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
HF_HOME = "./models"  # HuggingFace模型缓存目录
HF_OFFLINE = True     # 离线模式

# ChromaDB配置
CHROMA_PERSIST_DIRECTORY = "./vector_db/chroma"
CHROMA_COLLECTION = "documents"

# 文件存储配置
STATIC_PATH = "./static"
DOCUMENT_STORE_PATH = "./static/documents"
```

### 模型配置

**推荐的向量模型**
- `paraphrase-multilingual-MiniLM-L12-v2` - 多语言支持，平衡性能
- `text2vec-base-chinese` - 中文优化
- `all-MiniLM-L6-v2` - 英文轻量级

**LLM配置**
- 模型：GPT-3.5-turbo
- 温度：0.1（确保回答一致性）
- 最大令牌：2000

---

## 🚀 部署指南

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 数据库初始化

```bash
# 数据库迁移
aerich init -t config.TORTOISE_ORM
aerich init-db
aerich upgrade

# 初始化RAG系统
python init_rag.py
```

### 3. 启动服务

```bash
# 开发模式
fastapi dev asgi.py

# 生产模式
uvicorn asgi:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4. Docker部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "asgi:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 5. Nginx配置

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    client_max_body_size 100M;  # 支持大文件上传
}
```

---

## ⚡ 性能优化

### 1. 向量搜索优化

**ChromaDB优化**
```python
# 使用HNSW索引
collection = client.get_or_create_collection(
    name="documents",
    metadata={"hnsw:space": "cosine", "hnsw:M": 16}
)

# 批量操作
collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas)
```

**搜索参数调优**
- `top_k`: 根据业务需求调整（推荐5-10）
- `chunk_size`: 平衡精度和性能（推荐800-1200）
- `chunk_overlap`: 保持上下文连续性（推荐15-25%）

### 2. 数据库优化

**索引优化**
```sql
-- 文档表索引
CREATE INDEX idx_document_status ON documents(status);
CREATE INDEX idx_document_upload_time ON documents(upload_time);

-- 文档块表索引
CREATE INDEX idx_chunk_document_id ON document_chunks(document_id);
CREATE INDEX idx_chunk_index ON document_chunks(chunk_index);
```

**查询优化**
- 使用异步ORM减少阻塞
- 批量查询减少数据库访问
- 适当的分页大小

### 3. 缓存策略

**Redis缓存**
```python
# 缓存搜索结果
@cache(expire=3600)  # 1小时缓存
async def search_similar_chunks(query: str, top_k: int):
    # 搜索逻辑
    pass

# 缓存文档内容
@cache(expire=86400)  # 24小时缓存
async def get_document_content(document_id: int):
    # 获取文档内容
    pass
```

### 4. 异步处理

**后台任务**
```python
from fastapi import BackgroundTasks

@router.post("/upload")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile):
    # 立即返回响应
    document = await create_document_record(file)
    
    # 后台处理
    background_tasks.add_task(process_document, document.id)
    
    return {"message": "上传成功，正在处理中..."}
```

---

## 🔍 故障排除

### 常见问题

#### 1. 向量模型加载失败

**问题症状**
```
OSError: Can't load tokenizer for 'sentence-transformers/...'
```

**解决方案**
```bash
# 设置HuggingFace缓存目录
export HF_HOME=/path/to/models

# 手动下载模型
python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
"
```

#### 2. ChromaDB连接错误

**问题症状**
```
chromadb.errors.InvalidDimensionException: Embedding dimension mismatch
```

**解决方案**
```python
# 清理ChromaDB数据
import shutil
shutil.rmtree('./vector_db/chroma')

# 重新初始化
python init_rag.py
```

#### 3. OpenAI API调用失败

**问题症状**
```
openai.error.RateLimitError: Rate limit exceeded
```

**解决方案**
```python
# 添加重试机制
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def call_openai_api():
    # API调用逻辑
    pass
```

#### 4. 文档处理超时

**问题症状**
- 大文件处理时间过长
- 内存使用过高

**解决方案**
```python
# 分批处理大文档
async def process_large_document(content: str):
    chunks = split_content_into_batches(content, batch_size=50)
    
    for batch in chunks:
        await process_batch(batch)
        await asyncio.sleep(0.1)  # 避免资源占用过高
```

### 日志配置

```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rag_system.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

### 监控指标

**关键指标**
- 文档处理成功率
- 平均响应时间
- 向量搜索准确率
- LLM调用成功率
- 系统资源使用情况

---

## 👨‍💻 开发指南

### 代码结构

```
app/
├── apps/
│   ├── api/                 # API路由
│   │   ├── chat/           # 聊天API
│   │   ├── documents/      # 文档API
│   │   └── users/          # 用户API
│   ├── models/             # 数据模型
│   │   ├── document.py     # 文档模型
│   │   └── user.py         # 用户模型
│   ├── utils/              # 工具类
│   │   ├── rag_helper.py   # RAG核心组件
│   │   └── common.py       # 通用工具
│   └── dependencies/       # 依赖注入
├── static/                 # 静态资源
│   ├── chat.html          # 聊天界面
│   └── upload.html        # 上传界面
├── config.py              # 配置文件
├── asgi.py               # ASGI应用
└── init_rag.py           # 初始化脚本
```

### 开发规范

**代码风格**
- 使用Black格式化代码
- 遵循PEP 8规范
- 添加类型注解
- 编写详细的文档字符串

**错误处理**
```python
try:
    result = await some_operation()
    logger.info(f"操作成功: {result}")
    return result
except SpecificException as e:
    logger.error(f"特定错误: {e}")
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    logger.error(f"未知错误: {e}")
    raise HTTPException(status_code=500, detail="内部服务器错误")
```

**测试编写**
```python
import pytest
from fastapi.testclient import TestClient

@pytest.mark.asyncio
async def test_document_upload():
    with TestClient(app) as client:
        with open("test.pdf", "rb") as f:
            response = client.post(
                "/api/v1/documents/upload",
                files={"file": ("test.pdf", f, "application/pdf")}
            )
        assert response.status_code == 200
        assert "上传成功" in response.json()["message"]
```

### 扩展开发

**添加新的文档格式支持**
```python
class DocumentProcessor:
    async def _extract_content(self, file_path: str, file_type: str) -> str:
        if file_type == "new_format":
            return await self._extract_new_format_content(file_path)
        # 现有逻辑...
    
    async def _extract_new_format_content(self, file_path: str) -> str:
        # 新格式处理逻辑
        pass
```

**自定义向量模型**
```python
from sentence_transformers import SentenceTransformer

class CustomEmbeddingModel:
    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name)
    
    def encode(self, texts: List[str]) -> np.ndarray:
        # 自定义编码逻辑
        return self.model.encode(texts)
```

---

## 📊 系统监控

### 性能指标

**响应时间监控**
```python
import time
from functools import wraps

def monitor_performance(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        
        logger.info(f"{func.__name__} 执行时间: {end_time - start_time:.2f}秒")
        return result
    return wrapper

@monitor_performance
async def search_similar_chunks(query: str, top_k: int):
    # 搜索逻辑
    pass
```

**资源使用监控**
```python
import psutil

def log_system_stats():
    cpu_percent = psutil.cpu_percent()
    memory_percent = psutil.virtual_memory().percent
    disk_percent = psutil.disk_usage('/').percent
    
    logger.info(f"系统资源使用 - CPU: {cpu_percent}%, 内存: {memory_percent}%, 磁盘: {disk_percent}%")
```

### 健康检查

```python
@router.get("/health")
async def health_check():
    checks = {
        "database": await check_database_connection(),
        "vector_db": await check_vector_db_connection(),
        "llm": await check_llm_availability(),
        "storage": check_storage_space()
    }
    
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={"status": "healthy" if all_healthy else "unhealthy", "checks": checks}
    )
```

---

## 🔮 未来规划

### 功能扩展

1. **多模态支持** - 图片、音频文档处理
2. **实时协作** - 多用户同时编辑和问答
3. **知识图谱** - 文档间关系建模
4. **个性化推荐** - 基于用户历史的智能推荐
5. **API集成** - 支持更多第三方服务

### 技术优化

1. **分布式部署** - 支持集群部署和负载均衡
2. **流式处理** - 实时文档处理和增量更新
3. **模型优化** - 自定义训练和模型压缩
4. **缓存优化** - 多级缓存和智能预加载
5. **安全增强** - 数据加密和访问控制

---

## 📞 技术支持

### 联系方式

- **项目仓库**: [GitHub链接]
- **技术文档**: [文档链接]
- **问题反馈**: [Issue链接]

### 贡献指南

欢迎提交Pull Request和Issue！请确保：

1. 代码符合项目规范
2. 添加适当的测试
3. 更新相关文档
4. 详细描述变更内容

---

*最后更新时间: 2024年10月*
*文档版本: v1.0*
