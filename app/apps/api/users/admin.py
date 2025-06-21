import os
import random
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.expressions import Q

from apps.dependencies.auth import get_current_user
from apps.form.users.form import UserCreate
from apps.models.user import User, Contact
from apps.utils import response
from apps.utils.aes_helper import decrypt
from apps.utils.common import get_hash, get_pinyin
from config import AES_KEY, STATIC_PATH

router = APIRouter(prefix="/admin", tags=["用户管理"])

User_Pydantic = pydantic_model_creator(User, name="User", exclude=("password",))


@router.post("/upload/image", summary="图像上传接口", description="图像上传接口", dependencies=[Depends(get_current_user)])
async def upload_image(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[-1]
    filename = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(STATIC_PATH, "images", "user", filename)

    with open(save_path, "wb") as f:
        f.write(await file.read())

    return response(data={"filepath": os.path.join("/", "static", "images", "user", filename)}, message="上传成功")


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


@router.post("/register", response_model=User_Pydantic, summary="注册用户", description="创建用户接口")
async def create_user(user: UserCreate):
    # 判断用户名是否已经被注册
    if await User.filter(Q(username=user.username)).exists():
        return response(code=0, message="用户名已经被注册！")
    try:
        decrypt_pwd = decrypt(AES_KEY, user.password)
    except Exception as e:
        print(e)
        return response(code=0, message="密码参数错误！")
    heads = os.listdir(os.path.join(STATIC_PATH, "images", "user", "demo"))
    user_obj = await User.create(username=user.username, email=user.email, pinyin=get_pinyin(user.username),
                                 password=get_hash(decrypt_pwd), head=os.path.join("/", "static", "images", "user", "demo", random.choice(heads)))
    data = await User_Pydantic.from_tortoise_orm(user_obj)
    return response(data=data.model_dump(), message="注册成功！")


@router.put("/update/{user_id}", response_model=User_Pydantic, summary="更新用户", description="更新用户信息",
            dependencies=[Depends(get_current_user)])
async def update_user(user_id: int, user: UserCreate):
    if await User.filter(Q(username=user.username)).exclude(id=user_id).exists():
        return response(code=0, message="用户名已经被注册！")
    try:
        decrypt_pwd = decrypt(AES_KEY, user.password)
    except Exception as e:
        return response(code=0, message="密码参数错误！")
    await User.filter(id=user_id).update(
        username=user.username,
        pinyin=get_pinyin(user.username),
        email=user.email,
        password=get_hash(decrypt_pwd)
    )
    if user.head:
        await User.filter(id=user_id).update(head=user.head)
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


@router.post("/add/contact/{user_id}", summary="添加联系人", description="添加联系人", dependencies=[Depends(get_current_user)])
async def add_contact(user_id: int, user: User = Depends(get_current_user)):
    if user.id == user_id:
        return response(code=0, message="不允许添加自己为联系人！")
    contact_user = await User.get_or_none(id=user_id)
    if not contact_user:
        return response(code=0, message="用户不存在！")
    if await Contact.filter(user=user, contact=contact_user).exists():
        return response(code=0, message="联系人已存在！")
    # 这里可以添加添加联系人逻辑
    await Contact.create(user=user, contact=contact_user)
    return response(message="联系人添加成功！")


@router.get("/contacts", summary="获取联系人列表", description="获取联系人列表", dependencies=[Depends(get_current_user)])
async def get_contacts(user: User = Depends(get_current_user)):
    contacts = await Contact.filter(user=user).prefetch_related("contact")
    contact_list = []
    for item in contacts:
        obj = await User_Pydantic.from_tortoise_orm(item.contact)
        contact = obj.model_dump()
        contact["is_star"] = item.is_star
        contact_list.append(contact)
    return response(data=contact_list, message="获取联系人列表成功！")


@router.delete("/contact/{contact_id}", summary="删除联系人", description="删除联系人", dependencies=[Depends(get_current_user)])
async def delete_contact(contact_id: int, user: User = Depends(get_current_user)):
    contact = await Contact.get_or_none(user=user, contact_id=contact_id)
    if not contact:
        return response(code=0, message="联系人不存在！")
    if contact.contact.id == user.id:
        return response(code=0, message="不允许删除自己为联系人！")
    await contact.delete()
    return response(message="联系人删除成功！")
