from datetime import datetime, date
from typing import Optional, Any

from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse


def response(
        data: Optional[Any] = None,
        code: int = 200,
        message: str = "success",
        status_code: int = 200,
        **kwargs
) -> JSONResponse:
    resp = {
        "code": code,
        "message": message,
        "data": jsonable_encoder(data,
                                 custom_encoder={
                                     datetime: lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S"),
                                     date: lambda d: d.strftime("%Y-%m-%d")
                                 }),
        **kwargs
    }
    return JSONResponse(content=resp, status_code=status_code)
