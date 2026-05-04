from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from tortoise.expressions import Q

from apps.dependencies.auth import get_current_user
from apps.dependencies.permissions import check_admin_permission
from apps.form.communication import DirectMessageCreate
from apps.models.communication import DirectConversation, DirectMessage
from apps.models.user import FriendRequest, User
from apps.utils import response

router = APIRouter(prefix="/direct", tags=["好友通讯"])


def display_name(user: Optional[User]) -> str:
    if not user:
        return "未知用户"
    return user.fullname or user.username or "未知用户"


def user_to_dict(user: Optional[User]) -> dict | None:
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "fullname": user.fullname,
        "display_name": display_name(user),
        "head": user.head,
        "role": user.role,
        "contact": user.contact,
    }


async def are_friends(user_id: int, friend_id: int) -> bool:
    return await FriendRequest.filter(
        Q(requester_id=user_id, receiver_id=friend_id) | Q(requester_id=friend_id, receiver_id=user_id),
        is_accept=True,
    ).exists()


def ordered_pair(user_id: int, friend_id: int) -> tuple[int, int]:
    return (user_id, friend_id) if user_id < friend_id else (friend_id, user_id)


async def get_conversation_for_user(conversation_id: int, user: User) -> DirectConversation | None:
    return await DirectConversation.filter(
        Q(user_a_id=user.id) | Q(user_b_id=user.id),
        id=conversation_id,
    ).prefetch_related("user_a", "user_b").first()


async def conversation_to_dict(conversation: DirectConversation, current_user: Optional[User] = None) -> dict:
    await conversation.fetch_related("user_a", "user_b")
    peer = None
    if current_user:
        peer = conversation.user_b if conversation.user_a_id == current_user.id else conversation.user_a
    unread = 0
    if current_user:
        unread = await DirectMessage.filter(
            conversation_id=conversation.id,
            receiver_id=current_user.id,
            is_read=False,
        ).count()
    return {
        "id": conversation.id,
        "user_a": user_to_dict(conversation.user_a),
        "user_b": user_to_dict(conversation.user_b),
        "peer": user_to_dict(peer),
        "last_message": conversation.last_message,
        "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None,
        "unread_count": unread,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
    }


async def message_to_dict(message: DirectMessage) -> dict:
    await message.fetch_related("sender", "receiver")
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "sender_id": message.sender_id,
        "receiver_id": message.receiver_id,
        "sender": user_to_dict(message.sender),
        "receiver": user_to_dict(message.receiver),
        "content": message.content,
        "is_read": message.is_read,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


@router.get("/conversations", summary="我的通讯会话", dependencies=[Depends(get_current_user)])
async def list_conversations(user: User = Depends(get_current_user)):
    query = (
        DirectConversation.filter(Q(user_a_id=user.id) | Q(user_b_id=user.id))
        .order_by("-last_message_at", "-updated_at")
        .prefetch_related("user_a", "user_b")
    )
    conversations = await query
    return response(data=[await conversation_to_dict(item, user) for item in conversations], message="获取会话列表成功")


@router.post("/conversations/{friend_id}", summary="创建或获取好友会话", dependencies=[Depends(get_current_user)])
async def get_or_create_conversation(friend_id: int, user: User = Depends(get_current_user)):
    if friend_id == user.id:
        return response(code=0, message="不能和自己通讯")
    friend = await User.get_or_none(id=friend_id)
    if not friend:
        return response(code=404, message="用户不存在")
    if not await are_friends(user.id, friend_id):
        return response(code=403, message="需要先添加为联系人")

    user_a_id, user_b_id = ordered_pair(user.id, friend_id)
    conversation = await DirectConversation.get_or_none(user_a_id=user_a_id, user_b_id=user_b_id)
    if not conversation:
        conversation = await DirectConversation.create(user_a_id=user_a_id, user_b_id=user_b_id)
    return response(data=await conversation_to_dict(conversation, user), message="获取会话成功")


@router.get("/conversations/{conversation_id}/messages", summary="通讯消息列表", dependencies=[Depends(get_current_user)])
async def list_messages(
    conversation_id: int,
    page: int = 1,
    page_size: int = 50,
    user: User = Depends(get_current_user),
):
    conversation = await get_conversation_for_user(conversation_id, user)
    if not conversation:
        return response(code=404, message="会话不存在或无权访问")

    query = DirectMessage.filter(conversation_id=conversation_id).order_by("created_at")
    total = await query.count()
    messages = await query.offset((page - 1) * page_size).limit(page_size).prefetch_related("sender", "receiver")
    await DirectMessage.filter(conversation_id=conversation_id, receiver_id=user.id, is_read=False).update(is_read=True)
    return response(
        data={
            "items": [await message_to_dict(item) for item in messages],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        message="获取消息成功",
    )


@router.post("/conversations/{conversation_id}/messages", summary="发送通讯消息", dependencies=[Depends(get_current_user)])
async def send_message(
    conversation_id: int,
    form: DirectMessageCreate,
    user: User = Depends(get_current_user),
):
    conversation = await get_conversation_for_user(conversation_id, user)
    if not conversation:
        return response(code=404, message="会话不存在或无权访问")
    receiver_id = conversation.user_b_id if conversation.user_a_id == user.id else conversation.user_a_id
    if not await are_friends(user.id, receiver_id):
        return response(code=403, message="联系人关系已失效")

    content = form.content.strip()
    if not content:
        return response(code=0, message="消息内容不能为空")

    message = await DirectMessage.create(
        conversation_id=conversation.id,
        sender_id=user.id,
        receiver_id=receiver_id,
        content=content,
    )
    now = datetime.now()
    await DirectConversation.filter(id=conversation.id).update(
        last_message=content[:500],
        last_message_at=now,
        updated_at=now,
    )
    return response(data=await message_to_dict(message), message="发送成功")


@router.get("/admin/conversations", summary="后台通讯会话列表", dependencies=[Depends(check_admin_permission)])
async def admin_list_conversations(page: int = 1, page_size: int = 20):
    query = DirectConversation.all().order_by("-last_message_at", "-updated_at").prefetch_related("user_a", "user_b")
    total = await query.count()
    conversations = await query.offset((page - 1) * page_size).limit(page_size)
    return response(
        data=[await conversation_to_dict(item) for item in conversations],
        total=total,
        total_page=(total + page_size - 1) // page_size,
        message="获取通讯会话成功",
    )


@router.get("/admin/conversations/{conversation_id}/messages", summary="后台通讯消息列表", dependencies=[Depends(check_admin_permission)])
async def admin_list_messages(conversation_id: int, page: int = 1, page_size: int = 100):
    if not await DirectConversation.filter(id=conversation_id).exists():
        return response(code=404, message="会话不存在")
    query = DirectMessage.filter(conversation_id=conversation_id).order_by("created_at")
    total = await query.count()
    messages = await query.offset((page - 1) * page_size).limit(page_size).prefetch_related("sender", "receiver")
    return response(
        data={
            "items": [await message_to_dict(item) for item in messages],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        message="获取通讯消息成功",
    )
