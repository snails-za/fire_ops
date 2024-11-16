import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from fastapi import FastAPI

from apps import init_db, init_routes, init_cors, init_static
from apps.middleware.middleware import load_middleware
from config import DEBUG


def create_app():
    app = FastAPI(
        title="FastAPI Demo",
        description="This is a demo project for FastAPI",
        version="0.1",
        debug=DEBUG
    )
    init_static(app)
    init_db(app)
    init_cors(app)
    init_routes(app)
    load_middleware(app)
    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

