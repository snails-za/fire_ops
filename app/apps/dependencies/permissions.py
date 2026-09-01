"""
权限管理模块

正式角色仅 3 个：
- admin：管理员（可登后台，全量数据）
- leader：班长（App 全量设备/事件，不可登后台）
- maintainer：维护人员（仅本人相关设备/事件）
"""

from typing import Optional

from fastapi import HTTPException, Depends

from apps.dependencies.auth import get_current_user
from apps.models.user import User


class UserRole:
    ADMIN = "admin"
    LEADER = "leader"
    MAINTAINER = "maintainer"
    ALL = (ADMIN, LEADER, MAINTAINER)


def normalize_role(role: Optional[str]) -> str:
    """校验并返回正式角色；非法值回落为 maintainer。"""
    value = (role or "").strip()
    if value in UserRole.ALL:
        return value
    return UserRole.MAINTAINER


def effective_role(user: User) -> str:
    return normalize_role(getattr(user, "role", None))


def is_admin(user: User) -> bool:
    return effective_role(user) == UserRole.ADMIN


def is_privileged(user: User) -> bool:
    """管理员或班长：可看全部设备/事件。"""
    return effective_role(user) in (UserRole.ADMIN, UserRole.LEADER)


async def check_admin_permission(user: User = Depends(get_current_user)):
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="只有管理员可以访问后台系统")
    return user
