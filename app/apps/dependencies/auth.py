from fastapi import HTTPException, Depends, Security
from fastapi.security import APIKeyHeader

from apps.models import User
from apps.utils.token_ import decode_token
from apps.utils.redis_ import get_redis_client
from redis.asyncio import Redis

bearer_scheme = APIKeyHeader(name="Authorization", auto_error=False)



async def get_current_user(token: str = Security(bearer_scheme), redis_client: Redis = Depends(get_redis_client)):
    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = token.replace("Bearer ", "")
    is_login, info = decode_token(token)
    if not is_login:
        raise HTTPException(status_code=401, detail="token无效")

    user_id = info.get("user_id")
    login_time = info.get("login_time")

    redis_token_key = f"token-{login_time}-{user_id}"
    redis_refresh_key = f"refresh_token-{login_time}-{user_id}"

    # ✅ 使用 await 获取 Redis 中的值
    stored_token = await redis_client.get(redis_token_key)
    if stored_token != token:
        raise HTTPException(status_code=401, detail="登录失效")

    refresh_token = await redis_client.get(redis_refresh_key)
    if refresh_token != token:
        raise HTTPException(status_code=403, detail="请刷新token")

    # ✅ ORM 操作也要 await
    user = await User.get_or_none(id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return user
