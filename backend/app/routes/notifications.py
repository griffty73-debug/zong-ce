from flask import Blueprint, jsonify

from ..agents import NotificationAgent
from .helpers import current_user

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.get("/list")
def list_notifications():
    user = current_user()
    return jsonify(NotificationAgent().list(user))


@notifications_bp.get("/unread-count")
def unread_count():
    user = current_user()
    return jsonify(NotificationAgent().unread_count(user))


@notifications_bp.post("/<int:notif_id>/read")
def mark_read(notif_id: int):
    user = current_user()
    return jsonify(NotificationAgent().mark_read(user, notif_id))


@notifications_bp.post("/read-all")
def mark_all_read():
    user = current_user()
    return jsonify(NotificationAgent().mark_all_read(user))


@notifications_bp.delete("/<int:notif_id>")
def delete(notif_id: int):
    user = current_user()
    return jsonify(NotificationAgent().delete(user, notif_id))
