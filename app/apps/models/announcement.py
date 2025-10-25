from tortoise import fields

from apps.models.base import BaseModel


class Announcement(BaseModel):
    """公告模型"""
    
    title = fields.CharField(max_length=200, description="公告标题")
    content = fields.TextField(description="公告内容")

    # 发布状态
    status = fields.CharField(max_length=20, default="draft", description="状态：draft/published/archived")
    
    # 时间管理
    publish_time = fields.DatetimeField(null=True, description="发布时间")
    expire_time = fields.DatetimeField(null=True, description="过期时间")
    
    # 创建者信息
    created_by_user_id = fields.IntField(description="创建者用户ID")

    class Meta:
        table = "announcements"
        ordering = ["-is_pinned", "-priority", "-created_at"]
        table_description = "公告表"
    
    def __str__(self):
        return f"Announcement({self.id}): {self.title}"
