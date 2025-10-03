from tortoise import fields
from apps.models.base import BaseModel


class Document(BaseModel):
    """文档模型"""
    id = fields.IntField(pk=True, description="文档ID")
    filename = fields.CharField(max_length=255, description="文件名")
    original_filename = fields.CharField(max_length=255, description="原始文件名")
    file_path = fields.CharField(max_length=500, description="文件路径")
    file_size = fields.IntField(description="文件大小(字节)")
    file_type = fields.CharField(max_length=50, description="文件类型")
    content = fields.TextField(description="文档内容")
    status = fields.CharField(max_length=20, default="queued", description="处理状态: queued, processing, completed, failed")
    task_id = fields.CharField(max_length=255, null=True, description="Celery任务ID")
    upload_time = fields.DatetimeField(auto_now_add=True, description="上传时间")
    process_time = fields.DatetimeField(null=True, description="处理完成时间")
    error_message = fields.TextField(null=True, description="错误信息")
    
    class Meta:
        table = "document"
        ordering = ["-upload_time"]
        description = "文档表"


class DocumentChunk(BaseModel):
    """文档分块模型"""
    id = fields.IntField(pk=True, description="分块ID")
    document = fields.ForeignKeyField("models.Document", related_name="chunks", on_delete=fields.CASCADE, description="所属文档")
    chunk_index = fields.IntField(description="分块索引")
    content = fields.TextField(description="分块内容")
    content_length = fields.IntField(description="内容长度")
    metadata = fields.JSONField(null=True, description="元数据")
    
    class Meta:
        table = "document_chunk"
        ordering = ["document_id", "chunk_index"]
        description = "文档分块表"


class ChatSession(BaseModel):
    """聊天会话模型"""
    id = fields.IntField(pk=True, description="会话ID")
    user = fields.ForeignKeyField("models.User", related_name="chat_sessions", on_delete=fields.CASCADE, description="用户")
    session_name = fields.CharField(max_length=100, description="会话名称")
    created_time = fields.DatetimeField(auto_now_add=True, description="创建时间")
    last_active = fields.DatetimeField(auto_now=True, description="最后活跃时间")
    
    class Meta:
        table = "chat_session"
        ordering = ["-last_active"]
        description = "聊天会话表"


class ChatMessage(BaseModel):
    """聊天消息模型"""
    id = fields.IntField(pk=True, description="消息ID")
    session = fields.ForeignKeyField("models.ChatSession", related_name="messages", on_delete=fields.CASCADE, description="所属会话")
    role = fields.CharField(max_length=20, description="角色: user, assistant, system")
    content = fields.TextField(description="消息内容")
    timestamp = fields.DatetimeField(auto_now_add=True, description="时间戳")
    metadata = fields.JSONField(null=True, description="元数据")
    
    class Meta:
        table = "chat_message"
        ordering = ["session_id", "timestamp"]
        description = "聊天消息表"
