import os

from starlette.config import Config
from pydantic import Secret

config = Config()

DEBUG = config("DEBUG", cast=bool, default=False)
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
STATIC_PATH = os.path.join(BASE_PATH, "static")

# 刷新token时间【固定值，需要比MAX_AGE时间短】
REFLESH_MAX_AGE = 60
# 登录有效性 Token【可以数据库配置，需要大于 REFLESH_MAX_AGE】
MAX_AGE = 60*60

# 数据库配置
DB_HOST = config("POSTGRES_HOST", default="localhost")
DB_PORT = config("POSTGRES_PORT", cast=int, default=15432)
DB_USER = config("POSTGRES_USER", default="postgres")
DB_PASSWORD = Secret(config("POSTGRES_PASSWORD", cast=str, default="OTcxMDEx"))
DB_DATABASE = config("POSTGRES_DB", default="fire_ops")
DATABASE_URL = f"postgres://{DB_USER}:{DB_PASSWORD.get_secret_value()}@{DB_HOST}:{DB_PORT}/{DB_DATABASE}"
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
for _ in os.listdir(os.path.join("apps", "models")):
    if _.endswith(".py") and _ != "__init__.py":
        TORTOISE_ORM["apps"]["models"]["models"].append(f"apps.models.{_.split('.')[0]}")

REDIS_HOST = config("REDIS_HOST", default="localhost")
REDIS_PORT = config("REDIS_PORT", cast=int, default=16379)
REDIS_PASSWORD = config("REDIS_PASSWORD", cast=str, default="")
REDIS_DB = config("REDIS_DB", cast=int, default=0)

# Session配置
SECRET_KEY = "adjasdmasdjoqwijeqwbhfqwnqndaslmdlkas"

# 密钥配置
AES_KEY = config("AES_KEY", default="awkfjwhkgowkslg3")

# 数据库迁移安全模式：1表示安全模式，0表示非安全模式
AERICH_SAFE_MODE = config("AERICH_SAFE_MODE", cast=int, default=1)

# 文档存储路径
DOCUMENT_STORE_PATH = os.path.join(BASE_PATH, "data", "documents")

# RAG相关配置
# OpenAI API配置
OPENAI_API_KEY = config("OPENAI_API_KEY", default="sk-zk21f16b46c63a80f63e49c05308ebd59cb66be108a0fdca")
OPENAI_BASE_URL = config("OPENAI_BASE_URL", default="https://api.zhizengzeng.com/v1/")

# 向量数据库配置（Chroma）
VECTOR_DB_PATH = os.path.join(BASE_PATH, "data", "vector_db")
CHROMA_PERSIST_DIRECTORY = os.path.join(VECTOR_DB_PATH, "chroma")
CHROMA_COLLECTION = config("CHROMA_COLLECTION", default="documents")

# 文档处理配置
MAX_FILE_SIZE = config("MAX_FILE_SIZE", cast=int, default=50 * 1024 * 1024)  # 50MB
ALLOWED_FILE_TYPES = ['pdf', 'docx', 'doc', 'xlsx', 'xls', 'txt']

# 嵌入模型配置（本地模型优先）
# 当前模型：多语言通用
# EMBEDDING_MODEL = config("EMBEDDING_MODEL", default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# 中文优化模型选项：
# BGE模型（推荐）- 百度开源，中文效果优秀
EMBEDDING_MODEL = config("EMBEDDING_MODEL", default="BAAI/bge-small-zh-v1.5")

# Text2Vec模型 - 另一个中文优化选择
# EMBEDDING_MODEL = config("EMBEDDING_MODEL", default="shibing624/text2vec-base-chinese")

# 高精度多语言模型
# EMBEDDING_MODEL = config("EMBEDDING_MODEL", default="sentence-transformers/paraphrase-multilingual-mpnet-base-v2")

EMBEDDING_DIMENSION = config("EMBEDDING_DIMENSION", cast=int, default=384)
HF_HOME = config("HF_HOME", default=os.path.join(BASE_PATH, "models"))
HF_OFFLINE = config("HF_OFFLINE", cast=bool, default=True)

# 文本分割配置
CHUNK_SIZE = config("CHUNK_SIZE", cast=int, default=1000)
CHUNK_OVERLAP = config("CHUNK_OVERLAP", cast=int, default=200)

# 相似度阈值配置
SIMILARITY_THRESHOLD = config("SIMILARITY_THRESHOLD", cast=float, default=0.6)  # 相似度阈值，0-1之间
# 搜索配置
DEFAULT_TOP_K = config("DEFAULT_TOP_K", cast=int, default=5)

# OCR配置
OCR_ENABLED = config("OCR_ENABLED", cast=bool, default=True)  # OCR功能开关
OCR_AUTO_FALLBACK = config("OCR_AUTO_FALLBACK", cast=bool, default=True)  # 自动降级到OCR
OCR_MIN_TEXT_LENGTH = config("OCR_MIN_TEXT_LENGTH", cast=int, default=100)  # 触发OCR的最小文本长度
OCR_MAX_FILE_SIZE = config("OCR_MAX_FILE_SIZE", cast=int, default=50) * 1024 * 1024  # OCR最大文件大小(50MB)

# OCR引擎选择: paddleocr, easyocr (仅免费开源引擎)
OCR_ENGINE = config("OCR_ENGINE", default="paddleocr")

# OCR性能配置
OCR_USE_GPU = config("OCR_USE_GPU", cast=bool, default=True)  # 是否启用GPU加速
OCR_BATCH_SIZE = config("OCR_BATCH_SIZE", cast=int, default=12)  # 批处理大小
OCR_MAX_PAGES = config("OCR_MAX_PAGES", cast=int, default=50)  # 最大处理页数



