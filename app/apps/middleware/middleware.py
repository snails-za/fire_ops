import time
from fastapi import Request


def load_middleware(app):
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        print(f"Process time: {process_time}")
        return response
