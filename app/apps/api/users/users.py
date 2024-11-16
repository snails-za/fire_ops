from fastapi import APIRouter, HTTPException
from tortoise.contrib.pydantic import pydantic_model_creator

from apps.form.users.form import UserCreate
from apps.models.user import User

router = APIRouter(prefix="/users", tags=["用户管理"])

User_Pydantic = pydantic_model_creator(User, name="User")
UserIn_Pydantic = pydantic_model_creator(User, name="UserIn", exclude_readonly=True)


@router.post("/users/", response_model=User_Pydantic, summary="创建用户")
async def create_user(user: UserCreate):
    user_obj = await User.create(username=user.username, email=user.email,
                                 hashed_password=user.password + "notreallyhashed")
    return await User_Pydantic.from_tortoise_orm(user_obj)


@router.get("/users/{user_id}", response_model=User_Pydantic, summary="用户详情")
async def read_user(user_id: int):
    user = await User_Pydantic.from_queryset_single(User.get(id=user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/users/list", response_model=list[User_Pydantic], summary="用户列表")
async def user_list(username: str = None):
    if username:
        users = await User_Pydantic.from_queryset(User.filter(username=username))
    else:
        users = await User_Pydantic.from_queryset(User.all())
    return users


@router.put("/users/{user_id}", response_model=User_Pydantic, summary="更新用户")
async def update_user(user_id: int, user: UserCreate):
    await User.filter(id=user_id).update(username=user.username, email=user.email, hashed_password=user.password)
    return await User_Pydantic.from_queryset_single(User.get(id=user_id))


@router.delete("/users/{user_id}", response_model=dict, summary="删除用户")
async def delete_user(user_id: int):
    deleted_count = await User.filter(id=user_id).delete()
    return {"deleted": deleted_count}
