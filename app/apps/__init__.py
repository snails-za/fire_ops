import os
import importlib

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from config import DEBUG, STATIC_PATH, BASE_PATH

# 执行 Aerich 补丁以拦截 DROP 操作，防止迁移误删表字段。
from apps.utils import aerich_patch as aerich_patch


def init_static(app):
    app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")
    app.mount(
        "/data", StaticFiles(directory=os.path.join(BASE_PATH, "data")), name="data"
    )


def init_cors(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def init_routes(app):
    api_dir = os.path.join(os.path.dirname(__file__), "api")
    exclude_dirs = ["__pycache__"]

    for root, dirs, files in os.walk(api_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        package_name = root.replace(api_dir, "apps.api").replace(os.sep, ".")
        for filename in files:
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = f"{package_name}.{filename[:-3]}"
                module = importlib.import_module(module_name)
                if hasattr(module, "router"):
                    app.include_router(module.router, prefix="/api/v1")


def custom_openapi(app: FastAPI):
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
    }

    openapi_schema["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def create_app(lifespan=None):
    app = FastAPI(
        title="FastAPI Demo",
        description="This is a demo project for FastAPI",
        version="0.1",
        debug=DEBUG,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    init_static(app)
    init_cors(app)
    init_routes(app)

    app.openapi = lambda: custom_openapi(app)
    return app
