"""
公告管理API
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.expressions import Q

from apps.dependencies.auth import get_current_user
from apps.form.announcement.form import (
    AnnouncementCreateForm,
    AnnouncementUpdateForm
)
from apps.models.announcement import Announcement
from apps.models.user import User
from apps.utils import response

router = APIRouter(prefix="/announcement", tags=["公告管理"])

# 创建响应模型
Announcement_Pydantic = pydantic_model_creator(Announcement)


@router.post("/create", response_model=Announcement_Pydantic, summary="创建公告",
             dependencies=[Depends(get_current_user)])
async def create_announcement(form: AnnouncementCreateForm, user: User = Depends(get_current_user)):
    # 创建公告
    announcement = await Announcement.create(
        title=form.title,
        content=form.content,
        publish_time=form.publish_time,
        expire_time=form.expire_time,
        created_by_user_id=user.id
    )
    data = await Announcement_Pydantic.from_tortoise_orm(announcement)

    return response(
        data=data.model_dump(),
        message="公告创建成功"
    )


@router.get("/list", summary="获取公告列表", dependencies=[Depends(get_current_user)])
async def get_announcement_list(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        status: Optional[str] = Query(None),
        keyword: Optional[str] = Query(None),
):
    # 构建查询条件
    conditions = []

    # 状态筛选
    if status:
        conditions.append(Q(status=status))

    # 关键词搜索
    if keyword:
        conditions.append(Q(title__icontains=keyword) | Q(content__icontains=keyword))

    # 执行查询
    if conditions:
        query_condition = conditions[0]
        for condition in conditions[1:]:
            query_condition &= condition
        query = Announcement.filter(query_condition).order_by('-created_at')
    else:
        query = Announcement.all().order_by('-created_at')

    # 分页
    total = await query.count()
    
    # 转换为响应格式（在查询执行前）
    query = query.offset((page - 1) * page_size).limit(page_size)
    announcement_list = await Announcement_Pydantic.from_queryset(query)
    total_page = (total + page_size - 1) // page_size

    data = []
    for announcement in announcement_list:
        announcement_dict = announcement.model_dump()
        # 通过用户ID查询用户名
        try:
            user = await User.get_or_none(id=announcement_dict['created_by_user_id'])
            announcement_dict['created_by_username'] = user.username if user else '未知用户'
        except:
            announcement_dict['created_by_username'] = '未知用户'
        data.append(announcement_dict)

    return response(
        data=data,
        total=total,
        total_page=total_page,
        message="获取公告列表成功"
    )


@router.get("/{announcement_id}", response_model=Announcement_Pydantic, summary="获取公告详情",
            dependencies=[Depends(get_current_user)])
async def get_announcement_detail(announcement_id: int):
    # 查找公告
    announcement = await Announcement.get_or_none(id=announcement_id)
    if not announcement:
        return response(code=0, message="公告不存在！")

    data = await Announcement_Pydantic.from_tortoise_orm(announcement)
    return response(
        data=data.model_dump(),
        message="获取公告详情成功"
    )


@router.put("/{announcement_id}", summary="更新公告", dependencies=[Depends(get_current_user)])
async def update_announcement(announcement_id: int, form: AnnouncementUpdateForm):
    # 查找公告
    announcement = await Announcement.get_or_none(id=announcement_id)
    if not announcement:
        return response(code=404, message="公告不存在")

    # 更新字段
    update_data = form.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(announcement, field, value)

    await announcement.save()

    data = await Announcement_Pydantic.from_tortoise_orm(announcement)
    return response(
        data=data.model_dump(),
        message="公告更新成功"
    )


@router.delete("/{announcement_id}", summary="删除公告", dependencies=[Depends(get_current_user)])
async def delete_announcement(announcement_id: int):
    # 查找公告
    announcement = await Announcement.get_or_none(id=announcement_id)
    if not announcement:
        return response(code=404, message="公告不存在")

    await announcement.delete()

    return response(message="公告删除成功")


@router.post("/{announcement_id}/publish", dependencies=[Depends(get_current_user)])
async def publish_announcement(announcement_id: int):
    # 查找公告
    announcement = await Announcement.get_or_none(id=announcement_id)
    if not announcement:
        return response(code=404, message="公告不存在")

    # 更新状态和发布时间
    announcement.status = "published"
    if not announcement.publish_time:
        announcement.publish_time = datetime.now()

    await announcement.save()

    data = await Announcement_Pydantic.from_tortoise_orm(announcement)
    return response(
        data=data.model_dump(),
        message="公告发布成功"
    )


@router.post("/{announcement_id}/archive", summary="归档公告", dependencies=[Depends(get_current_user)])
async def archive_announcement(announcement_id: int):
    # 查找公告
    announcement = await Announcement.get_or_none(id=announcement_id)
    if not announcement:
        return response(code=404, message="公告不存在")

    # 更新状态
    announcement.status = "archived"
    await announcement.save()

    data = await Announcement_Pydantic.from_tortoise_orm(announcement)
    return response(
        data=data.model_dump(),
        message="公告归档成功"
    )


@router.get("/public/list", summary="获取公开公告列表", dependencies=[Depends(get_current_user)])
async def get_public_announcement_list(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        keyword: Optional[str] = Query(None)
):
    # 构建查询条件（只查询已发布的公告）
    conditions = [Q(status="published")]

    # 关键词搜索
    if keyword:
        conditions.append(Q(title__icontains=keyword) | Q(content__icontains=keyword))

    # 执行查询
    if conditions:
        query_condition = conditions[0]
        for condition in conditions[1:]:
            query_condition &= condition
        query = Announcement.filter(query_condition).order_by('-created_at')
    else:
        query = Announcement.filter(Q(status="published")).order_by('-created_at')

    # 分页
    total = await query.count()
    
    # 转换为响应格式（在查询执行前）
    query = query.offset((page - 1) * page_size).limit(page_size)
    announcement_list = await Announcement_Pydantic.from_queryset(query)
    total_page = (total + page_size - 1) // page_size

    data = []
    for announcement in announcement_list:
        announcement_dict = announcement.model_dump()
        # 通过用户ID查询用户名
        try:
            user = await User.get_or_none(id=announcement_dict['created_by_user_id'])
            announcement_dict['created_by_username'] = user.username if user else '未知用户'
        except:
            announcement_dict['created_by_username'] = '未知用户'
        data.append(announcement_dict)

    return response(
        data=data,
        total=total,
        total_page=total_page,
        message="获取公开公告列表成功"
    )
