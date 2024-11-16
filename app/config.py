import os

from starlette.config import Config
from pydantic import Secret

from apps.utils.common import Base64Util

config = Config()

DEBUG = config("DEBUG", cast=bool, default=False)
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
STATIC_PATH = os.path.join(BASE_PATH, "static")
# 数据库配置
DB_DRIVER = config("DB_DRIVER", default="postgresql")
DB_HOST = config("DB_HOST", default="localhost")
DB_PORT = config("DB_PORT", cast=int, default=15432)
DB_USER = config("DB_USER", default="postgres")
DB_PASSWORD = Secret(Base64Util.decode(config("DB_PASSWORD", cast=str, default="OTcxMDEx")))
DB_DATABASE = config("DB_DATABASE", default="fastapi_demo")



