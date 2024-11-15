from fastapi import FastAPI

from apps import init_db, init_routes


def create_app():
    app = FastAPI(title="GINO FastAPI Demo")
    init_db(app)
    init_routes(app)
    return app


app = create_app()

