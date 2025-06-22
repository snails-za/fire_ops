from tortoise import fields

from apps.models.base import BaseModel


class User(BaseModel):
    id = fields.IntField(pk=True, description="用户ID")
    username = fields.CharField(max_length=20, unique=True, index=True, description="用户名")
    email = fields.CharField(null=True, max_length=50, unique=True, index=True, description="邮箱")
    password = fields.CharField(max_length=128, null=True, description="密码")
    head = fields.CharField(max_length=255, null=True, description="头像")
    pinyin = fields.CharField(max_length=255, null=True, description="用户名首字母")


class FriendRequest(BaseModel):
    id = fields.IntField(pk=True, description="联系人ID")
    requester = fields.ForeignKeyField("models.User", related_name="sent_requests", on_delete=fields.CASCADE,
                                  description="申请人")
    receiver = fields.ForeignKeyField("models.User", related_name="received_requests", on_delete=fields.CASCADE,
                                     description="接收人")
    is_star = fields.BooleanField(default=False, description="是否星标")
    is_accept = fields.BooleanField(default=None, null=True, description="是否接受")
    bak = fields.TextField(null=True, description="备注")


