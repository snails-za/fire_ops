from fastapi import APIRouter, BackgroundTasks

from apps.tasks.task import write_notification

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.post("/list", summary="获取用户列表", description="获取用户列表")
async def add_user():
    return {"message": "获取用户列表"}


@router.delete("/users/{uid}", summary="删除用户", description="删除用户")
async def delete_user(uid: int):
    return dict(id=uid)


@router.post("/send-notification/{email}", summary="发送通知", description="发送通知")
async def send_notification(email: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(write_notification, email, message="some notification")
    return {"message": "Notification sent in the background"}



