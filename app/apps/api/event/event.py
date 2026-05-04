"""
事件管理API
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.expressions import Q, RawSQL
from tortoise.functions import Count

from apps.dependencies.auth import get_current_user
from apps.form.event.form import (
    EventUpdateForm,
    EventMessageForm,
)
from apps.models.event import Event, EventMessage
from apps.models.user import User
from apps.utils import response

router = APIRouter(prefix="/event", tags=["事件管理"])

Event_Pydantic = pydantic_model_creator(Event, name="Event")
EventMessage_Pydantic = pydantic_model_creator(EventMessage, name="EventMessage")


@router.get("/list", summary="获取事件列表", dependencies=[Depends(get_current_user)])
async def get_event_list(
        status: Optional[str] = Query(None,
                                      description="事件状态筛选：待处理(wait)、处理中(processing)、已关闭(closed)、全部(all)"),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        user: User = Depends(get_current_user)
):
    """
    获取事件列表
    默认只显示“待处理/处理中”事件。历史事件可按状态筛选。
    """
    conditions: list[Q] = []

    if status and status != "all":
        conditions.append(Q(status=status))
    elif not status:
        conditions.append(Q(status__in=["wait", "processing"]))

    if user.role == "maintainer":
        conditions.append(
            Q(device__created_by_user_id=user.id) | Q(device__maintainer_user_id=user.id)
        )

    base_qs = (
        Event.filter(*conditions).prefetch_related("device")
        if conditions
        else Event.all().prefetch_related("device")
    )

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

    total = await query.count()
    query = query.offset((page - 1) * page_size).limit(page_size)
    event_rows = await query

    event_ids = [e.id for e in event_rows]
    message_count_map: dict[int, int] = {}
    if event_ids:
        total_rows = (
            await EventMessage.filter(event_id__in=event_ids)
            .annotate(cnt=Count("id"))
            .group_by("event_id")
            .values("event_id", "cnt")
        )
        message_count_map = {r["event_id"]: r["cnt"] for r in total_rows}

    data = []
    for event in event_rows:
        event_data = await Event_Pydantic.from_tortoise_orm(event)
        event_dict = event_data.model_dump()
        event_dict["message_count"] = message_count_map.get(event.id, 0)

        device = event.device
        mu = await User.get_or_none(id=device.maintainer_user_id)
        maintainer_user = None
        if mu:
            maintainer_user = {
                "id": mu.id,
                "username": mu.username,
                "fullname": mu.fullname,
                "role": mu.role,
                "head": mu.head,
            }
        event_dict["device"] = {
            "id": device.id,
            "name": device.name,
            "address": device.address,
            "status": device.status,
            "maintainer_user": maintainer_user,
        }
        event_dict["triggered_time_display"] = event.created_at.strftime("%Y-%m-%d %H:%M:%S")

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
    """获取事件详情（包含消息列表）"""
    event = await Event.get_or_none(id=event_id).prefetch_related("device")

    if not event:
        return response(code=404, message="事件不存在")

    if user.role == "maintainer":
        await event.fetch_related("device")
        if (
                not event.device
                or (
                event.device.created_by_user_id != user.id
                and event.device.maintainer_user_id != user.id
        )
        ):
            return response(code=403, message="无权访问此事件")

    event_data = await Event_Pydantic.from_tortoise_orm(event)
    event_dict = event_data.model_dump()

    device = event.device
    event_dict['device'] = {
        'id': device.id,
        'name': device.name,
        'address': device.address,
        'status': device.status,
        'maintainer_user_id': device.maintainer_user_id,
    }

    messages = await EventMessage.filter(event_id=event_id).order_by('created_at').limit(50)
    message_list = []
    for msg in messages:
        msg_dict = {
            'id': msg.id,
            'content': msg.content,
            'username': msg.username,
            'user_role': msg.user_role,
            'message_type': msg.message_type,
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

    return response(data=event_dict, message="获取事件详情成功")


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

    if user.role not in ["admin", "leader"]:
        await event.fetch_related("device")
        if (
                not event.device
                or (
                event.device.created_by_user_id != user.id
                and event.device.maintainer_user_id != user.id
        )
        ):
            return response(code=403, message="无权更新此事件")

    update_data = form.model_dump(exclude_unset=True)

    if "title" in update_data:
        event.title = update_data["title"]
    if "level" in update_data:
        event.level = update_data["level"]
    if "status" in update_data:
        event.status = update_data["status"]

    await event.save()

    if update_data.get("status") == "closed":
        await event.fetch_related("device")
        if event.device:
            event.device.status = "正常"
            await event.device.save()

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

    if user.role == "maintainer":
        await event.fetch_related("device")
        if (
                not event.device
                or (
                event.device.created_by_user_id != user.id
                and event.device.maintainer_user_id != user.id
        )
        ):
            return response(code=403, message="无权在此事件中发送消息")

    message = await EventMessage.create(
        event=event,
        user=user,
        username=user.username,
        user_role=user.role,
        content=form.content,
        message_type="user"
    )

    event.status = "processing"
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

    if user.role == "maintainer":
        await event.fetch_related("device")
        if (
                not event.device
                or (
                event.device.created_by_user_id != user.id
                and event.device.maintainer_user_id != user.id
        )
        ):
            return response(code=403, message="无权查看此事件消息")

    query = EventMessage.filter(event_id=event_id).order_by('created_at')
    total = await query.count()

    query = query.offset((page - 1) * page_size).limit(page_size)
    messages = await EventMessage_Pydantic.from_queryset(query)

    data = []
    for message in messages:
        message_dict = message.model_dump()
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


@router.get("/communication/list", summary="获取通讯列表（进行中的事件）", dependencies=[Depends(get_current_user)])
async def get_communication_list(
        user: User = Depends(get_current_user)
):
    """获取通讯列表：待处理/处理中的事件"""
    conditions = Q(status__in=["wait", "processing"])

    if user.role == "maintainer":
        conditions &= (
                Q(device__created_by_user_id=user.id)
                | Q(device__maintainer_user_id=user.id)
        )

    events = await Event.filter(conditions).prefetch_related("device").order_by('-created_at')

    data = []
    for event in events:
        latest_message = await EventMessage.filter(event_id=event.id).order_by('-created_at').first()
        latest_message_info = None
        if latest_message:
            latest_message_info = {
                'content': latest_message.content[:50] + "..." if len(
                    latest_message.content) > 50 else latest_message.content,
                'username': latest_message.username,
                'user_role': latest_message.user_role,
                'created_at': latest_message.created_at.isoformat() if latest_message.created_at else None
            }

        device = event.device
        event_dict = {
            'id': event.id,
            'title': event.title,
            'status': event.status,
            'latest_message': latest_message_info,
            'created_at': event.created_at.isoformat() if event.created_at else None,
            'device': {
                'id': device.id,
                'name': device.name,
                'address': device.address,
                'status': device.status,
                'maintainer_user_id': device.maintainer_user_id,
            },
        }
        data.append(event_dict)

    return response(data=data, message="获取通讯列表成功")
