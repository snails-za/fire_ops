from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

class DeviceIn(BaseModel):
    name: Optional[str] = Field(None, description="设备名称")
    address: Optional[str] = Field(None, description="地址")
    location: Optional[List[float]] = Field(None, description="设备位置，经纬度 [lng, lat]")
    image: Optional[str] = Field(None, description="图片路径")
    status: Optional[str] = Field(None, description="设备状态")
    install_date: Optional[date] = Field(None, description="安装日期")
    bak: Optional[str] = Field(None, description="备注")

class DeviceOut(DeviceIn):
    id: int
