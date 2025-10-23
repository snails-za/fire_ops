from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import date
import re

class DeviceIn(BaseModel):
    name: Optional[str] = Field(None, description="设备名称")
    address: Optional[str] = Field(None, description="地址")
    location: Optional[List[float]] = Field(None, description="设备位置，经纬度 [lng, lat]")
    images: List[str] = Field(..., description="图片路径")
    status: Optional[str] = Field(None, description="设备状态")
    install_date: Optional[date] = Field(None, description="安装日期")
    installer: Optional[str] = Field(None, description="安装人")
    contact: Optional[str] = Field(None, description="联系方式（手机号）")
    remark: Optional[str] = Field(None, description="备注")

    @field_validator('contact')
    @classmethod
    def validate_phone(cls, v):
        if v is None or v == '':
            return v
        # 中国手机号格式：11位数字，以1开头
        phone_pattern = r'^1[3-9]\d{9}$'
        if not re.match(phone_pattern, v):
            raise ValueError('手机号格式不正确，请输入11位数字的手机号')
        return v

class DeviceUpdate(BaseModel):
    """设备更新表单，所有字段都是可选的"""
    name: Optional[str] = Field(None, description="设备名称")
    address: Optional[str] = Field(None, description="地址")
    location: Optional[List[float]] = Field(None, description="设备位置，经纬度 [lng, lat]")
    images: Optional[List[str]] = Field(None, description="图片路径")
    status: Optional[str] = Field(None, description="设备状态")
    install_date: Optional[date] = Field(None, description="安装日期")
    installer: Optional[str] = Field(None, description="安装人")
    contact: Optional[str] = Field(None, description="联系方式（手机号）")
    remark: Optional[str] = Field(None, description="备注")

    @field_validator('contact')
    @classmethod
    def validate_phone(cls, v):
        if v is None or v == '':
            return v
        # 中国手机号格式：11位数字，以1开头
        phone_pattern = r'^1[3-9]\d{9}$'
        if not re.match(phone_pattern, v):
            raise ValueError('手机号格式不正确，请输入11位数字的手机号')
        return v

class DeviceOut(DeviceIn):
    id: int
    created_by_user_id: Optional[int] = Field(None, description="创建用户ID")
