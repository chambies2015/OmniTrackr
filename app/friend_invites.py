"""Friend invite links: one reusable link per member that brings a friend in.

* A member shares ``/join/<token>``. The page names who invited the visitor.
* A visitor who signs up from it is recorded in ``FriendInviteSignup``; the two
  become friends when the new account's email is verified.
* A visitor who already has an account adds the inviter with one click.

Sharing the link is the inviter's consent and following it is the invitee's,
so no separate friend request is sent. Only new tables are used.
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from . import models
from .crud.friends import are_friends, create_friendship, create_notification

TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{16,32}")


def valid_token(token) -> bool:
    return isinstance(token, str) and TOKEN_RE.fullmatch(token) is not None


def link_for(db: Session, user, reset: bool = False) -> models.FriendInvite:
    """The member's invite link, created on first use. ``reset`` retires the old link."""
    invite = db.query(models.FriendInvite).filter(models.FriendInvite.user_id == user.id).first()
    if invite is None:
        invite = models.FriendInvite(user_id=user.id, token=secrets.token_urlsafe(16))
        db.add(invite)
    elif reset:
        invite.token = secrets.token_urlsafe(16)
        invite.created_at = datetime.utcnow()
    db.commit()
    db.refresh(invite)
    return invite


def inviter_for(db: Session, token) -> Optional[models.User]:
    """The active member behind an invite token, or None."""
    if not valid_token(token):
        return None
    invite = db.query(models.FriendInvite).filter(models.FriendInvite.token == token).first()
    if invite is None:
        return None
    user = db.query(models.User).filter(models.User.id == invite.user_id).first()
    return user if user is not None and user.is_active else None


def _clear_requests(db: Session, a: int, b: int) -> None:
    """Close any pending friend request between the two (the invite supersedes it)."""
    pending = db.query(models.FriendRequest).filter(
        ((models.FriendRequest.sender_id == a) & (models.FriendRequest.receiver_id == b))
        | ((models.FriendRequest.sender_id == b) & (models.FriendRequest.receiver_id == a)),
        models.FriendRequest.status == "pending").all()
    for request in pending:
        request.status = "accepted"
        db.query(models.Notification).filter(models.Notification.friend_request_id == request.id).delete()


def befriend(db: Session, inviter, invitee, joined: bool) -> bool:
    """Make the two friends and tell the inviter. Returns False when they already were."""
    if inviter.id == invitee.id:
        raise ValueError("That's your own invite link.")
    if are_friends(db, inviter.id, invitee.id):
        return False
    _clear_requests(db, inviter.id, invitee.id)
    create_friendship(db, min(inviter.id, invitee.id), max(inviter.id, invitee.id))
    verb = "joined OmniTrackr from your invite" if joined else "accepted your invite"
    create_notification(db, inviter.id, "friend_invite_accepted", f"{invitee.username} {verb}. You're now friends.")
    return True


def record_signup(db: Session, token, new_user) -> bool:
    """Remember that a new account came from an invite. Never blocks sign-up."""
    inviter = inviter_for(db, token)
    if inviter is None or inviter.id == new_user.id:
        return False
    exists = db.query(models.FriendInviteSignup.id).filter(models.FriendInviteSignup.invitee_id == new_user.id).first()
    if exists:
        return False
    db.add(models.FriendInviteSignup(inviter_id=inviter.id, invitee_id=new_user.id))
    db.commit()
    return True


def complete_signup(db: Session, user) -> Optional[str]:
    """After email verification: befriend the inviter. Returns the inviter's username when it happened."""
    signup = db.query(models.FriendInviteSignup).filter(
        models.FriendInviteSignup.invitee_id == user.id, models.FriendInviteSignup.completed_at.is_(None)).first()
    if signup is None:
        return None
    signup.completed_at = datetime.utcnow()
    db.commit()
    inviter = db.query(models.User).filter(models.User.id == signup.inviter_id).first()
    if inviter is None or not inviter.is_active:
        return None
    befriend(db, inviter, user, joined=True)
    return inviter.username


def friends_brought(db: Session, user_id: int) -> int:
    """How many active members joined OmniTrackr through this member's invite link."""
    return (db.query(models.FriendInviteSignup.id)
            .join(models.User, models.User.id == models.FriendInviteSignup.invitee_id)
            .filter(models.FriendInviteSignup.inviter_id == user_id,
                    models.FriendInviteSignup.completed_at.isnot(None), models.User.is_active.is_(True))
            .count())


def has_friends(db: Session, user_id: int) -> bool:
    return db.query(models.Friendship.id).filter(
        (models.Friendship.user1_id == user_id) | (models.Friendship.user2_id == user_id)).first() is not None
