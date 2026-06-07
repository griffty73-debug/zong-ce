from __future__ import annotations

from flask import abort

from ..extensions import db
from ..models import Notification, User, utc_now


class NotificationAgent:
    @staticmethod
    def push(
        *,
        user_id: int,
        type: str,
        title: str,
        content: str,
        link: str | None = None,
        related_id: int | None = None,
    ) -> Notification:
        notif = Notification(
            user_id=user_id,
            type=type,
            title=title,
            content=content,
            link=link,
            related_id=related_id,
        )
        db.session.add(notif)
        return notif

    def list(self, user: User, only_unread: bool = False) -> dict:
        query = Notification.query.filter_by(user_id=user.id)
        if only_unread:
            query = query.filter_by(is_read=False)
        items = query.order_by(Notification.created_at.desc()).limit(80).all()
        unread = Notification.query.filter_by(user_id=user.id, is_read=False).count()
        return {
            "items": [item.to_dict() for item in items],
            "unreadCount": unread,
        }

    def unread_count(self, user: User) -> dict:
        unread = Notification.query.filter_by(user_id=user.id, is_read=False).count()
        return {"unreadCount": unread}

    def mark_read(self, user: User, notif_id: int) -> dict:
        notif = db.session.get(Notification, notif_id)
        if not notif or notif.user_id != user.id:
            abort(404, description="通知不存在")
        notif.is_read = True
        db.session.commit()
        return notif.to_dict()

    def mark_all_read(self, user: User) -> dict:
        Notification.query.filter_by(user_id=user.id, is_read=False).update({Notification.is_read: True})
        db.session.commit()
        return {"message": "已全部标记为已读"}

    def delete(self, user: User, notif_id: int) -> dict:
        notif = db.session.get(Notification, notif_id)
        if not notif or notif.user_id != user.id:
            abort(404, description="通知不存在")
        db.session.delete(notif)
        db.session.commit()
        return {"message": "已删除"}
