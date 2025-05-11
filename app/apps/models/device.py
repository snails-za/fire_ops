from tortoise import fields

from apps.models.base import BaseModel


class Device(BaseModel):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, null=True, description="设备名称")
    address = fields.CharField(max_length=100, null=True, description="地址")
    location = fields.JSONField(null=True, description="设备位置")
    image = fields.CharField(max_length=255, null=True, description="图片路径")
    status = fields.CharField(max_length=50, null=True,description="设备状态")
    install_date = fields.DateField(null=True, description="安装日期")
    bak = fields.TextField(null=True, description="备注")

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


