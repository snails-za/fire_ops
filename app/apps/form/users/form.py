from typing import Optional

from pydantic import BaseModel, Field

class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class UserBase(BaseModel):
    username: str = Field(..., min_length=2, max_length=20, title="用户名", description="用户名长度在3到20之间")
    fullname: str = Field(..., min_length=1, max_length=50, title="姓名", description="用户真实姓名或展示名称")
    head: Optional[str] = Field(None, title="头像", description="头像路径")
    email: Optional[str] = Field(None, pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", title="邮箱",
                       description="邮箱格式不正确")
    contact: Optional[str] = Field(None, pattern=r"^1[3-9]\d{9}$", title="联系方式", description="手机号格式不正确")


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100, title="密码", description="密码长度在8到20之间")
    role: Optional[str] = Field(default="user", title="用户角色", description="用户角色: user, admin")


class UserUpdate(UserBase):
    password: Optional[str] = Field(None, min_length=8, max_length=100, title="密码", description="密码长度在8到20之间，不修改密码时不传此字段")
    role: Optional[str] = Field(default=None, title="用户角色", description="用户角色: user, admin, leader, maintainer")


class ChangePasswordForm(BaseModel):
    old_password: str = Field(..., min_length=8, max_length=100, title="原密码")
    new_password: str = Field(..., min_length=8, max_length=100, title="新密码")


class ProcessApplyRequest(BaseModel):
    accept: bool
