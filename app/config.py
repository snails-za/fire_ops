"""
系统配置文件
统一管理所有配置项，按功能模块分组
"""

import os
from starlette.config import Config
from pydantic import Secret

# 配置对象
config = Config()

# =============================================================================
# 基础配置
# =============================================================================

# 应用基础配置
DEBUG = config("DEBUG", cast=bool, default=False)
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
STATIC_PATH = os.path.join(BASE_PATH, "static")

# 安全配置
SECRET_KEY = config("SECRET_KEY", default="adjasdmasdjoqwijeqwbhfqwnqndaslmdlkas")
AES_KEY = config("AES_KEY", default="awkfjwhkgowkslg3")

# Token配置
REFRESH_MAX_AGE = 60  # 刷新token时间（秒）
MAX_AGE = 60 * 60     # 登录有效性Token（秒）

# =============================================================================
# 数据库配置
# =============================================================================

# PostgreSQL配置
DB_HOST = config("POSTGRES_HOST", default="localhost")
DB_PORT = config("POSTGRES_PORT", cast=int, default=15432)
DB_USER = config("POSTGRES_USER", default="postgres")
DB_PASSWORD = Secret(config("POSTGRES_PASSWORD", cast=str, default="OTcxMDEx"))
DB_DATABASE = config("POSTGRES_DB", default="fire_ops")

# 数据库连接URL
DATABASE_URL = f"postgres://{DB_USER}:{DB_PASSWORD.get_secret_value()}@{DB_HOST}:{DB_PORT}/{DB_DATABASE}"

# Tortoise ORM配置
TORTOISE_ORM = {
    "connections": {
        "default": DATABASE_URL,
    },
    "apps": {
        "models": {
            "models": ["aerich.models"],
            "default_connection": "default",
        }
    },
}

# 动态添加模型
for _ in os.listdir(os.path.join("apps", "models")):
    if _.endswith(".py") and _ != "__init__.py":
        TORTOISE_ORM["apps"]["models"]["models"].append(f"apps.models.{_.split('.')[0]}")

# 数据库迁移配置
AERICH_SAFE_MODE = config("AERICH_SAFE_MODE", cast=int, default=1)

# =============================================================================
# Redis配置
# =============================================================================

REDIS_HOST = config("REDIS_HOST", default="localhost")
REDIS_PORT = config("REDIS_PORT", cast=int, default=16379)
REDIS_PASSWORD = config("REDIS_PASSWORD", cast=str, default="")
REDIS_DB = config("REDIS_DB", cast=int, default=0)

# =============================================================================
# 文档处理配置
# =============================================================================

# 文档存储路径
DOCUMENT_STORE_PATH = os.path.join(BASE_PATH, "data", "documents")

# 文件处理限制
MAX_FILE_SIZE = config("MAX_FILE_SIZE", cast=int, default=50 * 1024 * 1024)  # 50MB
ALLOWED_FILE_TYPES = ['pdf', 'docx', 'doc', 'xlsx', 'xls', 'txt']

# =============================================================================
# RAG系统配置
# =============================================================================

# OpenAI API配置
OPENAI_API_KEY = config("OPENAI_API_KEY", default="sk-zk21f16b46c63a80f63e49c05308ebd59cb66be108a0fdca")
OPENAI_BASE_URL = config("OPENAI_BASE_URL", default="https://api.zhizengzeng.com/v1/")

# 嵌入模型配置
# 全局禁用 tokenizers 的并行分词
os.environ["TOKENIZERS_PARALLELISM"] = "false"
# 1. BAAI/bge-small-zh-v1.5
# 2. sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
# 3. sentence-transformers/paraphrase-multilingual-mpnet-base-v2
# 4. shibing624/text2vec-base-chinese
EMBEDDING_MODEL = config("EMBEDDING_MODEL", default="BAAI/bge-small-zh-v1.5")
EMBEDDING_DIMENSION = config("EMBEDDING_DIMENSION", cast=int, default=384)
HF_HOME = config("HF_HOME", default=os.path.join(BASE_PATH, "models"))
HF_OFFLINE = config("HF_OFFLINE", cast=bool, default=True)

# 文本分割配置
CHUNK_SIZE = config("CHUNK_SIZE", cast=int, default=1000)
CHUNK_OVERLAP = config("CHUNK_OVERLAP", cast=int, default=200)

# 搜索配置
SIMILARITY_THRESHOLD = config("SIMILARITY_THRESHOLD", cast=float, default=0.7)
DEFAULT_TOP_K = config("DEFAULT_TOP_K", cast=int, default=5)

# =============================================================================
# NLTK 配置
# =============================================================================

# NLTK 数据路径配置（避免网络下载）
NLTK_DATA_PATH = config("NLTK_DATA_PATH", default=os.path.join(BASE_PATH, "nltk_data"))

# =============================================================================
# 向量数据库配置
# =============================================================================

# 向量数据库类型选择
VECTOR_DB_TYPE = config("VECTOR_DB_TYPE", default="qdrant")  # 可选: chroma, qdrant

# ChromaDB配置
VECTOR_DB_PATH = os.path.join(BASE_PATH, "data", "vector_db")
CHROMA_PERSIST_DIRECTORY = os.path.join(VECTOR_DB_PATH, "chroma")
CHROMA_COLLECTION = config("CHROMA_COLLECTION", default="documents")

# Qdrant配置
QDRANT_HOST = config("QDRANT_HOST", default="localhost")
QDRANT_PORT = config("QDRANT_PORT", cast=int, default=6333)
QDRANT_COLLECTION_NAME = config("QDRANT_COLLECTION_NAME", default="documents")
QDRANT_URL = f"http://{QDRANT_HOST}:{QDRANT_PORT}"

# =============================================================================
# OCR配置
# =============================================================================

OCR_ENABLED = config("OCR_ENABLED", cast=bool, default=True)
OCR_USE_GPU = config("OCR_USE_GPU", cast=bool, default=True)
# OCR模型缓存路径
OCR_MODEL_PATH = config("OCR_MODEL_PATH", default=os.path.join(BASE_PATH, "models", "easyocr"))

# OCR并发处理配置
OCR_MAX_CONCURRENT_PAGES = config("OCR_MAX_CONCURRENT_PAGES", cast=int, default=1)
# 说明：
# 1 = 串行处理（最省内存，推荐内存 < 2GB）
# 2 = 并发2页（需要更多内存，推荐内存 2-4GB）
# 3+ = 更高并发（需要 4GB+ 内存）

# OCR分批处理配置（节省内存）
OCR_BATCH_SIZE = config("OCR_BATCH_SIZE", cast=int, default=5)  # 每批处理页数
OCR_DPI = config("OCR_DPI", cast=int, default=150)  # 降低DPI节省内存

# =============================================================================
# Celery异步任务配置
# =============================================================================

# 消息代理和结果后端
BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/1'
CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:{REDIS_PORT}/2'

# 序列化配置
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ["json"]

# 任务配置
CELERY_TASK_RESULT_EXPIRES = 60 * 60 * 24  # 24小时过期

# 队列配置
CELERY_DEFAULT_QUEUE = "default"
CELERY_QUEUES = {
    "default": {
        "exchange": "default",
        "exchange_type": "direct",
        "routing_key": "default"
    }
}