import os
import random
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.expressions import Q

from apps.dependencies.auth import get_current_user
from apps.dependencies.permissions import check_admin_permission
from apps.form.users.form import UserCreate, UserUpdate, ProcessApplyRequest
from apps.models.user import User, FriendRequest
from apps.utils import response
from apps.utils.aes_helper import decrypt
from apps.utils.common import get_hash, get_pinyin
from config import AES_KEY, STATIC_PATH, AVATAR_STORE_PATH

router = APIRouter(prefix="/admin", tags=["用户管理"])

User_Pydantic = pydantic_model_creator(User, name="User", exclude=("password",))


@router.post("/upload/image", summary="图像上传接口", description="图像上传接口", dependencies=[Depends(get_current_user)])
async def upload_image(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[-1]
    filename = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(AVATAR_STORE_PATH, filename)

    # 确保目录存在
    os.makedirs(AVATAR_STORE_PATH, exist_ok=True)

    with open(save_path, "wb") as f:
        f.write(await file.read())

    return response(data={"filepath": os.path.join("/", "data", "head", filename)}, message="上传成功")


@router.get("/list", summary="用户列表", description="获取用户列表", dependencies=[Depends(check_admin_permission)])
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
                                 password=get_hash(decrypt_pwd), head=os.path.join("/", "static", "images", "user", "demo", random.choice(heads)), role=user.role)
    data = await User_Pydantic.from_tortoise_orm(user_obj)
    return response(data=data.model_dump(), message="注册成功！")


@router.put("/update/{user_id}", response_model=User_Pydantic, summary="更新用户", description="更新用户信息",
            dependencies=[Depends(get_current_user)])
async def update_user(user_id: int, user: UserUpdate):
    if await User.filter(Q(username=user.username)).exclude(id=user_id).exists():
        return response(code=0, message="用户名已经被注册！")
    
    # 构建更新数据
    update_data = {
        "username": user.username,
        "pinyin": get_pinyin(user.username),
        "email": user.email,
    }

    # 更新头像（如果提供）
    if user.head:
        update_data["head"] = user.head

    # 只有传入密码时才更新密码
    if user.password:
        try:
            decrypt_pwd = decrypt(AES_KEY, user.password)
            update_data["password"] = get_hash(decrypt_pwd)
        except Exception as _:
            return response(code=0, message="密码参数错误！")
    
    # 更新基本信息
    update_data["updated_at"] = datetime.now()
    print(datetime.now())
    await User.filter(id=user_id).update(**update_data)
    
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
               dependencies=[Depends(check_admin_permission)])
async def delete_user(user_id: int, user: User = Depends(get_current_user)):
    if user.id == user_id:
        return response(code=0, message="不允许删除自身账号！")
    user_id = await User.filter(id=user_id).delete()
    return response(data={"id": user_id})


@router.post("/add/contact/{user_id}", summary="添加联系人", description="添加联系人", dependencies=[Depends(get_current_user)])
async def add_contact(user_id: int, bak: Optional[str] = None, user: User = Depends(get_current_user)):
    if user.id == user_id:
        return response(code=0, message="不允许添加自己为联系人！")
    contact_user = await User.get_or_none(id=user_id)
    if not contact_user:
        return response(code=0, message="用户不存在！")
    if await FriendRequest.filter(Q(requester=user, receiver=contact_user) | Q(requester=contact_user, receiver=user), is_accept=True).exists():
        return response(code=0, message="联系人已存在！")
    if  await FriendRequest.filter(requester=contact_user, receiver=user, is_accept=None).exists():
        return response(code=0, message="对方已经向您发起好友申请！请处理申请！")
    if  await FriendRequest.filter(requester=user, receiver=contact_user, is_accept=None).exists():
        return response(message="联系人添加成功！等待通过审核！")
    # 这里可以添加添加联系人逻辑
    await FriendRequest.create(requester=user, receiver=contact_user, bak=bak)
    return response(message="联系人添加成功！等待通过审核！")


@router.get("/contacts", summary="获取联系人列表", description="获取联系人列表", dependencies=[Depends(get_current_user)])
async def get_contacts(user: User = Depends(get_current_user)):
    requests = await FriendRequest.filter(
        Q(requester=user) | Q(receiver=user),
        is_accept=True
      ).prefetch_related("requester", "receiver")
    friends = []
    for req in requests:
        if req.requester.id == user.id:
            friend_user = req.receiver
        else:
            friend_user = req.requester
        friend = await User_Pydantic.from_tortoise_orm(friend_user)
        friend_data = friend.model_dump()
        # 添加 is_star 字段
        friend_data["is_star"] = req.is_star
        friends.append(friend_data)
    return response(data=friends, message="获取联系人列表成功！")


@router.delete("/contact/{contact_id}", summary="删除联系人", description="删除联系人", dependencies=[Depends(get_current_user)])
async def delete_contact(contact_id: int, user: User = Depends(get_current_user)):
    contact = await FriendRequest.get_or_none(requester=user, receiver=contact_id)
    if not contact:
        return response(code=0, message="联系人不存在！")
    if contact.receiver.id == user.id:
        return response(code=0, message="不允许删除自己为联系人！")
    await contact.delete()
    return response(message="联系人删除成功！")

@router.get("/contacts/apply", summary="获取联系人申请列表", description="获取联系人申请列表", dependencies=[Depends(get_current_user)])
async def get_contacts_apply(user: User = Depends(get_current_user)):
    res = {"processed": [], "wait_processed": []}
    requests = await FriendRequest.filter(receiver=user.id).order_by("-id").prefetch_related("requester", "receiver")
    for req in requests:
        friend = await User_Pydantic.from_tortoise_orm(req.requester)
        friend_data = friend.model_dump()
        friend_data["id"] = req.id
        friend_data["bak"] = req.bak
        friend_data["is_accept"] = req.is_accept
        if req.is_accept in (True, False):
            res["processed"].append(friend_data)
        else:
            res["wait_processed"].append(friend_data)
    return response(data=res)


@router.put("/apply/{id}", summary="处理申请", description="处理申请", dependencies=[Depends(get_current_user)])
async def process_apply(id: int, process: ProcessApplyRequest):
    if not await FriendRequest.filter(id=id).exists():
        return response(code=400, message="申请不存在")
    from datetime import datetime
    await FriendRequest.filter(id=id).update(is_accept=process.accept, updated_at=datetime.now())
    return response(message="更新成功")


@router.get("/can_add_contact/{id}", summary="是否可以添加联系人", description="是否可以添加联系人接口",
            dependencies=[Depends(get_current_user)])
async def can_add_contact(id: int, user: User = Depends(get_current_user)):
    """
    是否可以添加联系人
    :param id:
    :return:
    """
    # 检查用户是否存在
    if not await User.filter(id=id).exists():
        return response(data=False, message="用户不存在")
    # 检查用户是否已添加
    if await FriendRequest.filter(Q(requester_id=id, receiver_id=user.id) | Q(requester_id=user.id, receiver_id=id), is_accept=True).exists():
        return response(data=False, message="用户已添加")
    if user.id == id:
        return response(data=False, message="不能添加自己")
    return response(data=True, message="可以添加")

