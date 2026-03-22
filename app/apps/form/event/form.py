"""
事件表单验证
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class EventCreateForm(BaseModel):
    """创建事件表单"""
    title: str = Field(..., min_length=1, max_length=200, description="事件标题")
    level: Optional[str] = Field("medium", description="事件等级：高(high)、中(medium)、低(low)")
    device_id: Optional[int] = Field(None, description="关联设备ID")
    location: Optional[str] = Field(None, description="位置信息")


class EventUpdateForm(BaseModel):
    """更新事件表单"""
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="事件标题")
    status: Optional[str] = Field(None, description="事件状态：待处理(wait)、处理中(processing)、已关闭(closed)")
    level: Optional[str] = Field(None, description="事件等级")


class EventMessageForm(BaseModel):
    """事件消息表单"""
    content: str = Field(..., min_length=1, max_length=2000, description="消息内容（建议≤200字）")


