from typing import Optional

from fastapi import APIRouter
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.expressions import Q

from apps.form.device.device import DeviceOut, DeviceIn
from apps.models import Device
from apps.utils import response

router = APIRouter(prefix="/device", tags=["设备管理"])

Device_Pydantic = pydantic_model_creator(Device, name="Device", exclude=("id",))

@router.get("/swiper", summary="轮播图", description="获取轮播图")
async def swiper_data():
    """
    获取设备列表
    :return:
    """
    data = [
        {"id": 3, "title": "设备3", "image": "http://192.168.99.200:8000/static/images/device/image3.jpeg"},
        {"id": 2, "title": "设备2", "image": "http://192.168.99.200:8000/static/images/device/image2.jpeg"},
        {"id": 4, "title": "设备4", "image": "http://192.168.99.200:8000/static/images/device/image4.jpeg"},
        {"id": 1, "title": "设备1", "image": "http://192.168.99.200:8000/static/images/device/image1.jpeg"},
        {"id": 5, "title": "设备5", "image": "http://192.168.99.200:8000/static/images/device/image5.jpeg"},
        {"id": 6, "title": "设备6", "image": "http://192.168.99.200:8000/static/images/device/image6.jpeg"},
        {"id": 7, "title": "设备7", "image": "http://192.168.99.200:8000/static/images/device/image7.jpeg"},

    ]
    return response(data=data)


@router.post("/create", response_model=DeviceOut, summary="创建设备", description="创建设备接口")
async def create_device(device: DeviceIn):
    """
    创建设备
    :param device:
    :return:
    """
    # 检查设备是否存在
    if await Device.filter(name=device.name).exists():
        return response(code=400, message="设备已存在")
    # 创建设备
    device_obj = await Device.create(**device.model_dump(exclude_unset=True))
    data = await Device_Pydantic.from_tortoise_orm(device_obj)
    return response(data=data.model_dump())



@router.get("/list", response_model=list[Device_Pydantic], summary="设备列表", description="获取设备列表")
async def device_list(device_name: Optional[str] = None, page: int = 1, page_size: int = 10):
    """
    获取设备列表
    :return:
    """
    conditions = []

    if device_name:
        conditions.append(Q(name__icontains=device_name))

    # 将组合条件传入 filter
    query = Device.filter(*conditions).order_by("-id").offset((page  - 1) * page_size).limit(page_size)
    res = await Device_Pydantic.from_queryset(query)

    # 👇 显式调用 .model_dump() 以确保 jsonable_encoder 能生效
    data = [item.model_dump() for item in res]
    return response(data=data)

