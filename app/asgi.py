import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html, get_redoc_html

from apps.utils.redis_ import RedisManager
from apps import create_app


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up...")
    await RedisManager.init()
    yield
    await RedisManager.close()
    print("Finished up.")

app = create_app(lifespan=lifespan)

# 添加根路径重定向到登录页面
@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/login.html")

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
