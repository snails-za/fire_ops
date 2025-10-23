import base64
import time

from fastapi import Depends, Form, APIRouter
from redis import Redis
from tortoise.contrib.pydantic import pydantic_model_creator

from apps.dependencies.auth import get_token_str, get_current_user
from apps.form.users.form import TokenResponse
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


@router.get("/info", response_model=User_Pydantic, summary="获取用户信息", description="获取当前登录用户信息")
async def get_user_info(user: User = Depends(get_current_user)):
    """
    获取当前登录用户信息
    :param user: 当前登录用户
    :return: 用户信息
    """
    data = await User_Pydantic.from_tortoise_orm(user)
    return response(data=data.model_dump(), message="获取用户信息成功！")

@router.get("/check_login", summary="检查登录状态", description="检查登录状态接口")
async def check_login(user: User = Depends(get_current_user)):
    """
    检查登录状态
    :param user:
    :return:
    """
    data = await User_Pydantic.from_tortoise_orm(user)
    return response(message="已登录", data=data.model_dump())


@router.get("/get_captcha", summary="获取验证码", description="获取验证码接口")
async def get_captcha(redis_client: Redis = Depends(get_redis_client)):
    captcha_image, captcha_id, captcha_text = generate_captcha(130, 35)
    # 存储验证码，有效期为5分钟
    await redis_client.set(captcha_id, captcha_text.lower(), 300)
    # 将图片数据转换为 base64 编码
    base64_image = base64.b64encode(captcha_image).decode('utf-8')
    # 构造一个可以直接嵌入到 HTML 中的图片数据
    base64_string = f"data:image/png;base64,{base64_image}"
    print(captcha_id, captcha_text)
    return response(data={"captcha_id": captcha_id, "captcha": base64_string})


@router.post("/login", summary="前台登录接口", response_model=TokenResponse, description="前台登录接口（普通用户）")
async def login(
        username: str = Form(...),
        password: str = Form(...),
        captcha_text: str = Form(...),
        captcha_id: str = Form(...),
        redis_client: Redis = Depends(get_redis_client)
):
    """
    前台用户登录接口
    只允许普通用户（role=user）登录
    """
    # 验证密码
    decrypt_pwd = decrypt(AES_KEY, password)
    user = await User.get_or_none(username=username, password=get_hash(decrypt_pwd))
    if not user:
        return response(code=401, message="用户名或密码错误")
    
    # 验证码检查
    session_captcha_text = await redis_client.get(captcha_id)
    print(session_captcha_text, captcha_text)
    if not session_captcha_text or session_captcha_text.lower() != captcha_text.lower():
        return response(code=401, message="验证码错误或已过期，请重新获取验证码！")
    # 删除验证码，避免重复使用
    await redis_client.delete(captcha_id)
    
    # 检查用户角色，只允许普通用户登录前台
    # if user.role != "user":
    #     return response(code=403, message="管理员请使用后台登录接口")
    
    # 登录成功，返回用户信息
    login_time = time.time()
    token = gen_token(user.id, login_time, seconds=MAX_AGE)
    await redis_client.set(f"token-{login_time}-{user.id}", token, MAX_AGE)
    await redis_client.set(f"refresh_token-{login_time}-{user.id}", token, REFRESH_MAX_AGE)
    
    resp = {
        "access_token": token,
        "token_type": "bearer",
        "user_role": user.role
    }
    return response(data=resp, message="登录成功！")


@router.post("/admin/login", summary="后台登录接口", response_model=TokenResponse, description="后台登录接口（管理员）")
async def admin_login(
        username: str = Form(...),
        password: str = Form(...),
        captcha_text: str = Form(...),
        captcha_id: str = Form(...),
        redis_client: Redis = Depends(get_redis_client)
):
    """
    后台管理员登录接口
    只允许管理员（role=admin）登录
    """
    # 验证密码
    decrypt_pwd = decrypt(AES_KEY, password)
    user = await User.get_or_none(username=username, password=get_hash(decrypt_pwd))
    if not user:
        return response(code=401, message="用户名或密码错误")
    
    # 验证码检查
    session_captcha_text = await redis_client.get(captcha_id)
    print(session_captcha_text, captcha_text)
    if not session_captcha_text or session_captcha_text.lower() != captcha_text.lower():
        return response(code=401, message="验证码错误或已过期，请重新获取验证码！")
    # 删除验证码，避免重复使用
    await redis_client.delete(captcha_id)
    
    # 检查用户角色，只允许管理员登录后台
    if user.role != "admin":
        return response(code=403, message="普通用户无法登录后台管理系统，请使用前台登录")
    
    # 登录成功，生成token
    login_time = time.time()
    token = gen_token(user.id, login_time, seconds=MAX_AGE)
    await redis_client.set(f"token-{login_time}-{user.id}", token, MAX_AGE)
    await redis_client.set(f"refresh_token-{login_time}-{user.id}", token, REFRESH_MAX_AGE)
    
    resp = {
        "access_token": token,
        "token_type": "bearer",
        "user_role": user.role
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
    # 删除Redis中的token
    await redis_client.delete(f"token-{login_time}-{user_id}")
    await redis_client.delete(f"refresh_token-{login_time}-{user_id}")
    # 重新生成token
    login_time = time.time()
    new_token = gen_token(user_id, login_time, seconds=MAX_AGE)
    await redis_client.set(f"token-{login_time}-{user_id}", new_token, MAX_AGE)
    await redis_client.set(f"refresh_token-{login_time}-{user_id}", new_token, REFRESH_MAX_AGE)
    resp = {
        "access_token": new_token,
        "token_type": "bearer"
    }
    return response(data=resp, message="刷新token成功！")
