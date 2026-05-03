import os
import uuid
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Depends
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.expressions import Q

from apps.dependencies.auth import get_current_user
from apps.form.device.device import DeviceOut, DeviceIn, DeviceUpdate
from apps.models.device import Device
from apps.models.user import User
from apps.models.event import Event, EventMessage
from apps.utils import response
from config import DEVICE_STORE_PATH

router = APIRouter(prefix="/device", tags=["设备管理"])

Device_Pydantic = pydantic_model_creator(Device, name="Device")


async def create_event_from_device(device: Device, status: str, user: User):
    """
    从设备状态变更自动创建或更新事件。
    同一设备同时只允许一个未关闭事件（wait/processing）；若已存在则复用并追加系统消息。
    """
    level = "high" if status == "告警" else ("medium" if status == "异常" else "low")

    location_parts = []
    if device.address:
        location_parts.append(device.address)
    location_str = "・".join(location_parts) if location_parts else ""

    title = f"{device.name}・{status}"
    if location_str:
        title += f" ({location_str})"

    existing = (
        await Event.filter(
            device_id=device.id,
            status__in=["wait", "processing"],
        )
        .order_by("-created_at")
        .first()
    )

    if existing:
        existing.title = title
        existing.level = level
        existing.location = device.address
        await existing.save()
        event = existing
    else:
        event = await Event.create(
            title=title,
            level=level,
            status="wait",
            device=device,
            location=device.address,
        )

    await EventMessage.create(
        event=event,
        user=None,
        username="系统",
        user_role="system",
        content=f"告警触发({status})",
        message_type="system",
    )

    return event


@router.post("/upload/image", summary="图像上传接口", description="图像上传接口", dependencies=[Depends(get_current_user)])
async def upload_image(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[-1]
    filename = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(DEVICE_STORE_PATH, filename)

    with open(save_path, "wb") as f:
        f.write(await file.read())

    return response(data={"filepath": os.path.join("/", "data", "device", filename)}, message="上传成功")


@router.post("/create", response_model=DeviceOut, summary="创建设备", description="创建设备接口",
             dependencies=[Depends(get_current_user)])
async def create_device(device: DeviceIn, user: User = Depends(get_current_user)):
    """
    创建设备
    :param device:
    :return:
    """
    # 检查设备是否存在（管理员和班长可以创建任意设备名；普通用户检查自己的设备）
    if user.role in ["admin", "leader"]:
        exists = await Device.filter(name=device.name).exists()
    else:
        exists = await Device.filter(name=device.name, created_by_user_id=user.id).exists()

    if exists:
        return response(code=400, message="设备已存在")

    # 验证设备状态：只允许四种状态
    valid_statuses = ["告警", "异常", "离线", "正常"]
    device_data = device.model_dump(exclude_unset=True)
    device_status = device_data.get('status', '正常')  # 默认为正常
    
    if device_status and device_status not in valid_statuses:
        return response(code=400, message=f"设备状态无效，只允许：{', '.join(valid_statuses)}")
    
    # 创建设备时关联用户ID
    device_data["created_by_user_id"] = user.id

    # 设备负责人：优先使用传入的 maintainer_user_id，否则默认当前登录用户。
    # 联系方式统一从用户资料带出；资料未维护时允许为空。
    maintainer_id = device_data.pop("maintainer_user_id", None)
    if not maintainer_id:
        maintainer_id = user.id
    maintainer = await User.get_or_none(id=maintainer_id)
    if not maintainer:
        return response(code=400, message="维护人不存在")
    if maintainer.role == "admin":
        return response(code=400, message="管理员不能作为维护人")
    device_data["maintainer_user_id"] = maintainer_id
    device_data["contact"] = maintainer.contact or None

    if device_data.get("installer"):
        installer_user = await User.get_or_none(username=device_data["installer"])
        if installer_user:
            if installer_user.role == "admin":
                return response(code=400, message="管理员不能作为安装人")
            device_data["installer_contact"] = installer_user.contact or None

    device_obj = await Device.create(**device_data)
    
    # 如果设备状态不是正常，自动创建事件
    if device_obj.status and device_obj.status in ["告警", "异常", "离线"]:
        await create_event_from_device(device_obj, device_obj.status, user)
    
    data = await Device_Pydantic.from_tortoise_orm(device_obj)
    return response(data=data.model_dump())


@router.put("/update/{device_id}", response_model=DeviceOut, summary="更新设备", description="更新设备信息",
            dependencies=[Depends(get_current_user)])
async def update_device(device_id: int, device: DeviceUpdate, user: User = Depends(get_current_user)):
    """
    更新设备信息
    :param device_id: 设备ID
    :param device: 设备更新数据
    :param user: 当前用户
    :return:
    """
    # 查询设备是否存在（管理员和班长可以访问所有设备，其他用户只能访问自己创建的设备）
    if user.role in ["admin", "leader"]:
        device_obj = await Device.get_or_none(id=device_id)
    else:
        device_obj = await Device.get_or_none(id=device_id, created_by_user_id=user.id)
    
    if not device_obj:
        return response(code=404, message="设备不存在或无权访问")
    
    # 记录旧状态，用于判断是否需要创建事件
    old_status = device_obj.status
    update_data = device.model_dump(exclude_unset=True)
    new_status = update_data.get('status', old_status)
    
    # 处理设备负责人变更（仅存 user_id，不做强关联）
    maintainer_id = update_data.pop("maintainer_user_id", None)
    if maintainer_id is not None:
        maintainer = await User.get_or_none(id=maintainer_id)
        if not maintainer:
            return response(code=400, message="维护人不存在")
        if maintainer.role == "admin":
            return response(code=400, message="管理员不能作为维护人")
        device_obj.maintainer_user_id = maintainer_id
        update_data["contact"] = maintainer.contact or None

    if "installer" in update_data:
        installer_user = await User.get_or_none(username=update_data["installer"])
        if installer_user and installer_user.role == "admin":
            return response(code=400, message="管理员不能作为安装人")
        update_data["installer_contact"] = installer_user.contact if installer_user else None

    # 验证设备状态：只允许四种状态
    valid_statuses = ["告警", "异常", "离线", "正常"]
    if new_status and new_status not in valid_statuses:
        return response(code=400, message=f"设备状态无效，只允许：{', '.join(valid_statuses)}")
    
    # 更新设备信息
    await device_obj.update_from_dict(update_data)
    await device_obj.save()
    
    if new_status in ["告警", "异常", "离线"]:
        if old_status != new_status:
            await create_event_from_device(device_obj, new_status, user)
    
    # 如果设备状态从非正常变为正常，关闭相关的事件
    if new_status == "正常" and old_status in ["告警", "异常", "离线"]:
        # 关闭该设备所有进行中的事件
        ongoing_events = await Event.filter(
            device_id=device_obj.id,
            status__in=["wait", "processing"]
        )
        for event in ongoing_events:
            event.status = "closed"
            await event.save()
            
            # 创建系统消息
            await EventMessage.create(
                event=event,
                user=None,
                username="系统",
                user_role="system",
                content="设备状态已恢复为正常，事件已关闭",
                message_type="system"
            )
    
    data = await Device_Pydantic.from_tortoise_orm(device_obj)
    return response(data=data.model_dump(), message="更新成功")


@router.delete("/delete/{device_id}", summary="删除设备", description="删除设备",
               dependencies=[Depends(get_current_user)])
async def delete_device(device_id: int, user: User = Depends(get_current_user)):
    """
    删除设备
    :param device_id: 设备ID
    :param user: 当前用户
    :return:
    """
    # 查询设备是否存在（管理员和班长可以访问所有设备，其他用户只能访问自己创建的设备）
    if user.role in ["admin", "leader"]:
        device_obj = await Device.get_or_none(id=device_id)
    else:
        device_obj = await Device.get_or_none(id=device_id, created_by_user_id=user.id)
    
    if not device_obj:
        return response(code=404, message="设备不存在或无权访问")
    
    # 删除设备
    await device_obj.delete()
    
    return response(message="删除成功")


@router.get("/detail/{device_id}", response_model=DeviceOut, summary="设备详情", description="获取设备详情",
            dependencies=[Depends(get_current_user)])
async def device_detail(device_id: int, user: User = Depends(get_current_user)):
    """
    获取设备详情
    :param device_id: 设备ID
    :param user: 当前用户
    :return:
    """
    # 查询设备是否存在（管理员和班长可以访问所有设备，其他用户只能访问自己创建的设备）
    if user.role in ["admin", "leader"]:
        device_obj = await Device.get_or_none(id=device_id)
    else:
        device_obj = await Device.get_or_none(id=device_id, created_by_user_id=user.id)
    
    if not device_obj:
        return response(code=404, message="设备不存在或无权访问")
    
    data = await Device_Pydantic.from_tortoise_orm(device_obj)
    return response(data=data.model_dump())


@router.get("/list", response_model=list[Device_Pydantic], summary="设备列表", description="获取设备列表",
            dependencies=[Depends(get_current_user)])
async def device_list(
        device_name: Optional[str] = None,
        status: Optional[str] = None,  # 新增状态筛选：告警、异常、离线、正常
        exclude_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
        user: User = Depends(get_current_user)  # 👈 获取当前用户
):
    """
    获取设备列表
    支持按设备名称和状态筛选
    设备状态：告警、异常、离线、正常
    :return:
    """
    conditions = []
    if device_name:
        conditions.append(Q(name__icontains=device_name))
    
    # 状态筛选：告警、异常、离线、正常
    if status:
        valid_statuses = ["告警", "异常", "离线", "正常"]
        if status not in valid_statuses:
            return response(code=400, message=f"设备状态无效，只允许：{', '.join(valid_statuses)}")
        conditions.append(Q(status=status))
    if exclude_status:
        valid_statuses = ["告警", "异常", "离线", "正常"]
        if exclude_status not in valid_statuses:
            return response(code=400, message=f"设备状态无效，只允许：{', '.join(valid_statuses)}")
        conditions.append(~Q(status=exclude_status))
    # 如果不是管理员或班长，只查询与当前用户有关的设备：
    # 1）当前用户创建的设备 2）当前用户作为负责人维护的设备
    if user.role not in ["admin", "leader"]:
        conditions.append(
            Q(created_by_user_id=user.id) | Q(maintainer_user_id=user.id)
        )

    query = Device.filter(*conditions).order_by("-id")
    total = await query.count()
    
    query = query.offset((page - 1) * page_size).limit(page_size)
    res = await Device_Pydantic.from_queryset(query)

    data = [item.model_dump() for item in res]
    total_page = (total + page_size - 1) // page_size
    
    return response(
        data=data,
        total=total,
        total_page=total_page,
        message="获取设备列表成功"
    )


@router.get("/stats", summary="设备统计", description="获取设备统计信息", dependencies=[Depends(get_current_user)])
async def device_stats(user: User = Depends(get_current_user)):
    """
    获取设备统计信息（用于今日概览）
    设备状态：告警、异常、离线、正常
    :return:
    """
    # admin和leader可以看到所有设备，
    # maintainer只能看到与自己有关的设备（创建者或负责人）
    if user.role in ["admin", "leader"]:
        total = await Device.all().count()
        alarm = await Device.filter(status="告警").count()
        abnormal = await Device.filter(status="异常").count()
        offline = await Device.filter(status="离线").count()
        normal = await Device.filter(status="正常").count()
    else:
        base_q = Device.filter(
            Q(created_by_user_id=user.id) | Q(maintainer_user_id=user.id)
        )
        total = await base_q.count()
        alarm = await base_q.filter(status="告警").count()
        abnormal = await base_q.filter(status="异常").count()
        offline = await base_q.filter(status="离线").count()
        normal = await base_q.filter(status="正常").count()

    return response(data={
        "total": total,      # 总共
        "alarm": alarm,      # 告警
        "abnormal": abnormal,  # 异常
        "offline": offline,   # 离线
        "normal": normal      # 正常
    })
