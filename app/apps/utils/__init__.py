from fastapi.responses import JSONResponse


def response(data=None, code: int = 200, message="success", status_code: int = 200):
    resp = {
        "code": code,
        "message": message,
        "data": data
    }
    return JSONResponse(content=resp, status_code=status_code)
