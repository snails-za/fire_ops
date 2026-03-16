"""
事件管理API
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.expressions import Q, RawSQL

from apps.dependencies.auth import get_current_user
from apps.form.event.form import (
    EventCreateForm,
    EventUpdateForm,
    EventMessageForm,
    EventProgressForm
)
from apps.models.event import Event, EventMessage, EventProgress
from apps.models.user import User
from apps.models.device import Device
from apps.utils import response

router = APIRouter(prefix="/event", tags=["事件管理"])

# 创建响应模型
Event_Pydantic = pydantic_model_creator(Event, name="Event")
EventMessage_Pydantic = pydantic_model_creator(EventMessage, name="EventMessage")
EventProgress_Pydantic = pydantic_model_creator(EventProgress, name="EventProgress")

# 角色显示名称映射
ROLE_DISPLAY_MAP = {
    'maintainer': '维护',
    'leader': '值班员',
    'admin': '管理员'
}


@router.get("/list", summary="获取事件列表", dependencies=[Depends(get_current_user)])
async def get_event_list(
    status: Optional[str] = Query(None, description="事件状态筛选：告警(alarm)、处理中(processing)、已关闭(closed)、全部(all)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user)
):
    """
    获取事件列表
    默认只显示"告警/处理中"。历史事件可按状态筛选。
    """
    # 构建查询条件
    conditions = []
    
    # 状态筛选
    if status and status != "all":
        conditions.append(Q(status=status))
    elif not status:
        # 默认只显示告警和处理中的事件
        conditions.append(Q(status__in=["alarm", "processing"]))
    
    # 根据角色过滤事件
    # 管理员可以看到所有事件
    # 班长可以看到所有事件
    # 维护人员只能看到自己负责的事件
    if user.role == "maintainer":
        conditions.append(Q(responsible_user_id=user.id))
    
    # 执行查询
    if conditions:
        query_condition = conditions[0]
        for condition in conditions[1:]:
            query_condition &= condition
        base_qs = Event.filter(query_condition)
    else:
        base_qs = Event.all()
    query = (
        base_qs
        .annotate(
            level_order=RawSQL(
                "CASE level "
                "WHEN 'high' THEN 0 "
                "WHEN 'medium' THEN 1 "
                "WHEN 'low' THEN 2 "
                "ELSE 3 END"
            )
        )
        .order_by("level_order", "-created_at")
    )
    
    # 分页
    total = await query.count()
    query = query.offset((page - 1) * page_size).limit(page_size)
    events = await Event_Pydantic.from_queryset(query)
    
    # 转换为响应格式（根据UI图优化格式）
    data = []
    for event in events:
        event_dict = event.model_dump()
        
        # 获取关联设备信息
        if event_dict.get('device_id'):
            device = await Device.get_or_none(id=event_dict['device_id'])
            if device:
                event_dict['device'] = {
                    'id': device.id,
                    'name': device.name,
                    'address': device.address,
                    'status': device.status
                }
        
        # 获取负责人和协同人信息
        responsible_info = None
        if event_dict.get('responsible_user_id'):
            resp_user = await User.get_or_none(id=event_dict['responsible_user_id'])
            if resp_user:
                responsible_info = {
                    'id': resp_user.id,
                    'username': resp_user.username,
                    'role': resp_user.role
                }
                event_dict['responsible_user'] = responsible_info
        
        collaborator_info = None
        if event_dict.get('collaborator_user_id'):
            collab_user = await User.get_or_none(id=event_dict['collaborator_user_id'])
            if collab_user:
                collaborator_info = {
                    'id': collab_user.id,
                    'username': collab_user.username,
                    'role': collab_user.role
                }
                event_dict['collaborator_user'] = collaborator_info
        
        # 格式化负责人信息（用于UI显示）
        if responsible_info:
            role_name = ROLE_DISPLAY_MAP.get(responsible_info['role'], responsible_info['role'])
            event_dict['responsible_display'] = f"{responsible_info['username']}({role_name})"
        
        if collaborator_info:
            role_name = ROLE_DISPLAY_MAP.get(collaborator_info['role'], collaborator_info['role'])
            event_dict['collaborator_display'] = f"{collaborator_info['username']}({role_name})"
        
        # 格式化进度信息（用于UI显示）
        # 获取最新进度
        latest_progress = await EventProgress.filter(event_id=event_dict['id']).order_by('-created_at').first()
        if latest_progress:
            event_dict['progress_display'] = latest_progress.progress_type
        else:
            event_dict['progress_display'] = "告警触发"
        
        # 格式化时间显示
        if event_dict.get('triggered_at'):
            triggered_time = event_dict['triggered_at']
            if isinstance(triggered_time, str):
                try:
                    triggered_time = datetime.fromisoformat(triggered_time.replace('Z', '+00:00'))
                except Exception:
                    pass
            if isinstance(triggered_time, datetime):
                event_dict['triggered_time_display'] = triggered_time.strftime('%H:%M')
        
        data.append(event_dict)
    
    total_page = (total + page_size - 1) // page_size
    
    return response(
        data=data,
        total=total,
        total_page=total_page,
        message="获取事件列表成功"
    )


@router.get("/{event_id}", summary="获取事件详情", dependencies=[Depends(get_current_user)])
async def get_event_detail(
    event_id: int,
    user: User = Depends(get_current_user)
):
    """获取事件详情（包含消息列表和进度时间线）"""
    event = await Event.get_or_none(id=event_id)
    
    if not event:
        return response(code=404, message="事件不存在")
    
    # 权限检查：维护人员只能查看自己负责的事件
    if user.role == "maintainer" and event.responsible_user_id != user.id:
        return response(code=403, message="无权访问此事件")
    
    event_data = await Event_Pydantic.from_tortoise_orm(event)
    event_dict = event_data.model_dump()
    
    # 获取关联设备信息
    if event.device_id:
        device = await Device.get_or_none(id=event.device_id)
        if device:
            event_dict['device'] = {
                'id': device.id,
                'name': device.name,
                'address': device.address,
                'status': device.status
            }
    
    # 获取负责人和协同人信息
    if event.responsible_user_id:
        resp_user = await User.get_or_none(id=event.responsible_user_id)
        if resp_user:
            event_dict['responsible_user'] = {
                'id': resp_user.id,
                'username': resp_user.username,
                'role': resp_user.role
            }
    
    if event.collaborator_user_id:
        collab_user = await User.get_or_none(id=event.collaborator_user_id)
        if collab_user:
            event_dict['collaborator_user'] = {
                'id': collab_user.id,
                'username': collab_user.username,
                'role': collab_user.role
            }
    
    # 获取消息列表（最近50条）
    messages = await EventMessage.filter(event_id=event_id).order_by('created_at').limit(50)
    message_list = []
    for msg in messages:
        msg_dict = {
            'id': msg.id,
            'content': msg.content,
            'username': msg.username,
            'user_role': msg.user_role,
            'message_type': msg.message_type,
            'is_read': msg.is_read,
            'created_at': msg.created_at.isoformat() if msg.created_at else None
        }
        if msg.user_id:
            msg_user = await User.get_or_none(id=msg.user_id)
            if msg_user:
                msg_dict['user'] = {
                    'id': msg_user.id,
                    'username': msg_user.username,
                    'role': msg_user.role,
                    'head': msg_user.head
                }
        message_list.append(msg_dict)
    event_dict['messages'] = message_list
    
    # 获取进度时间线
    progresses = await EventProgress.filter(event_id=event_id).order_by('created_at')
    progress_list = []
    for prog in progresses:
        prog_dict = {
            'id': prog.id,
            'progress_type': prog.progress_type,
            'description': prog.description,
            'status': prog.status,
            'operator_username': prog.operator_username,
            'created_at': prog.created_at.isoformat() if prog.created_at else None
        }
        if prog.operator_id:
            operator = await User.get_or_none(id=prog.operator_id)
            if operator:
                prog_dict['operator'] = {
                    'id': operator.id,
                    'username': operator.username,
                    'role': operator.role
                }
        progress_list.append(prog_dict)
    event_dict['progresses'] = progress_list
    event.status = "processing"
    await event.save()
    
    return response(data=event_dict, message="获取事件详情成功")


@router.post("/create", summary="创建事件", dependencies=[Depends(get_current_user)])
async def create_event(
    form: EventCreateForm,
    user: User = Depends(get_current_user)
):
    """创建事件"""
    # 检查设备是否存在
    device = None
    if form.device_id:
        device = await Device.get_or_none(id=form.device_id)
        if not device:
            return response(code=404, message="设备不存在")
    
    # 创建事件
    event = await Event.create(
        title=form.title,
        level=form.level or "normal",
        status="alarm",
        device=device,
        device_name=device.name if device else None,
        device_address=device.address if device else None,
        location=form.location,
        circuit=form.circuit,
        triggered_at=datetime.now(),
        triggered_by="user",
        suggestion=form.suggestion
    )
    
    # 创建系统消息
    await EventMessage.create(
        event=event,
        user=None,
        username="系统",
        user_role="system",
        content=f"事件已创建：{form.title}",
        message_type="system"
    )
    
    # 创建初始进度记录
    await EventProgress.create(
        event=event,
        progress_type="告警触发",
        description=f"系统收到事件上报，自动创建事件并推送值班。",
        operator=None,
        operator_username="系统",
        status="completed"
    )
    
    # 更新事件消息计数
    event.message_count = 1
    await event.save()
    
    event_data = await Event_Pydantic.from_tortoise_orm(event)
    return response(data=event_data.model_dump(), message="事件创建成功")


@router.put("/{event_id}", summary="更新事件", dependencies=[Depends(get_current_user)])
async def update_event(
    event_id: int,
    form: EventUpdateForm,
    user: User = Depends(get_current_user)
):
    """更新事件"""
    event = await Event.get_or_none(id=event_id)
    
    if not event:
        return response(code=404, message="事件不存在")
    
    # 权限检查：只有管理员、班长或负责人可以更新事件
    if user.role not in ["admin", "leader"] and event.responsible_user_id != user.id:
        return response(code=403, message="无权更新此事件")
    
    # 更新事件信息
    update_data = form.model_dump(exclude_unset=True)
    
    # 处理负责人和协同人
    if "responsible_user_id" in update_data and update_data["responsible_user_id"]:
        resp_user = await User.get_or_none(id=update_data["responsible_user_id"])
        if resp_user:
            event.responsible_user_id = resp_user.id
            event.responsible_username = resp_user.username
        else:
            return response(code=404, message="负责人用户不存在")
    
    if "collaborator_user_id" in update_data and update_data["collaborator_user_id"]:
        collab_user = await User.get_or_none(id=update_data["collaborator_user_id"])
        if collab_user:
            event.collaborator_user_id = collab_user.id
            event.collaborator_username = collab_user.username
        else:
            return response(code=404, message="协同人用户不存在")
    
    # 记录旧状态，用于判断是否需要创建进度记录
    old_status = event.status
    
    # 更新其他字段
    if "title" in update_data:
        event.title = update_data["title"]
    if "status" in update_data:
        new_status = update_data["status"]
        event.status = new_status
        
        # 如果状态变更，自动创建进度记录
        if old_status != new_status:
            status_display = {
                "alarm": "告警",
                "processing": "处理中",
                "closed": "已关闭"
            }
            old_display = status_display.get(old_status, old_status)
            new_display = status_display.get(new_status, new_status)
            
            progress_type_map = {
                "processing": "派单/指派负责人",
                "closed": "处理完成"
            }
            progress_type = progress_type_map.get(new_status, f"状态变更：{old_display} → {new_display}")
            
            description_map = {
                "processing": "已通知维护人员到场核查。",
                "closed": f"事件已关闭，状态从{old_display}变更为{new_display}。"
            }
            description = description_map.get(new_status, f"事件状态从{old_display}变更为{new_display}。")
            
            await EventProgress.create(
                event=event,
                progress_type=progress_type,
                description=description,
                operator=user,
                operator_username=user.username,
                status="completed"
            )
            
            # 如果是状态变更为处理中，创建系统消息
            if new_status == "processing":
                await EventMessage.create(
                    event=event,
                    user=None,
                    username="系统",
                    user_role="system",
                    content=f"事件状态已变更为处理中",
                    message_type="system"
                )
                event.message_count += 1
    
    if "level" in update_data:
        event.level = update_data["level"]
    if "suggestion" in update_data:
        event.suggestion = update_data["suggestion"]
    if "conclusion" in update_data:
        event.conclusion = update_data["conclusion"]
    if "estimated_arrival" in update_data:
        event.estimated_arrival = update_data["estimated_arrival"]
    
    await event.save()
    
    event_data = await Event_Pydantic.from_tortoise_orm(event)
    return response(data=event_data.model_dump(), message="事件更新成功")


@router.post("/{event_id}/message", summary="发送事件消息", dependencies=[Depends(get_current_user)])
async def send_event_message(
    event_id: int,
    form: EventMessageForm,
    user: User = Depends(get_current_user)
):
    """发送事件消息"""
    event = await Event.get_or_none(id=event_id)
    
    if not event:
        return response(code=404, message="事件不存在")
    
    # 权限检查：维护人员只能在自己负责的事件中发送消息
    if user.role == "maintainer" and event.responsible_user_id != user.id:
        return response(code=403, message="无权在此事件中发送消息")
    
    # 创建消息
    message = await EventMessage.create(
        event=event,
        user=user,
        username=user.username,
        user_role=user.role,
        content=form.content,
        message_type="user"
    )
    
    # 更新事件消息计数
    event.message_count += 1
    # 更新未读消息计数（除了发送者本人，其他人都增加未读数）
    if event.responsible_user_id and event.responsible_user_id != user.id:
        event.unread_count += 1
    if event.collaborator_user_id and event.collaborator_user_id != user.id:
        event.unread_count += 1
    await event.save()
    
    message_data = await EventMessage_Pydantic.from_tortoise_orm(message)
    return response(data=message_data.model_dump(), message="消息发送成功")


@router.get("/{event_id}/messages", summary="获取事件消息列表", dependencies=[Depends(get_current_user)])
async def get_event_messages(
    event_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user)
):
    """获取事件消息列表"""
    event = await Event.get_or_none(id=event_id)
    
    if not event:
        return response(code=404, message="事件不存在")
    
    # 权限检查：维护人员只能查看自己负责的事件消息
    if user.role == "maintainer" and event.responsible_user_id != user.id:
        return response(code=403, message="无权查看此事件消息")
    
    # 查询消息
    query = EventMessage.filter(event_id=event_id).order_by('created_at')
    total = await query.count()
    
    query = query.offset((page - 1) * page_size).limit(page_size)
    messages = await EventMessage_Pydantic.from_queryset(query)
    
    # 转换为响应格式
    data = []
    for message in messages:
        message_dict = message.model_dump()
        # 添加用户信息
        if message_dict.get('user_id'):
            msg_user = await User.get_or_none(id=message_dict['user_id'])
            if msg_user:
                message_dict['user'] = {
                    'id': msg_user.id,
                    'username': msg_user.username,
                    'role': msg_user.role,
                    'head': msg_user.head
                }
        data.append(message_dict)
    
    total_page = (total + page_size - 1) // page_size
    
    return response(
        data=data,
        total=total,
        total_page=total_page,
        message="获取消息列表成功"
    )


@router.post("/{event_id}/messages/{message_id}/read", summary="标记消息为已读", dependencies=[Depends(get_current_user)])
async def mark_message_read(
    event_id: int,
    message_id: int,
    user: User = Depends(get_current_user)
):
    """标记消息为已读"""
    message = await EventMessage.get_or_none(id=message_id, event_id=event_id)
    if not message:
        return response(code=404, message="消息不存在")
    
    # 只有非发送者才能标记为已读
    if message.user_id and message.user_id == user.id:
        return response(code=400, message="不能标记自己发送的消息为已读")
    
    # 标记为已读
    if not message.is_read:
        message.is_read = True
        message.read_at = datetime.now()
        await message.save()
        
    # 更新事件的未读消息计数（需要重新计算）
    event_obj = await Event.get_or_none(id=event_id)
    if event_obj:
        # 重新计算未读消息数
        unread_count = await EventMessage.filter(
            event_id=event_id,
            is_read=False
        ).exclude(user_id=user.id).count()
        event_obj.unread_count = unread_count
        await event_obj.save()
    
    return response(message="消息已标记为已读")


@router.post("/{event_id}/messages/read-all", summary="标记所有消息为已读", dependencies=[Depends(get_current_user)])
async def mark_all_messages_read(
    event_id: int,
    user: User = Depends(get_current_user)
):
    """标记事件中所有消息为已读"""
    event = await Event.get_or_none(id=event_id)
    
    if not event:
        return response(code=404, message="事件不存在")
    
    # 权限检查
    if user.role == "maintainer" and event.responsible_user_id != user.id:
        return response(code=403, message="无权操作此事件")
    
    # 标记所有未读消息为已读
    unread_messages = await EventMessage.filter(
        event_id=event_id,
        is_read=False
    ).exclude(user_id=user.id)  # 排除自己发送的消息
    
    count = 0
    for message in unread_messages:
        message.is_read = True
        message.read_at = datetime.now()
        await message.save()
        count += 1
    
    # 更新事件的未读消息计数
    event.unread_count = 0
    await event.save()
    
    return response(data={"marked_count": count}, message=f"已标记{count}条消息为已读")


@router.get("/{event_id}/progress", summary="获取事件进度时间线", dependencies=[Depends(get_current_user)])
async def get_event_progress(
    event_id: int,
    user: User = Depends(get_current_user)
):
    """获取事件进度时间线"""
    event = await Event.get_or_none(id=event_id)
    
    if not event:
        return response(code=404, message="事件不存在")
    
    # 权限检查
    if user.role == "maintainer" and event.responsible_user_id != user.id:
        return response(code=403, message="无权查看此事件进度")
    
    # 查询进度记录
    progresses = await EventProgress.filter(event_id=event_id).order_by('created_at')
    progress_data = await EventProgress_Pydantic.from_queryset(progresses)
    
    # 转换为响应格式
    data = []
    for progress in progress_data:
        progress_dict = progress.model_dump()
        # 添加操作人信息
        if progress_dict.get('operator_id'):
            operator = await User.get_or_none(id=progress_dict['operator_id'])
            if operator:
                progress_dict['operator'] = {
                    'id': operator.id,
                    'username': operator.username,
                    'role': operator.role
                }
        data.append(progress_dict)
    
    return response(data=data, message="获取进度时间线成功")


@router.post("/{event_id}/progress", summary="创建事件进度记录", dependencies=[Depends(get_current_user)])
async def create_event_progress(
    event_id: int,
    form: EventProgressForm,
    user: User = Depends(get_current_user)
):
    """创建事件进度记录"""
    event = await Event.get_or_none(id=event_id)
    
    if not event:
        return response(code=404, message="事件不存在")
    
    # 权限检查：只有管理员、班长或负责人可以创建进度记录
    if user.role not in ["admin", "leader"] and event.responsible_user_id != user.id:
        return response(code=403, message="无权创建此事件进度记录")
    
    # 创建进度记录
    progress = await EventProgress.create(
        event=event,
        progress_type=form.progress_type,
        description=form.description,
        operator=user,
        operator_username=user.username,
        status=form.status or "completed"
    )
    
    progress_data = await EventProgress_Pydantic.from_tortoise_orm(progress)
    return response(data=progress_data.model_dump(), message="进度记录创建成功")


@router.get("/communication/list", summary="获取通讯列表（未读和进行中的事件）", dependencies=[Depends(get_current_user)])
async def get_communication_list(
    user: User = Depends(get_current_user)
):
    """获取通讯列表：未读和进行中的事件"""
    # 构建查询条件：未读消息数>0或状态为告警/处理中的事件
    conditions = Q(status__in=["alarm", "processing"])
    
    # 根据角色过滤
    if user.role == "maintainer":
        # 维护人员只看自己负责的事件
        conditions &= Q(responsible_user_id=user.id)
    # admin和leader看所有事件
    
    # 查询事件
    events = await Event.filter(conditions).order_by('-created_at')
    
    # 转换为响应格式
    data = []
    for event in events:
        # 计算当前用户的未读消息数
        unread_count = await EventMessage.filter(
            event_id=event.id,
            is_read=False
        ).exclude(user_id=user.id).count()
        
        # 获取最新消息
        latest_message = await EventMessage.filter(event_id=event.id).order_by('-created_at').first()
        latest_message_info = None
        if latest_message:
            latest_message_info = {
                'content': latest_message.content[:50] + "..." if len(latest_message.content) > 50 else latest_message.content,
                'username': latest_message.username,
                'user_role': latest_message.user_role,
                'created_at': latest_message.created_at.isoformat() if latest_message.created_at else None
            }
        
        event_dict = {
            'id': event.id,
            'title': event.title,
            'status': event.status,
            'unread_count': unread_count,
            'latest_message': latest_message_info,
            'created_at': event.created_at.isoformat() if event.created_at else None
        }
        
        # 只返回有未读消息或进行中的事件
        if unread_count > 0 or event.status in ["alarm", "processing"]:
            data.append(event_dict)
    
    return response(data=data, message="获取通讯列表成功")

