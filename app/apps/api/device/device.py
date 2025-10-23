import os
import uuid
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Depends
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.expressions import Q

from apps.dependencies.auth import get_current_user
from apps.form.device.device import DeviceOut, DeviceIn
from apps.models.device import Device
from apps.models.user import User
from apps.utils import response
from config import STATIC_PATH

router = APIRouter(prefix="/device", tags=["设备管理"])

Device_Pydantic = pydantic_model_creator(Device, name="Device", exclude=("id",))


@router.post("/upload/image", summary="图像上传接口", description="图像上传接口", dependencies=[Depends(get_current_user)])
async def upload_image(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[-1]
    filename = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(STATIC_PATH, "images", "device", filename)

    with open(save_path, "wb") as f:
        f.write(await file.read())

    return response(data={"filepath": os.path.join("/", "static", "images", "device", filename)}, message="上传成功")


@router.post("/create", response_model=DeviceOut, summary="创建设备", description="创建设备接口",
             dependencies=[Depends(get_current_user)])
async def create_device(device: DeviceIn, user: User = Depends(get_current_user)):
    """
    创建设备
    :param device:
    :return:
    """
    # 检查设备是否存在（如果是管理员，可以创建任意设备名；普通用户检查自己的设备）
    if user.role == "admin":
        exists = await Device.filter(name=device.name).exists()
    else:
        exists = await Device.filter(name=device.name, user_id=user.id).exists()

    if exists:
        return response(code=400, message="设备已存在")

    # 创建设备时关联用户ID
    device_data = device.model_dump(exclude_unset=True)
    device_data["user_id"] = user.id
    device_obj = await Device.create(**device_data)
    data = await Device_Pydantic.from_tortoise_orm(device_obj)
    return response(data=data.model_dump())


@router.get("/list", response_model=list[Device_Pydantic], summary="设备列表", description="获取设备列表",
            dependencies=[Depends(get_current_user)])
async def device_list(
        device_name: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
        user: User = Depends(get_current_user)  # 👈 获取当前用户
):
    """
    获取设备列表
    :return:
    """
    conditions = []
    if device_name:
        conditions.append(Q(name__icontains=device_name))

    # 👇 如果不是管理员，只查询当前用户的设备
    if user.role != "admin":  # 假设你的角色字段是 role
        conditions.append(Q(user_id=user.id))

    query = Device.filter(*conditions).order_by("-id").offset((page - 1) * page_size).limit(page_size)
    res = await Device_Pydantic.from_queryset(query)

    data = [item.model_dump() for item in res]
    return response(data=data)


@router.get("/stats", summary="设备统计", description="获取设备统计信息", dependencies=[Depends(get_current_user)])
async def device_stats(user: User = Depends(get_current_user)):
    """
    获取设备统计信息
    :return:
    """
    # 👇 根据角色决定查询范围
    if user.role == "admin":
        total = await Device.all().count()
        online = await Device.filter(status="在线").count()
        offline = await Device.filter(status="离线").count()
    else:
        total = await Device.filter(user_id=user.id).count()
        online = await Device.filter(user_id=user.id, status="在线").count()
        offline = await Device.filter(user_id=user.id, status="离线").count()

    return response(data={
        "total": total,
        "online": online,
        "offline": offline
    })