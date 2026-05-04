from tortoise import fields

from apps.models.base import BaseModel


class DirectConversation(BaseModel):
    """好友一对一会话。"""

    user_a = fields.ForeignKeyField(
        "models.User",
        related_name="direct_conversations_a",
        on_delete=fields.CASCADE,
        description="会话用户A",
    )
    user_b = fields.ForeignKeyField(
        "models.User",
        related_name="direct_conversations_b",
        on_delete=fields.CASCADE,
        description="会话用户B",
    )
    last_message = fields.CharField(max_length=500, null=True, description="最后一条消息")
    last_message_at = fields.DatetimeField(null=True, description="最后消息时间")

    class Meta:
        table = "direct_conversation"
        ordering = ["-last_message_at", "-updated_at"]
        indexes = [
            ("user_a_id", "user_b_id"),
            ("last_message_at",),
        ]
        unique_together = (("user_a_id", "user_b_id"),)


class DirectMessage(BaseModel):
    """好友一对一消息。"""

    conversation = fields.ForeignKeyField(
        "models.DirectConversation",
        related_name="messages",
        on_delete=fields.CASCADE,
        description="所属会话",
    )
    sender = fields.ForeignKeyField(
        "models.User",
        related_name="direct_messages_sent",
        on_delete=fields.SET_NULL,
        null=True,
        description="发送人",
    )
    receiver = fields.ForeignKeyField(
        "models.User",
        related_name="direct_messages_received",
        on_delete=fields.SET_NULL,
        null=True,
        description="接收人",
    )
    content = fields.TextField(description="消息内容")
    is_read = fields.BooleanField(default=False, description="是否已读")

    class Meta:
        table = "direct_message"
        ordering = ["created_at"]
        indexes = [
            ("conversation_id", "created_at"),
            ("receiver_id", "is_read"),
        ]
