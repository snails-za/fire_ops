import os
import importlib

from fastapi import APIRouter
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from tortoise.contrib.fastapi import register_tortoise

import config

router = APIRouter()


def init_db(app):
    print(config.TORTOISE_ORM)
    register_tortoise(
        app,
        config=config.TORTOISE_ORM,
        add_exception_handlers=True
    )



def init_static(app):
    app.mount("/static", StaticFiles(directory=config.STATIC_PATH), name="static")


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





