from typing import Union, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, Response
from tortoise.contrib.pydantic import pydantic_model_creator

from apps.form.users.form import UserCreate
from apps.models.user import User

router = APIRouter(prefix="/users", tags=["用户管理"])

User_Pydantic = pydantic_model_creator(User, name="User")
UserIn_Pydantic = pydantic_model_creator(User, name="UserIn", exclude_readonly=True)


@router.post("/create/", response_model=User_Pydantic, summary="创建用户")
async def create_user(user: UserCreate):
    user_obj = await User.create(username=user.username, email=user.email,
                                 hashed_password=user.password + "notreallyhashed")
    return await User_Pydantic.from_tortoise_orm(user_obj)


@router.get("/detail/{user_id}", response_model=User_Pydantic, summary="用户详情")
async def read_user(user_id: int):
    user = await User_Pydantic.from_queryset_single(User.get(id=user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/list", response_model=list[User_Pydantic], summary="用户列表")
async def user_list(username: Optional[str] = None):
    if username:
        users = await User_Pydantic.from_queryset(User.filter(username=username))
    else:
        users = await User_Pydantic.from_queryset(User.all())
    return users


@router.put("/update/{user_id}", response_model=User_Pydantic, summary="更新用户")
async def update_user(user_id: int, user: UserCreate):
    await User.filter(id=user_id).update(username=user.username, email=user.email, hashed_password=user.password)
    return await User_Pydantic.from_queryset_single(User.get(id=user_id))


@router.delete("/delete/{user_id}", response_model=dict, summary="删除用户")
async def delete_user(user_id: int):
    deleted_count = await User.filter(id=user_id).delete()
    return {"deleted": deleted_count}


@router.post("/uploadfile", summary="上传文件测试")
async def upload_file(filename: Union[str, None] = None, file: UploadFile = File(...)):
    print(filename)
    return {"filename": file.filename}


@router.get("/form", summary="获取表单数据")
async def get_form(username: Optional[str] = Form(default=None, description="用户名"), email: Optional[str] = Form(...)):
    return JSONResponse(content={"username": username, "email": email}, status_code=200)
