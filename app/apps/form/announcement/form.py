"""
公告表单验证
"""
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime


class AnnouncementCreateForm(BaseModel):
    """创建公告表单"""
    title: str = Field(..., min_length=1, max_length=200, description="公告标题")
    content: str = Field(..., min_length=1, description="公告内容")
    publish_time: Optional[datetime] = Field(None, description="发布时间")
    expire_time: Optional[datetime] = Field(None, description="过期时间")
    
    @validator('expire_time')
    def validate_expire_time(cls, v, values):
        if v and 'publish_time' in values and values['publish_time']:
            if v <= values['publish_time']:
                raise ValueError('过期时间必须晚于发布时间')
        return v


class AnnouncementUpdateForm(BaseModel):
    """更新公告表单"""
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="公告标题")
    content: Optional[str] = Field(None, min_length=1, description="公告内容")
    status: Optional[str] = Field(None, description="状态")
    publish_time: Optional[datetime] = Field(None, description="发布时间")
    expire_time: Optional[datetime] = Field(None, description="过期时间")
    
    @validator('status')
    def validate_status(cls, v):
        if v and v not in ['draft', 'published', 'archived']:
            raise ValueError('状态必须是 draft、published 或 archived')
        return v


class AnnouncementQueryForm(BaseModel):
    """公告查询表单"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    status: Optional[str] = Field(None, description="状态筛选")
    keyword: Optional[str] = Field(None, description="关键词搜索")


