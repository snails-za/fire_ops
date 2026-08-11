"""
权限管理模块

正式角色仅 3 个：
- admin：管理员（可登后台，全量数据）
- leader：班长（App 全量设备/事件，不可登后台）
- maintainer：维护人员（仅本人相关设备/事件）
"""

from functools import wraps
from typing import List, Optional

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


def is_leader(user: User) -> bool:
    return effective_role(user) == UserRole.LEADER


def is_maintainer(user: User) -> bool:
    return effective_role(user) == UserRole.MAINTAINER


def is_privileged(user: User) -> bool:
    """管理员或班长：可看全部设备/事件。"""
    return effective_role(user) in (UserRole.ADMIN, UserRole.LEADER)


def require_role(allowed_roles: List[str]):
    allowed = {normalize_role(r) for r in allowed_roles}

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get("user") or args[0] if args else None

            if not user:
                try:
                    user = await get_current_user()
                except Exception:
                    raise HTTPException(status_code=401, detail="未登录")

            if effective_role(user) not in allowed:
                raise HTTPException(
                    status_code=402,
                    detail=f"权限不足，需要角色: {', '.join(sorted(allowed))}",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_admin(func):
    return require_role([UserRole.ADMIN])(func)


async def check_admin_permission(user: User = Depends(get_current_user)):
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="只有管理员可以访问后台系统")
    return user


async def get_user_with_role_check(user: User = Depends(get_current_user)):
    role = effective_role(user)
    return {
        "user": user,
        "is_admin": role == UserRole.ADMIN,
        "is_leader": role == UserRole.LEADER,
        "is_maintainer": role == UserRole.MAINTAINER,
        "role": role,
    }


def can_view_all_events(user: User) -> bool:
    return is_privileged(user)


def can_view_all_devices(user: User) -> bool:
    return is_privileged(user)


def can_manage_event(user: User, event_responsible_user_id: int = None) -> bool:
    if is_privileged(user):
        return True
    if event_responsible_user_id and event_responsible_user_id == user.id:
        return True
    return False
