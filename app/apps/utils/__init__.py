from typing import Any, Optional

from fastapi.responses import JSONResponse


def serialize_data(data: Any) -> Any:
    # 自动处理 Pydantic 模型或模型列表
    if isinstance(data, list):
        return [d.dict() if hasattr(d, "dict") else d for d in data]
    if hasattr(data, "dict"):
        return data.dict()
    return data


def response(
        data: Optional[Any] = None,
        code: int = 200,
        message: str = "success",
        status_code: int = 200
) -> JSONResponse:
    resp = {
        "code": code,
        "message": message,
        "data": serialize_data(data)
    }
    return JSONResponse(content=resp, status_code=status_code)
