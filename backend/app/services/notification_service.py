"""通知服务 —— 创建/列表/已读/未读数 + WebSocket 实时推送

所有通知发送均用 try/except 包裹，失败不影响主流程。
"""

import logging
from datetime import datetime

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.schemas.notification import NotificationOut, UnreadCountOut
from app.schemas.common import PaginatedData
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)


async def create_notification(
    db: AsyncSession,
    *,
    user_id: int,
    type: str,
    title: str,
    content: str,
    link: str | None = None,
) -> Notification | None:
    """创建通知 + WebSocket 实时推送（不阻塞主流程）"""
    try:
        notif = Notification(
            user_id=user_id,
            type=type,
            title=title,
            content=content,
            link=link,
            is_read=False,
        )
        db.add(notif)
        await db.flush()

        # WebSocket 实时推送（异步，不阻塞）
        try:
            await manager.send_to_user(user_id, {
                "type": "notification",
                "data": {
                    "id": notif.id,
                    "type": notif.type,
                    "title": notif.title,
                    "content": notif.content,
                    "link": notif.link,
                    "is_read": False,
                    "created_at": notif.created_at.isoformat() if notif.created_at else None,
                },
            })
        except Exception:
            logger.debug(f"WebSocket 推送失败: user_id={user_id}", exc_info=True)

        return notif
    except Exception:
        logger.error(f"创建通知失败: user_id={user_id}, type={type}", exc_info=True)
        return None


async def list_notifications(
    db: AsyncSession,
    *,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """我的通知列表（按时间倒序）"""
    conditions = [Notification.user_id == user_id]

    count_stmt = select(func.count()).select_from(Notification).where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    items = [NotificationOut.model_validate(n) for n in result.scalars().all()]

    return PaginatedData(items=items, total=total, page=page, page_size=page_size)


async def get_unread_count(db: AsyncSession, *, user_id: int) -> UnreadCountOut:
    """获取当前用户未读通知数量"""
    stmt = select(func.count()).select_from(Notification).where(
        Notification.user_id == user_id,
        Notification.is_read == False,
    )
    count = (await db.execute(stmt)).scalar() or 0
    return UnreadCountOut(count=count)


async def mark_read(db: AsyncSession, *, notification_id: int, user_id: int) -> None:
    """标记单条通知为已读（仅操作自己的通知）"""
    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .values(is_read=True)
    )
    await db.flush()


async def mark_all_read(db: AsyncSession, *, user_id: int) -> None:
    """标记当前用户全部通知为已读"""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)
        .values(is_read=True)
    )
    await db.flush()


async def clear_related(db: AsyncSession, *, user_id: int, types: list[str]) -> None:
    """操作完成后删除相关通知（不阻塞主流程）"""
    try:
        from sqlalchemy import delete
        await db.execute(
            delete(Notification).where(
                Notification.user_id == user_id,
                Notification.type.in_(types),
            )
        )
        await db.flush()
    except Exception:
        logger.debug(f"清除通知失败: user_id={user_id}, types={types}", exc_info=True)
