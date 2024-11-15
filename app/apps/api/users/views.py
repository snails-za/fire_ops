from fastapi import APIRouter

from apps.form.users.form import UserModel
from apps.models.users.models import User

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.post("/list", summary="获取用户列表", description="获取用户列表")
async def add_user(user: UserModel):
    rv = await User.create(nickname=user.name)
    return rv.to_dict()


@router.delete("/users/{uid}", summary="删除用户", description="删除用户")
async def delete_user(uid: int):
    user = await User.get_or_404(uid)
    await user.delete()
    return dict(id=uid)



