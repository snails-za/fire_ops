from tortoise import fields
from apps.models.base import BaseModel


class Event(BaseModel):
    """事件模型 - 以事件为核心的处理流程"""
    
    # 事件基本信息
    title = fields.CharField(max_length=200, description="事件标题，如：3号楼・烟感告警 (A区 2F)")
    level = fields.CharField(max_length=20, default="normal", description="事件等级：严重(severe)、高(high)、中(medium)、低(low)、正常(normal)")
    status = fields.CharField(max_length=20, default="alarm", description="事件状态：告警(alarm)、处理中(processing)、已关闭(closed)")
    
    # 关联设备
    device = fields.ForeignKeyField("models.Device", related_name="events", on_delete=fields.CASCADE, null=True, description="关联设备")
    device_name = fields.CharField(max_length=100, null=True, description="设备名称（冗余字段，便于查询）")
    device_address = fields.CharField(max_length=100, null=True, description="设备地址（冗余字段）")
    location = fields.CharField(max_length=200, null=True, description="位置信息，如：3号楼A区2F")
    circuit = fields.CharField(max_length=50, null=True, description="回路信息，如：2-04")
    
    # 触发信息
    triggered_at = fields.DatetimeField(null=True, description="触发时间")
    triggered_by = fields.CharField(max_length=50, null=True, description="触发来源：系统/用户")
    
    # 负责人和协同人
    responsible_user = fields.ForeignKeyField("models.User", related_name="responsible_events", on_delete=fields.SET_NULL, null=True, description="负责人（维护人员）")
    responsible_username = fields.CharField(max_length=50, null=True, description="负责人用户名（冗余字段）")
    collaborator_user = fields.ForeignKeyField("models.User", related_name="collaborated_events", on_delete=fields.SET_NULL, null=True, description="协同人（值班员/班长）")
    collaborator_username = fields.CharField(max_length=50, null=True, description="协同人用户名（冗余字段）")
    
    # 处置信息
    suggestion = fields.TextField(null=True, description="建议/处理建议")
    conclusion = fields.TextField(null=True, description="结论/处理结果")
    estimated_arrival = fields.CharField(max_length=50, null=True, description="预计到场时间，如：5分钟")
    
    # 统计信息
    message_count = fields.IntField(default=0, description="消息数量")
    unread_count = fields.IntField(default=0, description="未读消息数量")
    
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
    
    # 已读状态
    is_read = fields.BooleanField(default=False, description="是否已读")
    read_at = fields.DatetimeField(null=True, description="已读时间")
    
    class Meta:
        table = "event_message"
        ordering = ["created_at"]
        indexes = [
            ("event_id", "created_at"),
            ("user_id", "is_read"),
        ]
        description = "事件消息表"
    
    def __str__(self):
        return f"EventMessage({self.id}): {self.content[:50]}"


class EventProgress(BaseModel):
    """事件进度模型 - 记录事件处置进度时间线"""
    
    event = fields.ForeignKeyField("models.Event", related_name="progresses", on_delete=fields.CASCADE, description="所属事件")
    progress_type = fields.CharField(max_length=50, description="进度类型：告警触发、派单/指派负责人、到场检查中、处理完成等")
    description = fields.TextField(description="进度描述")
    
    # 操作人
    operator = fields.ForeignKeyField("models.User", related_name="event_progresses", on_delete=fields.SET_NULL, null=True, description="操作人")
    operator_username = fields.CharField(max_length=50, null=True, description="操作人用户名（冗余字段）")
    
    # 进度状态
    status = fields.CharField(max_length=20, default="pending", description="进度状态：pending(待处理)、in_progress(进行中)、completed(已完成)")
    
    class Meta:
        table = "event_progress"
        ordering = ["created_at"]
        indexes = [
            ("event_id", "created_at"),
        ]
        description = "事件进度表"
    
    def __str__(self):
        return f"EventProgress({self.id}): {self.progress_type}"

