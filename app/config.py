import os

from starlette.config import Config
from pydantic import Secret

from apps.utils.common import Base64Util

config = Config()

DEBUG = config("DEBUG", cast=bool, default=False)
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
STATIC_PATH = os.path.join(BASE_PATH, "static")
# 数据库配置
DB_HOST = config("POSTGRES_HOST", default="localhost")
DB_PORT = config("POSTGRES_PORT", cast=int, default=15432)
DB_USER = config("POSTGRES_USER", default="postgres")
DB_PASSWORD = Secret(Base64Util.decode(config("POSTGRES_PASSWORD", cast=str, default="OTcxMDEx")))
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



