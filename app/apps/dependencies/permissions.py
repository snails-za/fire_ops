"""
权限管理模块
用于检查用户角色权限
"""

from functools import wraps
from typing import List

from fastapi import HTTPException, Depends

from apps.dependencies.auth import get_current_user
from apps.models.user import User


class UserRole:
    """用户角色常量"""
    USER = "user"          # 普通用户
    ADMIN = "admin"        # 管理员（后台）
    LEADER = "leader"      # 班长
    MAINTAINER = "maintainer"  # 维护人员


def require_role(allowed_roles: List[str]):
    """
    权限检查装饰器
    
    Args:
        allowed_roles: 允许的角色列表，如 ["admin"] 或 ["user", "admin"]
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 获取当前用户
            user = kwargs.get('user') or args[0] if args else None
            
            if not user:
                # 如果没有直接传入用户，尝试从依赖注入获取
                try:
                    user = await get_current_user()
                except Exception as _:
                    raise HTTPException(status_code=401, detail="未登录")
            
            # 检查用户角色
            if user.role not in allowed_roles:
                raise HTTPException(
                    status_code=402,
                    detail=f"权限不足，需要角色: {', '.join(allowed_roles)}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_admin(func):
    """管理员权限装饰器"""
    return require_role([UserRole.ADMIN])(func)


def require_user_or_admin(func):
    """用户或管理员权限装饰器"""
    return require_role([UserRole.USER, UserRole.ADMIN])(func)


async def check_admin_permission(user: User = Depends(get_current_user)):
    """
    检查管理员权限的依赖注入函数
    
    Args:
        user: 当前登录用户
        
    Returns:
        User: 管理员用户
        
    Raises:
        HTTPException: 如果不是管理员
    """
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403, 
            detail="只有管理员可以访问后台系统"
        )
    return user


async def get_user_with_role_check(user: User = Depends(get_current_user)):
    """
    获取用户并返回角色信息
    
    Args:
        user: 当前登录用户
        
    Returns:
        dict: 包含用户信息和角色权限的字典
    """
    return {
        "user": user,
        "is_admin": user.role == UserRole.ADMIN,
        "is_leader": user.role == UserRole.LEADER,
        "is_maintainer": user.role == UserRole.MAINTAINER,
        "is_user": user.role == UserRole.USER,
        "role": user.role
    }


def can_view_all_events(user: User) -> bool:
    """
    检查用户是否可以查看所有事件
    
    Args:
        user: 当前用户
        
    Returns:
        bool: True表示可以查看所有事件（admin和leader），False表示只能查看自己负责的事件
    """
    return user.role in [UserRole.ADMIN, UserRole.LEADER]


def can_view_all_devices(user: User) -> bool:
    """
    检查用户是否可以查看所有设备
    
    Args:
        user: 当前用户
        
    Returns:
        bool: True表示可以查看所有设备（admin和leader），False表示只能查看自己创建的设备
    """
    return user.role in [UserRole.ADMIN, UserRole.LEADER]


def can_manage_event(user: User, event_responsible_user_id: int = None) -> bool:
    """
    检查用户是否可以管理事件
    
    Args:
        user: 当前用户
        event_responsible_user_id: 事件负责人ID
        
    Returns:
        bool: True表示可以管理事件（admin、leader或负责人本人）
    """
    if user.role in [UserRole.ADMIN, UserRole.LEADER]:
        return True
    if event_responsible_user_id and event_responsible_user_id == user.id:
        return True
    return False
