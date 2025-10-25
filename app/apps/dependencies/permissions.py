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
    USER = "user"      # 普通用户
    ADMIN = "admin"    # 管理员


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
        "is_user": user.role == UserRole.USER,
        "role": user.role
    }
