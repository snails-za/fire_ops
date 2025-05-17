import time
from typing import Union, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials
from redis import Redis
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.expressions import Q

from apps.dependencies.auth import get_current_user, bearer_scheme, get_token_str
from apps.form.users.form import UserCreate, TokenResponse
from apps.models.user import User
from apps.utils import response
from apps.utils.aes_helper import decrypt
from apps.utils.common import get_hash
from apps.utils.redis_ import get_redis_client
from apps.utils.token_ import gen_token, decode_token
from config import AES_KEY, MAX_AGE, REFLESH_MAX_AGE

router = APIRouter(prefix="/users", tags=["用户管理"])

User_Pydantic = pydantic_model_creator(User, name="User", exclude=("hashed_password",))


@router.get("/list", summary="用户列表", description="获取用户列表", dependencies=[Depends(get_current_user)])
async def user_list(username: Optional[str] = None, page: int = 1, page_size: int = 10):
    conditions = []
    if username:
        conditions.append(Q(username__icontains=username))

    query = User.filter(*conditions).order_by("-id")
    total = await query.count()
    total_page = total // page_size + (1 if total % page_size > 0 else 0)
    items = await User_Pydantic.from_queryset(query.offset((page - 1) * page_size).limit(page_size))
    data = [_.model_dump() for _ in items]
    return response(data=data, total=total, total_page=total_page, message="获取用户列表成功！")


@router.post("/register/", response_model=User_Pydantic, summary="注册用户", description="创建用户接口",
             dependencies=[Depends(get_current_user)])
async def create_user(user: UserCreate):
    # 判断用户名或邮箱是否已经被注册
    if await User.filter(Q(username=user.username) | Q(email=user.email)).exists():
        return response(code=0, message="用户名或邮箱已经被注册！")
    try:
        decrypt_pwd = decrypt(AES_KEY, user.password)
    except Exception as e:
        print(e)
        return response(code=0, message="密码参数错误！")
    user_obj = await User.create(username=user.username, email=user.email,
                                 hashed_password=get_hash(decrypt_pwd))
    data = await User_Pydantic.from_tortoise_orm(user_obj)
    return response(data=data.model_dump(), message="注册成功！")


@router.put("/update/{user_id}", response_model=User_Pydantic, summary="更新用户", description="更新用户信息",
            dependencies=[Depends(get_current_user)])
async def update_user(user_id: int, user: UserCreate):
    if await User.filter(Q(username=user.username) | Q(email=user.email)).exclude(id=user_id).exists():
        return response(code=0, message="用户名或邮箱已经被注册！")
    try:
        decrypt_pwd = decrypt(AES_KEY, user.password)
    except Exception as e:
        return response(code=0, message="密码参数错误！")

    await User.filter(id=user_id).update(
        username=user.username,
        email=user.email,
        hashed_password=get_hash(decrypt_pwd)
    )
    user_obj = await User.get(id=user_id)
    data = await User_Pydantic.from_tortoise_orm(user_obj)
    return response(data=data.model_dump(), message="更新成功！")


@router.get("/detail/{user_id}", response_model=User_Pydantic, summary="用户详情", description="获取用户详情",
            dependencies=[Depends(get_current_user)])
async def read_user(user_id: int):
    user = await User.get_or_none(id=user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    data = await User_Pydantic.from_tortoise_orm(user)
    return response(data=data.model_dump())


@router.delete("/delete/{user_id}", response_model=dict, summary="删除用户", description="删除用户",
               dependencies=[Depends(get_current_user)])
async def delete_user(user_id: int, user: User = Depends(get_current_user)):
    if user.id == user_id:
        return response(code=0, message="不允许删除自身账号！")
    user_id = await User.filter(id=user_id).delete()
    return response(data={"id": user_id})


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
