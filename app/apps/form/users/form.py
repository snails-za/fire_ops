from typing import Optional

from pydantic import BaseModel, Field


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, title="用户名", description="用户名长度在3到20之间")
    email: Optional[str] = Field(None, pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", title="邮箱",
                       description="邮箱格式不正确")


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=20, title="密码", description="密码长度在8到20之间")


class UserInDB(UserBase):
    id: int

    class Config:
        orm_mode = True
