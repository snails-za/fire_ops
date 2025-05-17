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
DB_DATABASE = config("POSTGRES_DB", default="fastapi_demo")
DATABASE_URL = f"postgres://{DB_USER}:{DB_PASSWORD.get_secret_value()}@{DB_HOST}:{DB_PORT}/{DB_DATABASE}"
TORTOISE_ORM = {
    "connections": {
        "default": DATABASE_URL,
    },
    "apps": {
        "models": {
            "models": ["aerich.models", "apps.models"],
            "default_connection": "default",
        }
    },
}

REDIS_HOST = config("REDIS_HOST", default="localhost")
REDIS_PORT = config("REDIS_PORT", cast=int, default=16379)
REDIS_PASSWORD = config("REDIS_PASSWORD", cast=str, default="")
REDIS_DB = config("REDIS_DB", cast=int, default=0)

# Session配置
SECRET_KEY = "adjasdmasdjoqwijeqwbhfqwnqndaslmdlkas"

# 密钥配置
AES_KEY = config("AES_KEY", default="awkfjwhkgowkslg3")



