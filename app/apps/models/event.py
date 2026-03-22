from tortoise import fields
from apps.models.base import BaseModel


class Event(BaseModel):
    """事件模型 - 以事件为核心的处理流程"""
    
    # 事件基本信息
    title = fields.CharField(max_length=200, description="事件标题，如：3号楼・烟感告警 (A区 2F)")
    level = fields.CharField(max_length=20, default="medium", description="事件等级：高(high)、中(medium)、低(low)")
    status = fields.CharField(max_length=20, default="wait", description="事件状态：待处理(wait)、处理中(processing)、已关闭(closed)")
    
    # 关联设备（名称/地址等一律从 Device 表联查，不在事件表冗余存储）
    device = fields.ForeignKeyField("models.Device", related_name="events", on_delete=fields.CASCADE, null=True, description="关联设备")
    location = fields.CharField(max_length=200, null=True, description="位置信息，如：3号楼A区2F")

    # 负责人（仅为兼容历史表结构和索引保留，不参与当前业务逻辑）
    responsible_user = fields.ForeignKeyField(
        "models.User",
        related_name="responsible_events",
        on_delete=fields.SET_NULL,
        null=True,
        description="负责人（历史字段，当前业务未使用）",
    )
    
    class Meta:
        table = "event"
        ordering = ["-created_at"]
        indexes = [
            ("status",),
            ("device_id", "status"),
            ("responsible_user_id", "status"),
        ]
        description = "事件表"
    
    def __str__(self):
        return f"Event({self.id}): {self.title}"


class EventMessage(BaseModel):
    """事件消息模型 - 事件会话中的消息"""
    
    event = fields.ForeignKeyField("models.Event", related_name="messages", on_delete=fields.CASCADE, description="所属事件")
    user = fields.ForeignKeyField("models.User", related_name="event_messages", on_delete=fields.SET_NULL, null=True, description="发送用户（null表示系统消息）")
    username = fields.CharField(max_length=50, null=True, description="用户名（冗余字段）")
    user_role = fields.CharField(max_length=20, null=True, description="用户角色（冗余字段）")
    
    # 消息内容
    content = fields.TextField(description="消息内容")
    message_type = fields.CharField(max_length=20, default="user", description="消息类型：user(用户消息)、system(系统消息)")
    
    class Meta:
        table = "event_message"
        ordering = ["created_at"]
        indexes = [
            ("event_id", "created_at"),
        ]
        description = "事件消息表"
    
    def __str__(self):
        return f"EventMessage({self.id}): {self.content[:50]}"


