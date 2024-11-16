import os
import importlib

from fastapi import APIRouter
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html, get_redoc_html
from gino_starlette import Gino
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

import config

db = Gino(
    dsn=config.DB_DSN,
    pool_min_size=config.DB_POOL_MIN_SIZE,
    pool_max_size=config.DB_POOL_MAX_SIZE,
    echo=config.DB_ECHO,
    ssl=config.DB_SSL,
    use_connection_for_request=config.DB_USE_CONNECTION_FOR_REQUEST,
    retry_limit=config.DB_RETRY_LIMIT,
    retry_interval=config.DB_RETRY_INTERVAL,
)
router = APIRouter()


def init_static(app):
    app.mount("/static", StaticFiles(directory=config.STATIC_PATH), name="static")


def init_db(app):
    db.init_app(app)


def init_cors(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def init_routes(app):
    api_dir = os.path.join(os.path.dirname(__file__), 'api')
    exclude_dirs = ['__pycache__']

    # 使用 os.walk 遍历所有子目录和文件
    for root, dirs, files in os.walk(api_dir):
        # 检查当前目录名是否在排除列表中
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        # 将文件路径转换为包名
        package_name = root.replace(api_dir, 'apps.api').replace(os.sep, '.')
        for filename in files:
            # 只处理 .py 文件，且排除 __init__.py 文件
            if filename.endswith('.py') and filename != '__init__.py':
                module_name = f"{package_name}.{filename[:-3]}"
                module = importlib.import_module(module_name)
                if hasattr(module, 'router'):
                    app.include_router(module.router, prefix="/api/v1")





