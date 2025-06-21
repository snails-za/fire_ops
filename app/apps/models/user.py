from tortoise import fields

from apps.models.base import BaseModel


class User(BaseModel):
    id = fields.IntField(pk=True, description="用户ID")
    username = fields.CharField(max_length=20, unique=True, index=True, description="用户名")
    email = fields.CharField(null=True, max_length=50, unique=True, index=True, description="邮箱")
    password = fields.CharField(max_length=128, null=True, description="密码")
    head = fields.CharField(max_length=255, null=True, description="头像")
    pinyin = fields.CharField(max_length=255, null=True, description="用户名首字母")


class Contact(BaseModel):
    id = fields.IntField(pk=True, description="联系人ID")
    user = fields.ForeignKeyField("models.User", related_name="contacted_by", on_delete=fields.CASCADE,
                                  description="用户")
    contact = fields.ForeignKeyField("models.User", related_name="contact", on_delete=fields.CASCADE,
                                     description="联系人")
    is_star = fields.BooleanField(default=False, description="是否星标")


