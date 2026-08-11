from tortoise import fields

from apps.models.base import BaseModel


class AppVersion(BaseModel):
    """App 发版记录：后台上传包，移动端按 version_code 检测更新。"""

    platform = fields.CharField(
        max_length=20, default="android", description="平台：android"
    )
    version_name = fields.CharField(max_length=32, description="版本号名称，如 1.0.1")
    version_code = fields.IntField(description="版本号整数，用于比较，如 101")
    package_type = fields.CharField(
        max_length=10, description="包类型：apk(整包) / wgt(热更新)"
    )
    file_path = fields.CharField(max_length=500, description="包文件访问路径")
    file_size = fields.BigIntField(default=0, description="文件大小（字节）")
    force_update = fields.BooleanField(default=False, description="是否强制更新")
    changelog = fields.TextField(null=True, description="更新说明")
    status = fields.CharField(
        max_length=20,
        default="draft",
        description="状态：draft/published/archived",
    )
    published_at = fields.DatetimeField(null=True, description="上线时间")
    created_by_user_id = fields.IntField(null=True, description="创建者用户ID")

    class Meta:
        table = "app_versions"
        ordering = ["-version_code", "-id"]
        table_description = "App版本发版表"

    def __str__(self):
        return f"AppVersion({self.platform}:{self.version_name}/{self.version_code})"
