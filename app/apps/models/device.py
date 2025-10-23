from typing import List

from tortoise import fields

from apps.models.base import BaseModel


class Device(BaseModel):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, null=True, index=True, description="设备名称")
    address = fields.CharField(max_length=100, null=True, description="地址")
    location = fields.JSONField(null=True, description="设备位置")
    images: List[str] = fields.JSONField(null=True, description="设备图片")
    status = fields.CharField(max_length=50, null=True,description="设备状态")
    install_date = fields.DateField(null=True, description="安装日期")
    installer = fields.CharField(max_length=50, null=True, description="安装人")
    contact = fields.CharField(max_length=11, null=True, description="联系人")
    remark = fields.TextField(null=True, description="备注")
    created_by_user_id = fields.IntField(null=True, description="创建用户ID")

    class Meta:
        table = "device"
        ordering = ["-id"]
        unique_together = ("name", "address")
        indexes = [
            ("name", "status", "install_date"),
        ]
        description = "设备表"

    def __str__(self):
        return self.name


