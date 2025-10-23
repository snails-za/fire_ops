from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

class DeviceIn(BaseModel):
    name: Optional[str] = Field(None, description="设备名称")
    address: Optional[str] = Field(None, description="地址")
    location: Optional[List[float]] = Field(None, description="设备位置，经纬度 [lng, lat]")
    images: List[str] = Field(..., description="图片路径")
    status: Optional[str] = Field(None, description="设备状态")
    install_date: Optional[date] = Field(None, description="安装日期")
    installer: Optional[str] = Field(None, description="安装人")
    contact: Optional[str] = Field(None, description="联系人")
    remark: Optional[str] = Field(None, description="备注")

class DeviceUpdate(BaseModel):
    """设备更新表单，所有字段都是可选的"""
    name: Optional[str] = Field(None, description="设备名称")
    address: Optional[str] = Field(None, description="地址")
    location: Optional[List[float]] = Field(None, description="设备位置，经纬度 [lng, lat]")
    images: Optional[List[str]] = Field(None, description="图片路径")
    status: Optional[str] = Field(None, description="设备状态")
    install_date: Optional[date] = Field(None, description="安装日期")
    installer: Optional[str] = Field(None, description="安装人")
    contact: Optional[str] = Field(None, description="联系人")
    remark: Optional[str] = Field(None, description="备注")

class DeviceOut(DeviceIn):
    id: int
    created_by_user_id: Optional[int] = Field(None, description="创建用户ID")
