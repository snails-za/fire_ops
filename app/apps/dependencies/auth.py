# dependencies/auth.py

from fastapi import Request, HTTPException, Depends
from apps import cache
from apps.models import User
from apps.utils.token_ import decode_token


def get_current_user(request: Request):
    token = request.cookies.get("auth")
    if not token:
        raise HTTPException(status_code=401, detail="未登录")

    is_login, info = decode_token(token)
    if not is_login:
        raise HTTPException(status_code=401, detail="token无效")

    user_id = info.get("user_id")
    login_time = info.get("login_time")

    if cache.get(f"token-{login_time}-{user_id}") != token:
        raise HTTPException(status_code=401, detail="登录失效")

    if cache.get(f"refresh_token-{login_time}-{user_id}") != token:
        raise HTTPException(status_code=403, detail="请刷新token")

    user = User.get(id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return user
