import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html, get_redoc_html

from tortoise import Tortoise
from apps.utils.redis_ import RedisManager
from apps.models.user import User
from apps.utils.common import get_hash, get_pinyin
from apps import create_app
from config import (
    INITIAL_ADMIN_FULLNAME,
    INITIAL_ADMIN_PASSWORD,
    INITIAL_ADMIN_USERNAME,
    STATIC_PATH,
    TORTOISE_ORM,
)


def get_default_admin_head():
    demo_dir = os.path.join(STATIC_PATH, "images", "user", "demo")
    if not os.path.isdir(demo_dir):
        return None

    heads = sorted(
        filename
        for filename in os.listdir(demo_dir)
        if not filename.startswith(".")
    )
    if not heads:
        return None

    return os.path.join("/", "static", "images", "user", "demo", heads[0])


async def ensure_initial_admin():
    admin = await User.get_or_none(username=INITIAL_ADMIN_USERNAME)
    if admin:
        if not admin.head:
            admin.head = get_default_admin_head()
            await admin.save(update_fields=["head"])
        return

    password = INITIAL_ADMIN_PASSWORD.get_secret_value()
    await User.create(
        username=INITIAL_ADMIN_USERNAME,
        fullname=INITIAL_ADMIN_FULLNAME,
        password=get_hash(password),
        head=get_default_admin_head(),
        pinyin=get_pinyin(INITIAL_ADMIN_FULLNAME or INITIAL_ADMIN_USERNAME),
        role="admin",
    )
    print(f"✅ 已创建初始管理员账号：{INITIAL_ADMIN_USERNAME}，请登录后尽快修改密码")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up...")
    # 初始化 Tortoise ORM
    await Tortoise.init(config=TORTOISE_ORM)
    await ensure_initial_admin()
    print("✅ 数据库初始化完成")

    # 初始化 Redis
    await RedisManager.init()
    print("✅ Redis 初始化完成")
    
    yield
    
    # 关闭连接
    await RedisManager.close()
    await Tortoise.close_connections()
    print("✅ Finished up.")

app = create_app(lifespan=lifespan)

# 添加根路径重定向到登录页面
@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/admin.html")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="static/js/swagger-ui-bundle.js",
        swagger_css_url="static/css/swagger-ui.css",
        swagger_favicon_url="static/images/favicon.ico",
    )


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="static/js/redoc.standalone.js",
        redoc_favicon_url="static/images/favicon.ico",
        with_google_fonts=False,
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
