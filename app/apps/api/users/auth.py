import base64
import time

from fastapi import Depends, Form, APIRouter
from redis import Redis
from tortoise.contrib.pydantic import pydantic_model_creator

from apps.dependencies.auth import get_token_str, get_current_user
from apps.dependencies.permissions import effective_role, is_admin
from apps.form.users.form import ChangePasswordForm, TokenResponse
from apps.models.user import User
from apps.utils import response
from apps.utils.aes_helper import decrypt
from apps.utils.common import get_hash
from apps.utils.generate_captcha import generate_captcha
from apps.utils.redis_ import get_redis_client
from apps.utils.token_ import gen_token, decode_token
from config import AES_KEY, MAX_AGE, REFRESH_MAX_AGE

router = APIRouter(prefix="/auth", tags=["用户认证"])
User_Pydantic = pydantic_model_creator(User, name="User", exclude=("password",))


@router.get(
    "/info",
    response_model=User_Pydantic,
    summary="获取用户信息",
    description="获取当前登录用户信息",
)
async def get_user_info(user: User = Depends(get_current_user)):
    data = await User_Pydantic.from_tortoise_orm(user)
    return response(data=data.model_dump(), message="获取用户信息成功！")


@router.get("/check_login", summary="检查登录状态", description="检查登录状态接口")
async def check_login(user: User = Depends(get_current_user)):
    data = await User_Pydantic.from_tortoise_orm(user)
    return response(message="已登录", data=data.model_dump())


@router.put(
    "/change_password",
    summary="修改当前用户密码",
    dependencies=[Depends(get_current_user)],
)
async def change_password(
    form: ChangePasswordForm, user: User = Depends(get_current_user)
):
    try:
        old_password = decrypt(AES_KEY, form.old_password)
        new_password = decrypt(AES_KEY, form.new_password)
    except Exception:
        return response(code=0, message="密码参数错误！")

    if user.password != get_hash(old_password):
        return response(code=0, message="原密码不正确")

    user.password = get_hash(new_password)
    await user.save()
    return response(message="密码修改成功！")


@router.get("/get_captcha", summary="获取验证码", description="获取验证码接口")
async def get_captcha(redis_client: Redis = Depends(get_redis_client)):
    captcha_image, captcha_id, captcha_text = generate_captcha(130, 35)
    await redis_client.set(captcha_id, captcha_text.lower(), 300)
    base64_image = base64.b64encode(captcha_image).decode("utf-8")
    base64_string = f"data:image/png;base64,{base64_image}"
    return response(data={"captcha_id": captcha_id, "captcha": base64_string})


@router.post(
    "/login",
    summary="前台登录接口",
    response_model=TokenResponse,
    description="前台登录接口（App：管理员/班长/维护人员）",
)
async def login(
    username: str = Form(...),
    password: str = Form(...),
    captcha_text: str = Form(...),
    captcha_id: str = Form(...),
    redis_client: Redis = Depends(get_redis_client),
):
    decrypt_pwd = decrypt(AES_KEY, password)
    user = await User.get_or_none(username=username, password=get_hash(decrypt_pwd))
    if not user:
        return response(code=401, message="用户名或密码错误")

    session_captcha_text = await redis_client.get(captcha_id)
    if not session_captcha_text or session_captcha_text.lower() != captcha_text.lower():
        return response(code=401, message="验证码错误或已过期，请重新获取验证码！")
    await redis_client.delete(captcha_id)

    login_time = time.time()
    token = gen_token(user.id, login_time, seconds=MAX_AGE)
    await redis_client.set(f"token-{login_time}-{user.id}", token, MAX_AGE)
    await redis_client.set(
        f"refresh_token-{login_time}-{user.id}", token, REFRESH_MAX_AGE
    )

    resp = {
        "access_token": token,
        "token_type": "bearer",
        "user_role": effective_role(user),
    }
    return response(data=resp, message="登录成功！")


@router.post(
    "/admin/login",
    summary="后台登录接口",
    response_model=TokenResponse,
    description="后台登录接口（管理员）",
)
async def admin_login(
    username: str = Form(...),
    password: str = Form(...),
    captcha_text: str = Form(...),
    captcha_id: str = Form(...),
    redis_client: Redis = Depends(get_redis_client),
):
    decrypt_pwd = decrypt(AES_KEY, password)
    user = await User.get_or_none(username=username, password=get_hash(decrypt_pwd))
    if not user:
        return response(code=401, message="用户名或密码错误")

    session_captcha_text = await redis_client.get(captcha_id)
    if not session_captcha_text or session_captcha_text.lower() != captcha_text.lower():
        return response(code=401, message="验证码错误或已过期，请重新获取验证码！")
    await redis_client.delete(captcha_id)

    if not is_admin(user):
        return response(
            code=403, message="仅管理员可登录后台管理系统，请使用 App 登录"
        )

    login_time = time.time()
    token = gen_token(user.id, login_time, seconds=MAX_AGE)
    await redis_client.set(f"token-{login_time}-{user.id}", token, MAX_AGE)
    await redis_client.set(
        f"refresh_token-{login_time}-{user.id}", token, REFRESH_MAX_AGE
    )

    resp = {
        "access_token": token,
        "token_type": "bearer",
        "user_role": effective_role(user),
    }
    return response(data=resp, message="登录成功！")


@router.get(
    "/logout",
    summary="注销接口",
    description="注销接口",
    dependencies=[Depends(get_current_user)],
)
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
    await redis_client.delete(f"token-{login_time}-{user_id}")
    await redis_client.delete(f"refresh_token-{login_time}-{user_id}")
    return response(message="注销成功！")


@router.get("/refresh_token", summary="刷新token", description="刷新token接口")
async def refresh_token(
    redis_client: Redis = Depends(get_redis_client),
    token: str = Depends(get_token_str),
):
    is_login, info = decode_token(token)
    if not is_login:
        return response(code=0, message="登录失效！请重新登录！")
    user_id = info.get("user_id")
    login_time = info.get("login_time")
    await redis_client.delete(f"token-{login_time}-{user_id}")
    await redis_client.delete(f"refresh_token-{login_time}-{user_id}")
    login_time = time.time()
    new_token = gen_token(user_id, login_time, seconds=MAX_AGE)
    await redis_client.set(f"token-{login_time}-{user_id}", new_token, MAX_AGE)
    await redis_client.set(
        f"refresh_token-{login_time}-{user_id}", new_token, REFRESH_MAX_AGE
    )
    resp = {"access_token": new_token, "token_type": "bearer"}
    return response(data=resp, message="刷新token成功！")
