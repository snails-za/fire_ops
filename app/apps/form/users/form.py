from typing import Optional

from pydantic import BaseModel, Field

class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class UserBase(BaseModel):
    username: str = Field(..., min_length=2, max_length=20, title="用户名", description="用户名长度在3到20之间")
    head: Optional[str] = Field(None, title="头像", description="头像路径")
    email: Optional[str] = Field(None, pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", title="邮箱",
                       description="邮箱格式不正确")


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100, title="密码", description="密码长度在8到20之间")
    role: Optional[str] = Field(default="user", title="用户角色", description="用户角色: user, admin")


class ProcessApplyRequest(BaseModel):
    accept: bool