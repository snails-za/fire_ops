from pydantic import BaseModel, Field


class DirectMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000, title="消息内容")
