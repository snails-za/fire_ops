from tortoise import fields

from apps.models.base import BaseModel


class User(BaseModel):
    id = fields.IntField(pk=True, description="用户ID")
    username = fields.CharField(max_length=20, unique=True, index=True, description="用户名")
    email = fields.CharField(null=True, max_length=50, unique=True, index=True, description="邮箱")
    password = fields.CharField(max_length=128, null=True, description="密码")