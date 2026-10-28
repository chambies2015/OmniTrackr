"""Discussion boards on public title pages (Oct 2026).

Every title page gets a board at /titles/<kind>/<slug>/discussions where members
start threads and reply. Reviews stay one verdict per member; a board is for the
conversation around a title: theories, questions, favourite scenes, "is it worth
finishing?".

Abuse controls, all per member (signed-in, verified accounts only):
  * posting limits per day, tighter for accounts younger than a day, and a short
    gap between any two posts;
  * no more than two links in a post, and no repeating the same text within a day;
  * three reports from different members hide a post until a moderator looks; two
    "unmarked spoilers" reports fold it behind a spoiler warning instead.
Moderators are the usernames in admin_access (environment variables, never the
database). They can hide, restore, lock and mark spoilers.

Text is stored as typed and always escaped on output. ``||like this||`` marks an
inline spoiler; nothing else is formatted, and links are not made clickable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from . import models
from .admin_access import is_moderator, moderator_usernames
from .review_quality import AD_MIN_REVIEW_WORDS, word_count

SUBJECT_MIN, SUBJECT_MAX = 6, 120
THREAD_BODY_MIN, THREAD_BODY_MAX = 20, 5000
REPLY_BODY_MIN, REPLY_BODY_MAX = 2, 3000
THREADS_PER_DAY = 5
REPLIES_PER_DAY = 60
NEW_ACCOUNT_HOURS = 24
NEW_ACCOUNT_THREADS = 2
NEW_ACCOUNT_REPLIES = 15
POST_GAP_SECONDS = 20
MAX_LINKS = 2
MAX_REPLIES = 500
REPORT_HIDE_THRESHOLD = 3
SPOILER_REPORT_THRESHOLD = 2
BOARD_PAGE_SIZE = 25
REPORT_REASONS = {
    "spam": "Spam or advertising",
    "harassment": "Harassment or hate",
    "spoilers": "Unmarked spoilers",
    "off_topic": "Not about this title",
    "other": "Something else",
}
LINK = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)
INLINE_SPOILER = re.compile(r"\|\|(.+?)\|\|")


class DiscussionError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _now() -> datetime:
    return datetime.utcnow()


def board_path(kind: str, slug: str) -> str:
    return f"/titles/{kind}/{slug}/discussions"


def thread_path(thread: models.TitleDiscussion) -> str:
    return f"{board_path(thread.kind, thread.slug)}/{thread.id}"


def _clean(text: str) -> str:
    """Trim, normalise line endings and squeeze runs of blank lines."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text)


def _check_text(db: Session, user, body: str, low: int, high: int) -> str:
    body = _clean(body)
    if len(body) < low:
        raise DiscussionError(422, "Write a little more first." if low > 2 else "Write a few words first.")
    if len(body) > high:
        raise DiscussionError(422, f"Keep it under {high:,} characters.")
    if len(LINK.findall(body)) > MAX_LINKS:
        raise DiscussionError(422, f"Posts can include up to {MAX_LINKS} links.")
    since = _now() - timedelta(days=1)
    repeat = (db.query(models.TitleDiscussion.id).filter(models.TitleDiscussion.user_id == user.id,
                                                         models.TitleDiscussion.created_at >= since,
                                                         models.TitleDiscussion.body == body).first()
              or db.query(models.TitleDiscussionReply.id).filter(models.TitleDiscussionReply.user_id == user.id,
                                                                 models.TitleDiscussionReply.created_at >= since,
                                                                 models.TitleDiscussionReply.body == body).first())
    if repeat:
        raise DiscussionError(409, "You already posted that. Say something new, or edit what you wrote.")
    return body


def _check_pace(db: Session, user, threads: bool) -> None:
    """Per-member posting limits. IP limits in main.py sit on top of these."""
    now = _now()
    last_thread = db.query(func.max(models.TitleDiscussion.created_at)).filter(
        models.TitleDiscussion.user_id == user.id).scalar()
    last_reply = db.query(func.max(models.TitleDiscussionReply.created_at)).filter(
        models.TitleDiscussionReply.user_id == user.id).scalar()
    last = max(filter(None, (last_thread, last_reply)), default=None)
    if last and (now - last).total_seconds() < POST_GAP_SECONDS:
        raise DiscussionError(429, "You're posting quickly. Give it a few seconds and try again.")
    created = getattr(user, "created_at", None)
    young = created is not None and now - created < timedelta(hours=NEW_ACCOUNT_HOURS)
    since = now - timedelta(days=1)
    if threads:
        cap = NEW_ACCOUNT_THREADS if young else THREADS_PER_DAY
        count = db.query(func.count(models.TitleDiscussion.id)).filter(
            models.TitleDiscussion.user_id == user.id, models.TitleDiscussion.created_at >= since).scalar()
        if count >= cap:
            raise DiscussionError(429, f"You can start {cap} discussions a day. Reply to one that's already going, "
                                       "or come back tomorrow.")
    else:
        cap = NEW_ACCOUNT_REPLIES if young else REPLIES_PER_DAY
        count = db.query(func.count(models.TitleDiscussionReply.id)).filter(
            models.TitleDiscussionReply.user_id == user.id, models.TitleDiscussionReply.created_at >= since).scalar()
        if count >= cap:
            raise DiscussionError(429, f"That's {cap} replies today, the daily limit. Come back tomorrow.")


# ---------------------------------------------------------------- reading

def _visible_threads(db: Session):
    active = db.query(models.User.id).filter(models.User.is_active == True)
    return db.query(models.TitleDiscussion).filter(models.TitleDiscussion.hidden_at.is_(None),
                                                   models.TitleDiscussion.user_id.in_(active))


def board_threads(db: Session, kind: str, slug: str, limit: int = BOARD_PAGE_SIZE, offset: int = 0) -> list:
    query = (_visible_threads(db).filter(models.TitleDiscussion.kind == kind, models.TitleDiscussion.slug == slug)
             .filter(or_(models.TitleDiscussion.deleted_at.is_(None), models.TitleDiscussion.reply_count > 0)))
    return (query.order_by(models.TitleDiscussion.last_activity_at.desc(), models.TitleDiscussion.id.desc())
            .offset(offset).limit(limit).all())


def board_count(db: Session, kind: str, slug: str) -> int:
    return (_visible_threads(db).filter(models.TitleDiscussion.kind == kind, models.TitleDiscussion.slug == slug)
            .filter(or_(models.TitleDiscussion.deleted_at.is_(None), models.TitleDiscussion.reply_count > 0)).count())


def get_thread(db: Session, thread_id: int, viewer=None, kind: Optional[str] = None,
               slug: Optional[str] = None) -> models.TitleDiscussion:
    """The thread, if this viewer may read it. Hidden threads are kept for their author and moderators."""
    thread = db.get(models.TitleDiscussion, thread_id)
    if thread is None or (kind is not None and thread.kind != kind) or (slug is not None and thread.slug != slug):
        raise DiscussionError(404, "Discussion not found")
    author = db.get(models.User, thread.user_id)
    staff = viewer is not None and (is_moderator(viewer) or viewer.id == thread.user_id)
    if author is None or not author.is_active or (thread.hidden_at and not staff):
        raise DiscussionError(404, "Discussion not found")
    if thread.deleted_at and not thread.reply_count and not staff:
        raise DiscussionError(404, "Discussion not found")
    return thread


def visible_replies(db: Session, thread: models.TitleDiscussion, viewer=None) -> list:
    active = db.query(models.User.id).filter(models.User.is_active == True)
    rows = (db.query(models.TitleDiscussionReply).filter(models.TitleDiscussionReply.discussion_id == thread.id,
                                                          models.TitleDiscussionReply.user_id.in_(active))
            .order_by(models.TitleDiscussionReply.created_at, models.TitleDiscussionReply.id).all())
    moderator = viewer is not None and is_moderator(viewer)
    return [row for row in rows if not row.hidden_at or moderator or (viewer is not None and viewer.id == row.user_id)]


def thread_words(thread: models.TitleDiscussion, replies: list) -> int:
    words = 0 if thread.deleted_at or thread.hidden_at else word_count(thread.subject) + word_count(thread.body)
    return words + sum(word_count(reply.body) for reply in replies if not reply.hidden_at)


def is_indexable(thread: models.TitleDiscussion, replies: list) -> bool:
    """Search engines see a thread once it carries as much member writing as an indexed review."""
    return not thread.hidden_at and not thread.deleted_at and thread_words(thread, replies) >= AD_MIN_REVIEW_WORDS


def sitemap_paths(db: Session, limit: int = 300) -> list[tuple[str, datetime]]:
    threads = (_visible_threads(db).filter(models.TitleDiscussion.deleted_at.is_(None))
               .order_by(models.TitleDiscussion.last_activity_at.desc()).limit(limit * 3).all())
    paths = []
    for thread in threads:
        replies = [r for r in thread.replies if not r.hidden_at]
        if is_indexable(thread, replies):
            paths.append((thread_path(thread), thread.last_activity_at))
        if len(paths) >= limit:
            break
    return paths


def summary_for_page(db: Session, kind: str, slug: str, limit: int = 4) -> dict:
    """The latest few threads and the total, for the section on the title page."""
    return {"threads": board_threads(db, kind, slug, limit=limit), "count": board_count(db, kind, slug)}


# ---------------------------------------------------------------- writing

def start(db: Session, user, group, subject: str, body: str, spoiler: bool) -> models.TitleDiscussion:
    subject = " ".join((subject or "").split())
    if len(subject) < SUBJECT_MIN:
        raise DiscussionError(422, "Give your discussion a title of a few words.")
    if len(subject) > SUBJECT_MAX:
        raise DiscussionError(422, f"Keep the title under {SUBJECT_MAX} characters.")
    if len(LINK.findall(subject)):
        raise DiscussionError(422, "Leave links out of the title.")
    _check_pace(db, user, threads=True)
    body = _check_text(db, user, body, THREAD_BODY_MIN, THREAD_BODY_MAX)
    now = _now()
    thread = models.TitleDiscussion(kind=group.kind, slug=group.path.rsplit("/", 1)[1], title=group.title[:200],
                                    user_id=user.id, subject=subject, body=body, spoiler=bool(spoiler),
                                    created_at=now, last_activity_at=now)
    db.add(thread)
    db.commit()
    return thread


def reply(db: Session, user, thread: models.TitleDiscussion, body: str, spoiler: bool) -> models.TitleDiscussionReply:
    if thread.hidden_at or thread.deleted_at:
        raise DiscussionError(409, "This discussion is closed to new replies.")
    if thread.locked_at:
        raise DiscussionError(409, "A moderator locked this discussion, so it can't take new replies.")
    if thread.reply_count >= MAX_REPLIES:
        raise DiscussionError(409, "This discussion is full. Start a new one to keep talking.")
    _check_pace(db, user, threads=False)
    body = _check_text(db, user, body, REPLY_BODY_MIN, REPLY_BODY_MAX)
    now = _now()
    post = models.TitleDiscussionReply(discussion_id=thread.id, user_id=user.id, body=body, spoiler=bool(spoiler),
                                       created_at=now)
    db.add(post)
    thread.reply_count = (thread.reply_count or 0) + 1
    thread.last_activity_at = now
    db.flush()
    _notify_reply(db, user, thread, post)
    db.commit()
    return post


def _notify_reply(db: Session, author, thread: models.TitleDiscussion, post: models.TitleDiscussionReply) -> None:
    """Tell the thread's starter and earlier repliers. One unread note per thread per person."""
    link = thread_path(thread)
    earlier = {uid for uid, in db.query(models.TitleDiscussionReply.user_id).filter(
        models.TitleDiscussionReply.discussion_id == thread.id, models.TitleDiscussionReply.id != post.id).distinct()}
    people = ({thread.user_id} | earlier) - {author.id}
    if not people:
        return
    waiting = {uid for uid, in db.query(models.Notification.user_id).filter(
        models.Notification.user_id.in_(people), models.Notification.type == "discussion_reply",
        models.Notification.link == link, models.Notification.read_at.is_(None))}
    active = {uid for uid, in db.query(models.User.id).filter(models.User.id.in_(people), models.User.is_active == True)}
    subject = thread.subject if len(thread.subject) <= 60 else thread.subject[:57].rstrip() + "…"
    for uid in sorted((people & active) - waiting):
        whose = "your discussion" if uid == thread.user_id else "a discussion you joined"
        db.add(models.Notification(user_id=uid, type="discussion_reply", link=link,
                                   message=f'{author.username} replied to {whose} "{subject}" on {thread.title}.'))


def _owned_reply(db: Session, thread, reply_id: int) -> models.TitleDiscussionReply:
    post = db.get(models.TitleDiscussionReply, reply_id)
    if post is None or post.discussion_id != thread.id:
        raise DiscussionError(404, "Reply not found")
    return post


def delete_thread(db: Session, user, thread: models.TitleDiscussion) -> str:
    """Authors (and moderators) remove a thread. With replies, the thread stays so the replies make sense."""
    if thread.user_id != user.id and not is_moderator(user):
        raise DiscussionError(403, "Only the person who started this discussion can delete it.")
    if thread.reply_count:
        thread.deleted_at = thread.deleted_at or _now()
        db.commit()
        return "cleared"
    _drop_reports(db, "thread", [thread.id])
    db.delete(thread)
    db.commit()
    return "deleted"


def delete_reply(db: Session, user, thread: models.TitleDiscussion, reply_id: int) -> None:
    post = _owned_reply(db, thread, reply_id)
    if post.user_id != user.id and not is_moderator(user):
        raise DiscussionError(403, "You can only delete your own replies.")
    _drop_reports(db, "reply", [post.id])
    db.delete(post)
    thread.reply_count = max(0, (thread.reply_count or 1) - 1)
    db.commit()


def edit(db: Session, user, thread: models.TitleDiscussion, reply_id: Optional[int], body: str, spoiler: Optional[bool]):
    """Authors fix typos. Editing does not lift a hide: a moderator still has to look."""
    if reply_id is None:
        if thread.user_id != user.id or thread.deleted_at:
            raise DiscussionError(403, "You can only edit your own posts.")
        target, low, high = thread, THREAD_BODY_MIN, THREAD_BODY_MAX
    else:
        target = _owned_reply(db, thread, reply_id)
        if target.user_id != user.id:
            raise DiscussionError(403, "You can only edit your own posts.")
        low, high = REPLY_BODY_MIN, REPLY_BODY_MAX
    cleaned = _clean(body)
    if cleaned != target.body:
        target.body = _check_text(db, user, cleaned, low, high)
    if spoiler is not None:
        target.spoiler = bool(spoiler) or target.spoiler and _spoiler_reports(db, target) >= SPOILER_REPORT_THRESHOLD
    target.edited_at = _now()
    db.commit()
    return target


# ---------------------------------------------------------------- reports and moderation

def _drop_reports(db: Session, target: str, ids: list) -> None:
    if ids:
        db.query(models.TitleDiscussionReport).filter(models.TitleDiscussionReport.target == target,
                                                     models.TitleDiscussionReport.target_id.in_(ids)).delete(
            synchronize_session=False)


def _target_name(post) -> str:
    return "thread" if isinstance(post, models.TitleDiscussion) else "reply"


def _spoiler_reports(db: Session, post) -> int:
    return db.query(func.count(models.TitleDiscussionReport.id)).filter(
        models.TitleDiscussionReport.target == _target_name(post), models.TitleDiscussionReport.target_id == post.id,
        models.TitleDiscussionReport.reason == "spoilers", models.TitleDiscussionReport.resolved_at.is_(None)).scalar()


def report(db: Session, user, thread: models.TitleDiscussion, reply_id: Optional[int], reason: str) -> dict:
    if reason not in REPORT_REASONS:
        raise DiscussionError(422, "Pick a reason for the report.")
    post = thread if reply_id is None else _owned_reply(db, thread, reply_id)
    if post.user_id == user.id:
        raise DiscussionError(409, "That's your own post. You can edit or delete it instead.")
    target = _target_name(post)
    exists = db.query(models.TitleDiscussionReport.id).filter_by(target=target, target_id=post.id, user_id=user.id).first()
    if exists:
        return {"reported": True, "duplicate": True, "hidden": bool(post.hidden_at)}
    db.add(models.TitleDiscussionReport(target=target, target_id=post.id, user_id=user.id, reason=reason))
    db.flush()
    open_reports = db.query(models.TitleDiscussionReport).filter(
        models.TitleDiscussionReport.target == target, models.TitleDiscussionReport.target_id == post.id,
        models.TitleDiscussionReport.resolved_at.is_(None)).all()
    spoilers = sum(1 for row in open_reports if row.reason == "spoilers")
    serious = len(open_reports) - spoilers
    if spoilers >= SPOILER_REPORT_THRESHOLD and not post.spoiler:
        post.spoiler = True
    if serious >= REPORT_HIDE_THRESHOLD and not post.hidden_at:
        post.hidden_at = _now()
        _notify_moderators(db, thread, f'A post in "{thread.subject}" on {thread.title} was hidden after '
                                       f'{serious} reports. Have a look and restore or remove it.')
    elif len(open_reports) == 1:
        _notify_moderators(db, thread, f'Someone reported a post in "{thread.subject}" on {thread.title}.')
    db.commit()
    return {"reported": True, "duplicate": False, "hidden": bool(post.hidden_at)}


def _notify_moderators(db: Session, thread, message: str) -> None:
    names = moderator_usernames()
    if not names:
        return
    for (uid,) in db.query(models.User.id).filter(models.User.username.in_(names), models.User.is_active == True):
        db.add(models.Notification(user_id=uid, type="discussion_report", link="/discussions/moderation", message=message))


MOD_ACTIONS = ("hide", "restore", "lock", "unlock", "spoiler", "unspoiler")


def moderate(db: Session, user, thread: models.TitleDiscussion, reply_id: Optional[int], action: str) -> dict:
    if not is_moderator(user):
        raise DiscussionError(403, "Only moderators can do that.")
    if action not in MOD_ACTIONS:
        raise DiscussionError(422, "Unknown action")
    post = thread if reply_id is None else _owned_reply(db, thread, reply_id)
    now = _now()
    if action in ("lock", "unlock"):
        if post is not thread:
            raise DiscussionError(422, "Lock the discussion, not a reply.")
        thread.locked_at = now if action == "lock" else None
    elif action == "hide":
        post.hidden_at = post.hidden_at or now
    elif action == "restore":
        post.hidden_at = None
    else:
        post.spoiler = action == "spoiler"
    if action in ("hide", "restore", "spoiler", "unspoiler"):
        db.query(models.TitleDiscussionReport).filter(
            models.TitleDiscussionReport.target == _target_name(post), models.TitleDiscussionReport.target_id == post.id,
            models.TitleDiscussionReport.resolved_at.is_(None)).update({"resolved_at": now}, synchronize_session=False)
    db.commit()
    return {"hidden": bool(post.hidden_at), "spoiler": bool(post.spoiler), "locked": bool(thread.locked_at)}


def moderation_queue(db: Session, limit: int = 100) -> list[dict]:
    """Posts with open reports or a hide on them, newest report first."""
    rows = (db.query(models.TitleDiscussionReport).filter(models.TitleDiscussionReport.resolved_at.is_(None))
            .order_by(models.TitleDiscussionReport.created_at.desc()).limit(1000).all())
    grouped: dict = {}
    for row in rows:
        grouped.setdefault((row.target, row.target_id), []).append(row)
    hidden_threads = db.query(models.TitleDiscussion).filter(models.TitleDiscussion.hidden_at.isnot(None)).limit(limit).all()
    hidden_replies = db.query(models.TitleDiscussionReply).filter(models.TitleDiscussionReply.hidden_at.isnot(None)).limit(limit).all()
    for thread in hidden_threads:
        grouped.setdefault(("thread", thread.id), [])
    for post in hidden_replies:
        grouped.setdefault(("reply", post.id), [])
    queue = []
    for (target, target_id), reports in grouped.items():
        post = db.get(models.TitleDiscussion if target == "thread" else models.TitleDiscussionReply, target_id)
        if post is None:
            continue
        thread = post if target == "thread" else db.get(models.TitleDiscussion, post.discussion_id)
        author = db.get(models.User, post.user_id)
        queue.append({
            "target": target, "id": post.id, "thread": thread, "body": post.body, "spoiler": post.spoiler,
            "hidden": bool(post.hidden_at), "author": author.username if author else "?",
            "reasons": sorted({REPORT_REASONS.get(r.reason, r.reason) for r in reports}),
            "reports": len(reports),
            "latest": max((r.created_at for r in reports), default=post.hidden_at or post.created_at),
        })
    queue.sort(key=lambda entry: entry["latest"], reverse=True)
    return queue[:limit]


# ---------------------------------------------------------------- rendering helpers

def body_html(text: str) -> str:
    """Escaped paragraphs; ||text|| becomes an inline spoiler the reader taps to show."""
    parts = []
    for paragraph in re.split(r"\n\s*\n", text or ""):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        safe = escape(paragraph, quote=True)
        safe = INLINE_SPOILER.sub(
            lambda m: f'<span class="disc-spoiler" tabindex="0" role="button" aria-pressed="false" '
                      f'title="Spoiler: select to show">{m.group(1)}</span>', safe)
        parts.append("<p>" + safe.replace("\n", "<br>") + "</p>")
    return "".join(parts)


def plain_excerpt(text: str, limit: int = 180) -> str:
    """For listings and meta descriptions: inline spoilers are blanked out, never shown."""
    text = INLINE_SPOILER.sub("[spoiler]", " ".join((text or "").split()))
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def ago(moment: Optional[datetime], now: Optional[datetime] = None) -> str:
    if moment is None:
        return ""
    seconds = max(0, int(((now or _now()) - moment).total_seconds()))
    if seconds < 60:
        return "just now"
    for size, unit in ((86400 * 365, "year"), (86400 * 30, "month"), (86400 * 7, "week"), (86400, "day"),
                       (3600, "hour"), (60, "minute")):
        if seconds >= size:
            count = seconds // size
            return f"{count} {unit}{'s' if count != 1 else ''} ago"
    return "just now"


@dataclass
class Author:
    username: str
    profile_url: Optional[str]
    supporter: Optional[dict]


def authors(db: Session, user_ids) -> dict[int, Author]:
    from .public_profiles import enabled_profile_paths
    from .supporters import public_badges
    ids = {int(uid) for uid in user_ids if uid}
    if not ids:
        return {}
    users = {u.id: u for u in db.query(models.User).filter(models.User.id.in_(ids)).all()}
    profiles = enabled_profile_paths(db, ids)
    badges = public_badges(db, ids)
    return {uid: Author(user.username, profiles.get(uid), badges.get(uid)) for uid, user in users.items()}
