import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html, get_redoc_html

from apps import init_routes, init_cors, init_static, init_db
from config import DEBUG


def create_app():
    app = FastAPI(
        title="FastAPI Demo",
        description="This is a demo project for FastAPI",
        version="0.1",
        debug=DEBUG,
        docs_url=None,
        redoc_url=None
    )
    init_static(app)
    init_cors(app)
    init_db(app)
    init_routes(app)
    return app


app = create_app()


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="static/swagger-ui-bundle.js",
        swagger_css_url="static/swagger-ui.css",
        swagger_favicon_url="static/favicon.ico",
    )


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="static/redoc.standalone.js",
        redoc_favicon_url="static/favicon.ico",
        with_google_fonts=False,
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
