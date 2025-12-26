"""
事件表单验证
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class EventCreateForm(BaseModel):
    """创建事件表单"""
    title: str = Field(..., min_length=1, max_length=200, description="事件标题")
    level: Optional[str] = Field("normal", description="事件等级：严重(severe)、高(high)、中(medium)、低(low)、正常(normal)")
    device_id: Optional[int] = Field(None, description="关联设备ID")
    location: Optional[str] = Field(None, description="位置信息")
    circuit: Optional[str] = Field(None, description="回路信息")
    suggestion: Optional[str] = Field(None, description="建议/处理建议")


class EventUpdateForm(BaseModel):
    """更新事件表单"""
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="事件标题")
    status: Optional[str] = Field(None, description="事件状态：告警(alarm)、处理中(processing)、已关闭(closed)")
    level: Optional[str] = Field(None, description="事件等级")
    responsible_user_id: Optional[int] = Field(None, description="负责人用户ID")
    collaborator_user_id: Optional[int] = Field(None, description="协同人用户ID")
    suggestion: Optional[str] = Field(None, description="建议/处理建议")
    conclusion: Optional[str] = Field(None, description="结论/处理结果")
    estimated_arrival: Optional[str] = Field(None, description="预计到场时间")


class EventMessageForm(BaseModel):
    """事件消息表单"""
    content: str = Field(..., min_length=1, max_length=2000, description="消息内容（建议≤200字）")


class EventProgressForm(BaseModel):
    """事件进度表单"""
    progress_type: str = Field(..., description="进度类型")
    description: str = Field(..., description="进度描述")
    status: Optional[str] = Field("pending", description="进度状态：pending(待处理)、in_progress(进行中)、completed(已完成)")

