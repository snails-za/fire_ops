from fastapi import HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from apps.models.user import User
from apps.utils.token_ import decode_token
from apps.utils.redis_ import get_redis_client
from redis.asyncio import Redis

bearer_scheme = HTTPBearer(scheme_name="BearerAuth", auto_error=True)  # ✅ 让它匹配你 openapi 中定义的名称



def get_token_str(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
) -> str:
    """
    安全地获取 Bearer Token 字符串。
    """
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="无效的认证方式（必须是 Bearer）"
        )
    return credentials.credentials


async def get_current_user(token: HTTPAuthorizationCredentials = Security(bearer_scheme), redis_client: Redis = Depends(get_redis_client)):
    # ✅ 直接获取 token 的值
    token = token.credentials
    if not token:
        raise HTTPException(status_code=401, detail="登录失效， 请重新登录！")
    token = token.replace("Bearer ", "")
    is_login, info = decode_token(token)
    if not is_login:
        raise HTTPException(status_code=401, detail="登录失效， 请重新登录！")

    user_id = info.get("user_id")
    login_time = info.get("login_time")

    redis_token_key = f"token-{login_time}-{user_id}"
    redis_refresh_key = f"refresh_token-{login_time}-{user_id}"

    # ✅ 使用 await 获取 Redis 中的值
    stored_token = await redis_client.get(redis_token_key)
    if stored_token != token:
        raise HTTPException(status_code=401, detail="登录失效， 请重新登录！")

    refresh_token = await redis_client.get(redis_refresh_key)
    if refresh_token != token:
        raise HTTPException(status_code=403, detail="请刷新token")

    # ✅ ORM 操作也要 await
    user = await User.get_or_none(id=user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在! 请重新登录")

    return user
