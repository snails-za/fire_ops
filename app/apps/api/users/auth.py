import time

from fastapi import Depends, Form, APIRouter
from redis import Redis

from apps.dependencies.auth import get_token_str, get_current_user
from apps.form.users.form import TokenResponse
from apps.models import User
from apps.utils import response
from apps.utils.aes_helper import decrypt
from apps.utils.common import get_hash
from apps.utils.redis_ import get_redis_client
from apps.utils.token_ import gen_token, decode_token
from config import AES_KEY, MAX_AGE, REFLESH_MAX_AGE

router = APIRouter(prefix="/admin", tags=["用户管理"])


@router.post("/login", summary="登录接口", response_model=TokenResponse, description="登录接口")
async def login(username: str = Form(...), password: str = Form(...), redis_client: Redis = Depends(get_redis_client)):
    # 这里可以添加登录逻辑
    print(username, password)
    decrypt_pwd = decrypt(AES_KEY, password)
    user = await User.get_or_none(username=username, hashed_password=get_hash(decrypt_pwd))
    if not user:
        return response(code=0, message="用户名或密码错误")
    # 登录成功，返回用户信息
    login_time = time.time()
    token = gen_token(user.id, login_time, seconds=MAX_AGE)
    await redis_client.set(f"token-{login_time}-{user.id}", token, MAX_AGE)
    await redis_client.set(f"refresh_token-{login_time}-{user.id}", token, REFLESH_MAX_AGE)
    resp = {
        "access_token": f"Bearer {token}",
        "token_type": "bearer"
    }
    return response(data=resp, message="登录成功！")


@router.get("/logout", summary="注销接口", description="注销接口", dependencies=[Depends(get_current_user)])
async def logout(
        redis_client: Redis = Depends(get_redis_client),
        token: str = Depends(get_token_str),
):
    if not token:
        return response(code=0, message="未登录")
    is_login, info = decode_token(token)
    if not is_login:
        return response(code=0, message="登录失效！请重新登录！")
    user_id = info.get("user_id")
    login_time = info.get("login_time")
    # 删除Redis中的token
    await redis_client.delete(f"token-{login_time}-{user_id}")
    await redis_client.delete(f"refresh_token-{login_time}-{user_id}")
    return response(message="注销成功！")
