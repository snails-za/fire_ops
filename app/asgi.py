from fastapi import FastAPI

from apps import init_db, init_routes, init_cors
from apps.middleware.middleware import load_middleware


def create_app():
    app = FastAPI(title="GINO FastAPI Demo")
    init_db(app)
    init_cors(app)
    init_routes(app)
    load_middleware(app)
    return app


app = create_app()

