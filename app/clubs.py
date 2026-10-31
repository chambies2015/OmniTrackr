"""Watch clubs: a shared list picks one title, everyone gets to it by a date, then talks it over.

* Any member of a shared list can start a club pick from a title on the list when
  none is running. Everyone else in the list gets a notification.
* Members say where they are (started or finished, with an optional 1-10 score)
  and post in the pick's discussion. Spoiler posts stay folded for anyone who
  hasn't finished yet.
* Whoever started the pick, or the list's owner, wraps it up. The title is marked
  done on the list and the pick moves to the club's history with its scores.

Rounds copy the title (kind, name, year, art) when they start and never read or
change anyone's library. Only new tables are used.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models
from .shared_lists import KIND_LABELS, ListError, _initials, _member_rows, _notify

MAX_DAYS = 90
POSTS_MAX = 500
HISTORY_SHOWN = 12
STATUSES = ("started", "finished")
DONE_WORD = {"movie": "watched", "tv": "watched", "anime": "watched", "game": "played", "book": "read", "album": "heard",
             "manga": "read", "podcast": "heard", "audiobook": "heard"}


def _now() -> datetime:
    return datetime.utcnow()


def _today() -> date:
    return _now().date()


def current(db: Session, list_id: int) -> Optional[models.ClubRound]:
    return (db.query(models.ClubRound).filter(models.ClubRound.list_id == list_id, models.ClubRound.ended_at.is_(None))
            .order_by(models.ClubRound.id.desc()).first())


def get_round(db: Session, shared: models.SharedList, round_id: int) -> models.ClubRound:
    found = db.query(models.ClubRound).filter_by(id=round_id, list_id=shared.id).first()
    if found is None:
        raise ListError("That club pick isn't here anymore.", 404)
    return found


def _check_ends_on(ends_on: date) -> date:
    today = _today()
    if ends_on <= today:
        raise ListError("Pick a finish-by date after today.")
    if ends_on > today + timedelta(days=MAX_DAYS):
        raise ListError(f"Pick a finish-by date within {MAX_DAYS} days.")
    return ends_on


def _when(day: date) -> str:
    return f"{day:%a} {day:%b} {day.day}"


def start(db: Session, shared: models.SharedList, user, item_id: int, ends_on: date) -> models.ClubRound:
    """Start a club pick from a title on the list. Tells everyone else in the list."""
    # Two members starting a pick at once would otherwise both get one running.
    db.query(models.SharedList.id).filter(models.SharedList.id == shared.id).with_for_update().first()
    if current(db, shared.id) is not None:
        raise ListError("There's already a club pick running. Wrap it up before starting the next one.", 409)
    item = db.query(models.SharedListItem).filter_by(id=item_id, list_id=shared.id).first()
    if item is None:
        raise ListError("That title isn't on this list anymore.", 404)
    ends_on = _check_ends_on(ends_on)
    picked = models.ClubRound(list_id=shared.id, item_id=item.id, started_by_id=user.id, kind=item.kind,
                              title=item.title, year=item.year, slug=item.slug, image=item.image, ends_on=ends_on)
    db.add(picked)
    db.flush()
    # Whoever picks it is in for it.
    db.add(models.ClubProgress(round_id=picked.id, user_id=user.id, status="started"))
    if item.done_at is not None:
        item.done_at, item.done_by_id = None, None
    for member, _ in _member_rows(db, shared.id):
        if member.user_id != user.id:
            _notify(db, member.user_id, "club_pick",
                    f'{user.username} picked {item.title} for "{shared.name}". Finish by {_when(ends_on)}.',
                    f"/lists/{shared.id}")
    shared.updated_at = _now()
    db.commit()
    db.refresh(picked)
    return picked


def _can_run(shared: models.SharedList, picked: models.ClubRound, user) -> bool:
    return user.id in (shared.owner_id, picked.started_by_id)


def change_date(db: Session, shared: models.SharedList, picked: models.ClubRound, user, ends_on: date) -> None:
    if picked.ended_at is not None:
        raise ListError("This club pick is already wrapped up.")
    if not _can_run(shared, picked, user):
        raise ListError("Only whoever started this pick, or the list's owner, can move its date.", 403)
    picked.ends_on = _check_ends_on(ends_on)
    db.commit()


def finish(db: Session, shared: models.SharedList, picked: models.ClubRound, user) -> None:
    """Wrap up the pick: it moves to the club's history and the title is marked done on the list."""
    if picked.ended_at is not None:
        return
    if not _can_run(shared, picked, user):
        raise ListError("Only whoever started this pick, or the list's owner, can wrap it up.", 403)
    picked.ended_at = _now()
    item = db.get(models.SharedListItem, picked.item_id) if picked.item_id else None
    if item is not None and item.list_id == shared.id and item.done_at is None:
        item.done_at, item.done_by_id = _now(), user.id
    shared.updated_at = _now()
    db.commit()


def cancel(db: Session, shared: models.SharedList, picked: models.ClubRound, user) -> None:
    """Drop a pick nobody has talked about yet, e.g. one started by mistake."""
    if not _can_run(shared, picked, user):
        raise ListError("Only whoever started this pick, or the list's owner, can drop it.", 403)
    if picked.ended_at is not None:
        raise ListError("This club pick is already wrapped up.")
    if db.query(models.ClubPost.id).filter_by(round_id=picked.id).first() is not None:
        raise ListError("People have already talked about this pick, so wrap it up instead.")
    db.delete(picked)
    db.commit()


def set_progress(db: Session, picked: models.ClubRound, user, status: Optional[str], score: Optional[int]) -> None:
    if picked.ended_at is not None:
        raise ListError("This club pick is already wrapped up.")
    row = db.query(models.ClubProgress).filter_by(round_id=picked.id, user_id=user.id).first()
    if status is None:
        if row is not None:
            db.delete(row)
        db.commit()
        return
    if status not in STATUSES:
        raise ListError("Say whether you've started or finished.")
    if score is not None and status != "finished":
        raise ListError("Scores are for when you've finished.")
    if row is None:
        row = models.ClubProgress(round_id=picked.id, user_id=user.id, status=status)
        db.add(row)
    row.status, row.score, row.updated_at = status, score, _now()
    db.commit()


def add_post(db: Session, shared: models.SharedList, picked: models.ClubRound, user, body: str, spoiler: bool) -> models.ClubPost:
    body = (body or "").strip()[:1000]
    if not body:
        raise ListError("Write something first.")
    if db.query(models.ClubPost.id).filter_by(round_id=picked.id).count() >= POSTS_MAX:
        raise ListError(f"This discussion has {POSTS_MAX} posts, which is as many as one pick can hold.")
    post = models.ClubPost(round_id=picked.id, user_id=user.id, body=body, spoiler=bool(spoiler))
    db.add(post)
    link = f"/lists/{shared.id}"
    for member, _ in _member_rows(db, shared.id):
        if member.user_id == user.id:
            continue
        # One note per member until they open the list again, however many posts go in meanwhile.
        waiting = db.query(models.Notification.id).filter(
            models.Notification.user_id == member.user_id, models.Notification.type == "club_post",
            models.Notification.link == link, models.Notification.read_at.is_(None)).first()
        if waiting is None:
            _notify(db, member.user_id, "club_post", f'{user.username} posted about {picked.title} in "{shared.name}".', link)
    shared.updated_at = _now()
    db.commit()
    db.refresh(post)
    return post


def delete_post(db: Session, shared: models.SharedList, picked: models.ClubRound, user, post_id: int) -> None:
    post = db.query(models.ClubPost).filter_by(id=post_id, round_id=picked.id).first()
    if post is None:
        raise ListError("That post isn't here anymore.", 404)
    if post.user_id != user.id and shared.owner_id != user.id:
        raise ListError("Only whoever wrote a post, or the list's owner, can delete it.", 403)
    db.delete(post)
    db.commit()


REMIND_DAYS_BEFORE = 2


def send_due_reminders(db: Session, today: Optional[date] = None) -> int:
    """Nudge members who haven't finished a club pick that's due within two days. Once per member per pick.

    Picks started less than two days ago are skipped: everyone just heard about them.
    Returns how many members were nudged.
    """
    today = today or _today()
    started_before = datetime.combine(today, datetime.min.time()) - timedelta(days=REMIND_DAYS_BEFORE)
    rounds = (db.query(models.ClubRound, models.SharedList)
              .join(models.SharedList, models.SharedList.id == models.ClubRound.list_id)
              .filter(models.ClubRound.ended_at.is_(None), models.ClubRound.ends_on > today,
                      models.ClubRound.ends_on <= today + timedelta(days=REMIND_DAYS_BEFORE),
                      models.ClubRound.started_at <= started_before)
              .all())
    nudged = 0
    for picked, shared in rounds:
        finished = {user_id for user_id, in db.query(models.ClubProgress.user_id).filter(
            models.ClubProgress.round_id == picked.id, models.ClubProgress.status == "finished")}
        reminded = {user_id for user_id, in db.query(models.ClubReminder.user_id).filter(
            models.ClubReminder.round_id == picked.id)}
        verb = DONE_WORD.get(picked.kind, "finished")
        for member, _ in _member_rows(db, shared.id):
            if member.user_id in finished or member.user_id in reminded:
                continue
            try:
                db.add(models.ClubReminder(round_id=picked.id, user_id=member.user_id))
                _notify(db, member.user_id, "club_due_soon",
                        f'Finish by {_when(picked.ends_on)}: {picked.title}, the club pick in "{shared.name}". '
                        f"Mark it {verb} when you're done.",
                        f"/lists/{shared.id}")
                db.commit()
            except Exception:
                # Another worker nudged this member first (unique constraint).
                db.rollback()
                continue
            nudged += 1
    return nudged


def forget_member(db: Session, list_id: int, user_id: int) -> None:
    """Someone left the list: their progress goes with them, their posts stay. Does not commit."""
    round_ids = [round_id for round_id, in db.query(models.ClubRound.id).filter_by(list_id=list_id)]
    if round_ids:
        db.query(models.ClubProgress).filter(models.ClubProgress.user_id == user_id,
                                             models.ClubProgress.round_id.in_(round_ids)).delete(synchronize_session=False)


def item_removed(db: Session, item: models.SharedListItem) -> None:
    """A list title went away; a pick made from it keeps its copied title. Does not commit."""
    db.query(models.ClubRound).filter(models.ClubRound.item_id == item.id).update(
        {"item_id": None}, synchronize_session=False)


def _person(user, viewer) -> Optional[dict]:
    if user is None or not user.is_active:
        return None
    return {"id": user.id, "username": user.username, "initials": _initials(user.username), "you": user.id == viewer.id}


def _average(scores: list[int]) -> Optional[float]:
    return round(sum(scores) / len(scores), 1) if scores else None


def _title(picked: models.ClubRound) -> dict:
    return {"kind": picked.kind, "label": KIND_LABELS.get(picked.kind, "Title"), "title": picked.title,
            "year": picked.year, "image": picked.image,
            "url": f"/titles/{picked.kind}/{picked.slug}" if picked.slug else None,
            "done_word": DONE_WORD.get(picked.kind, "finished")}


def _round_detail(db: Session, shared: models.SharedList, picked: models.ClubRound, rows, viewer, seen) -> dict:
    inside = {user.id: user for _, user in rows}
    progress = {row.user_id: row for row in db.query(models.ClubProgress).filter_by(round_id=picked.id)}
    mine = progress.get(viewer.id)
    finished = mine is not None and mine.status == "finished"
    posts = (db.query(models.ClubPost, models.User).join(models.User, models.User.id == models.ClubPost.user_id)
             .filter(models.ClubPost.round_id == picked.id, models.User.is_active.is_(True))
             .order_by(models.ClubPost.created_at, models.ClubPost.id).all())
    is_owner = shared.owner_id == viewer.id
    people = []
    for user_id, user in inside.items():
        row = progress.get(user_id)
        people.append(dict(_person(user, viewer), status=row.status if row else None,
                           score=row.score if row else None))
    order = {"finished": 0, "started": 1, None: 2}
    people.sort(key=lambda person: (order[person["status"]], person["username"].casefold()))
    scores = [row.score for user_id, row in progress.items() if user_id in inside and row.score is not None]
    starter = db.get(models.User, picked.started_by_id) if picked.started_by_id else None
    today = _today()
    return dict(_title(picked), **{
        "id": picked.id, "ends_on": picked.ends_on.isoformat(), "ends_label": _when(picked.ends_on), "days_left": (picked.ends_on - today).days,
        "started_at": picked.started_at.isoformat() + "Z",
        "started_by": _person(starter, viewer),
        "can_run": _can_run(shared, picked, viewer),
        "members": people,
        "finished_count": sum(1 for person in people if person["status"] == "finished"),
        "average": _average(scores), "score_count": len(scores),
        "me": {"status": mine.status if mine else None, "score": mine.score if mine else None},
        "posts": [{
            "id": post.id, "body": post.body, "spoiler": post.spoiler,
            # Spoilers come folded for anyone who hasn't finished yet.
            "folded": post.spoiler and not finished and post.user_id != viewer.id,
            "author": _person(user, viewer), "at": post.created_at.isoformat() + "Z",
            "new": bool(seen and post.created_at > seen and post.user_id != viewer.id),
            "can_delete": is_owner or post.user_id == viewer.id,
        } for post, user in posts],
    })


def detail(db: Session, shared: models.SharedList, member: models.SharedListMember, viewer) -> dict:
    """The club part of the list page: the running pick, if any, and the ones before it.

    Read before the list page marks things seen, so new posts still say so.
    """
    rows = _member_rows(db, shared.id)
    running = current(db, shared.id)
    history = (db.query(models.ClubRound).filter(models.ClubRound.list_id == shared.id, models.ClubRound.ended_at.isnot(None))
               .order_by(models.ClubRound.ended_at.desc(), models.ClubRound.id.desc()).limit(HISTORY_SHOWN).all())
    inside = {user.id for _, user in rows}
    past = []
    if history:
        ids = [picked.id for picked in history]
        scores: dict[int, list[int]] = {}
        finished: dict[int, int] = {}
        mine: dict[int, Optional[int]] = {}
        for round_id, user_id, status, score in db.query(
                models.ClubProgress.round_id, models.ClubProgress.user_id, models.ClubProgress.status,
                models.ClubProgress.score).filter(models.ClubProgress.round_id.in_(ids)):
            if user_id == viewer.id:
                mine[round_id] = score
            if user_id not in inside:
                continue
            if status == "finished":
                finished[round_id] = finished.get(round_id, 0) + 1
            if score is not None:
                scores.setdefault(round_id, []).append(score)
        counts = dict(db.query(models.ClubPost.round_id, func.count(models.ClubPost.id))
                      .filter(models.ClubPost.round_id.in_(ids)).group_by(models.ClubPost.round_id).all())
        for picked in history:
            past.append(dict(_title(picked), **{
                "id": picked.id, "ended_at": picked.ended_at.isoformat() + "Z",
                "finished_count": finished.get(picked.id, 0), "average": _average(scores.get(picked.id, [])),
                "my_score": mine.get(picked.id), "post_count": counts.get(picked.id, 0),
            }))
    return {
        "current": _round_detail(db, shared, running, rows, viewer, member.seen_at) if running else None,
        "past": past, "max_days": MAX_DAYS,
    }


def past_posts(db: Session, shared: models.SharedList, picked: models.ClubRound, viewer) -> list[dict]:
    """A wrapped-up pick's discussion. Nothing is folded anymore, but spoiler posts keep their label."""
    posts = (db.query(models.ClubPost, models.User).join(models.User, models.User.id == models.ClubPost.user_id)
             .filter(models.ClubPost.round_id == picked.id, models.User.is_active.is_(True))
             .order_by(models.ClubPost.created_at, models.ClubPost.id).all())
    return [{"id": post.id, "body": post.body, "spoiler": post.spoiler, "folded": False,
             "author": _person(user, viewer), "at": post.created_at.isoformat() + "Z", "new": False,
             "can_delete": shared.owner_id == viewer.id or post.user_id == viewer.id} for post, user in posts]


def summary(db: Session, list_id: int) -> Optional[dict]:
    """A line for list cards and join links: what the club is on right now."""
    running = current(db, list_id)
    if running is None:
        return None
    return {"title": running.title, "label": KIND_LABELS.get(running.kind, "Title"), "image": running.image,
            "ends_on": running.ends_on.isoformat(), "ends_label": _when(running.ends_on),
            "days_left": (running.ends_on - _today()).days}
