from fastapi import APIRouter, HTTPException
from tortoise.contrib.pydantic import pydantic_model_creator

from apps.form.users.form import UserCreate
from apps.models.user import User

router = APIRouter(prefix="/users", tags=["用户管理"])

User_Pydantic = pydantic_model_creator(User, name="User")
UserIn_Pydantic = pydantic_model_creator(User, name="UserIn", exclude_readonly=True)


@router.post("/users/", response_model=User_Pydantic)
async def create_user(user: UserCreate):
    user_obj = await User.create(username=user.username, email=user.email,
                                 hashed_password=user.password + "notreallyhashed")
    return await User_Pydantic.from_tortoise_orm(user_obj)


@router.get("/users/{user_id}", response_model=User_Pydantic)
async def read_user(user_id: int):
    user = await User_Pydantic.from_queryset_single(User.get(id=user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
