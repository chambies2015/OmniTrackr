"""What gets members talking: the /discussions hub, openers for an empty board, and the
"talk about it" links on finish screens and reviews (Nov 2026).

With a few dozen active members a title board is usually empty, and an empty box with
"Start a discussion" rarely gets used. This module gives people something to answer
instead: openers written for each kind of title, the threads already going on titles
in their own library, and titles they just finished that nobody has talked about yet.

Nothing here writes to a library. Reading a member's library only happens for that
member's own page ("On your shelf", "You finished"), and site-wide lists only use
threads, which are public already, and the trending chart, which has its own floors.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import models, title_discussions as boards, title_pages

LATEST_LIMIT = 12
SHELF_LIMIT = 8
YOURS_LIMIT = 8
WAITING_LIMIT = 6
SHELF_SCAN = 400  # Most recent library entries per kind looked at for "On your shelf".
FINISHED_SCAN = 40

# Openers per kind of title. {title} is filled in; a member edits either part before posting.
# Each body is a first sentence to finish, long enough (20+ characters) to pass the post check
# once they add their own words, and never a statement on their behalf.
SCREEN = (
    ("That ending of {title}: did it work for you?", "I'm still thinking about how {title} ended. For me it "),
    ("Who's your favourite character in {title}?", "My favourite character in {title} is "),
    ("The scene from {title} I can't stop thinking about", "There's one scene in {title} I keep coming back to: "),
    ("Is {title} worth it for someone new?", "If a friend asked me whether to start {title}, I'd tell them "),
    ("What should I watch after {title}?", "I just finished {title} and want something with the same feel. "),
)
EPISODIC = (
    ("Best episode of {title}?", "If I had to pick one episode of {title} to show someone, it would be "),
    ("Did {title} get better or worse as it went on?", "The way {title} changed over its run: "),
) + SCREEN[1:3] + (
    ("Is {title} worth it for someone new?", "If a friend asked me whether to start {title}, I'd tell them "),
)
GAME = (
    ("How long did {title} take you?", "I finished {title} in about "),
    ("Tips for someone starting {title}", "One thing I wish I'd known before starting {title}: "),
    ("The moment in {title} that hooked you", "The moment {title} really clicked for me was "),
    ("Is {title} worth finishing?", "I'm partway through {title} and wondering if it's worth seeing through. "),
    ("Games like {title}?", "I loved {title} and want something with the same feel. "),
)
READ = (
    ("That ending of {title}: did it work for you?", "I'm still thinking about how {title} ended. For me it "),
    ("Favourite character in {title}?", "The character I'd follow anywhere from {title} is "),
    ("A line from {title} that stuck with you", "There's a line in {title} I keep coming back to: "),
    ("Is {title} worth it for someone new?", "If a friend asked me whether to start {title}, I'd tell them "),
    ("What to read after {title}?", "I just finished {title} and want something with the same feel. "),
)
LISTEN = (
    ("Favourite track on {title}?", "The track from {title} I keep replaying is "),
    ("Where should someone start with {title}?", "If someone's new to {title}, I'd start them with "),
    ("Did {title} grow on you?", "My first listen of {title} versus now: "),
    ("Anything else that sounds like {title}?", "I love {title} and want more like it. "),
)
SPOKEN = (
    ("Best episode of {title}?", "If I had to pick one episode of {title} to send a friend, it would be "),
    ("Where should someone start with {title}?", "If someone's new to {title}, I'd tell them to start with "),
    ("Did {title} hold up all the way through?", "The way {title} changed as it went on: "),
    ("Anything else like {title}?", "I love {title} and want more like it. "),
)
AUDIOBOOK = (
    ("How was the narration of {title}?", "The narration of {title} for me was "),
) + READ[:2] + (READ[3], READ[4])
OPENERS = {"movie": SCREEN, "tv": EPISODIC, "anime": EPISODIC, "game": GAME, "book": READ, "manga": READ,
           "album": LISTEN, "podcast": SPOKEN, "audiobook": AUDIOBOOK}


def openers(kind: str, title: str) -> list[dict]:
    """[{"subject", "body"}] for this kind, with the title filled in and kept within the subject limit."""
    name = " ".join((title or "").split()) or "this"
    found = []
    for subject, body in OPENERS.get(kind, SCREEN):
        text = subject.format(title=name)
        if len(text) > boards.SUBJECT_MAX:
            text = subject.format(title="it")
        found.append({"subject": text, "body": body.format(title=name)})
    return found


def opener(kind: str, title: str, index: Optional[int]) -> Optional[dict]:
    choices = openers(kind, title)
    if index is None or not 0 <= index < len(choices):
        return None
    return choices[index]


# ---------------------------------------------------------------- reading

def _slug(path: str) -> str:
    return path.rsplit("/", 1)[1]


def _listed(query):
    """Threads a list may show: not deleted, or deleted with replies still worth reading."""
    return query.filter(or_(models.TitleDiscussion.deleted_at.is_(None), models.TitleDiscussion.reply_count > 0))


def latest(db: Session, limit: int = LATEST_LIMIT, exclude=()) -> list:
    """The most recently active threads anywhere on the site."""
    rows = (_listed(boards._visible_threads(db))
            .order_by(models.TitleDiscussion.last_activity_at.desc(), models.TitleDiscussion.id.desc())
            .limit(limit + len(exclude)).all())
    skip = set(exclude)
    return [row for row in rows if row.id not in skip][:limit]


def total_threads(db: Session) -> int:
    return _listed(boards._visible_threads(db)).count()


def shelf_slugs(db: Session, user_id: int, scan: int = SHELF_SCAN) -> dict[str, set]:
    """{kind: {title slug}} for the member's own library, newest entries first. Their own data, for their own page."""
    found: dict[str, set] = {}
    for kind, (model, _, _, _, _) in title_pages.KINDS.items():
        year = title_pages._year_column(kind, model)
        rows = (db.query(model.title, year).filter(model.user_id == user_id)
                .order_by(model.id.desc()).limit(scan).all())
        slugs = {title_pages.title_slug(title or "", title_pages._row_year(kind, value))
                 for title, value in rows if (title or "").strip()}
        if slugs:
            found[kind] = slugs
    return found


def on_shelf(db: Session, user_id: int, limit: int = SHELF_LIMIT, exclude=()) -> list:
    """Threads about titles in the member's library, by latest activity."""
    shelf = shelf_slugs(db, user_id)
    if not shelf:
        return []
    clauses = []
    for kind, slugs in shelf.items():
        ordered = sorted(slugs)
        for start in range(0, len(ordered), 400):
            clauses.append((models.TitleDiscussion.kind == kind) & models.TitleDiscussion.slug.in_(ordered[start:start + 400]))
    query = _listed(boards._visible_threads(db)).filter(or_(*clauses))
    if exclude:
        query = query.filter(~models.TitleDiscussion.id.in_(list(exclude)))
    return (query.order_by(models.TitleDiscussion.last_activity_at.desc(), models.TitleDiscussion.id.desc())
            .limit(limit).all())


@dataclass
class Joined:
    thread: models.TitleDiscussion
    new_replies: int  # Replies from other people since the member last posted there.


def yours(db: Session, user_id: int, limit: int = YOURS_LIMIT) -> list[Joined]:
    """Threads the member started or replied in, newest activity first, with what's new since they last posted."""
    reply = models.TitleDiscussionReply
    joined = {tid for tid, in db.query(reply.discussion_id).filter(reply.user_id == user_id).distinct()}
    query = _listed(boards._visible_threads(db)).filter(or_(
        models.TitleDiscussion.user_id == user_id, models.TitleDiscussion.id.in_(joined or {0})))
    threads = (query.order_by(models.TitleDiscussion.last_activity_at.desc(), models.TitleDiscussion.id.desc())
               .limit(limit).all())
    if not threads:
        return []
    ids = [thread.id for thread in threads]
    last_own: dict[int, datetime] = {}
    for tid, at in db.query(reply.discussion_id, reply.created_at).filter(
            reply.discussion_id.in_(ids), reply.user_id == user_id):
        if tid not in last_own or at > last_own[tid]:
            last_own[tid] = at
    others: dict[int, list] = {}
    for tid, at in db.query(reply.discussion_id, reply.created_at).filter(
            reply.discussion_id.in_(ids), reply.user_id != user_id, reply.hidden_at.is_(None)):
        others.setdefault(tid, []).append(at)
    found = []
    for thread in threads:
        posted = [at for at in (last_own.get(thread.id), thread.created_at if thread.user_id == user_id else None) if at]
        since = max(posted) if posted else thread.created_at
        found.append(Joined(thread, sum(1 for at in others.get(thread.id, ()) if at > since)))
    return found


def _boards_with_threads(db: Session, pairs: set) -> set:
    """Which (kind, slug) pairs already have a listed thread."""
    if not pairs:
        return set()
    by_kind: dict[str, list] = {}
    for kind, slug in pairs:
        by_kind.setdefault(kind, []).append(slug)
    taken = set()
    for kind, slugs in by_kind.items():
        for kind_, slug in _listed(boards._visible_threads(db)).filter(
                models.TitleDiscussion.kind == kind, models.TitleDiscussion.slug.in_(slugs)).with_entities(
                models.TitleDiscussion.kind, models.TitleDiscussion.slug):
            taken.add((kind_, slug))
    return taken


@dataclass
class Waiting:
    kind: str
    title: str
    url: str          # the title page
    image: Optional[str]
    reason: str       # why it's here, in a few words
    opener: dict      # the suggested first post

    @property
    def board(self) -> str:
        return boards.board_path(self.kind, _slug(self.url))


def _finished_titles(db: Session, user_id: int) -> list[tuple[Optional[datetime], str, object]]:
    found = []
    for kind, (model, _, _, _, _) in title_pages.KINDS.items():
        done = getattr(model, title_pages.COMPLETE_FIELD[kind])
        for item in (db.query(model).filter(model.user_id == user_id, done == True)
                     .order_by(model.id.desc()).limit(FINISHED_SCAN)):
            if (item.title or "").strip():
                found.append((getattr(item, "added_at", None) or datetime.min, kind, item))
    found.sort(key=lambda row: (row[0], row[2].id), reverse=True)
    return found


def _trending_entries(db: Session) -> list[dict]:
    try:
        from . import trending
        month = trending.data(db, "month")
        return list(month.get("overall") or [])
    except Exception:
        return []


def waiting(db: Session, user=None, limit: int = WAITING_LIMIT) -> list[Waiting]:
    """Titles with no discussion yet: the member's own finished titles first, then what members are into this month."""
    candidates: list[tuple[str, str, Optional[str], str]] = []  # kind, title page path, image, reason
    seen = set()
    titles = {}
    if user is not None:
        finished = _finished_titles(db, user.id)
        by_kind: dict[str, list] = {}
        for _, kind, item in finished:
            by_kind.setdefault(kind, []).append(item)
        for kind, items in by_kind.items():
            slugs = [_slug(title_pages.path_for_item(kind, item)) for item in items]
            existing = title_pages.paths_many(db, kind, slugs)
            for item, slug in zip(items, slugs):
                path = existing.get(slug)
                if path and (kind, path) not in seen:
                    seen.add((kind, path))
                    titles[(kind, path)] = item.title.strip()
                    image = title_pages._safe_image(getattr(item, title_pages.IMAGE_FIELD[kind], None))
                    candidates.append((kind, path, image, "You finished it"))
    for entry in _trending_entries(db):
        kind, path = entry.get("kind"), entry.get("url")
        if kind in title_pages.KINDS and path and (kind, path) not in seen:
            seen.add((kind, path))
            titles[(kind, path)] = entry.get("title") or ""
            members = int(entry.get("members") or 0)
            reason = f"{members} members are into it this month" if members >= 2 else "Members are into it this month"
            candidates.append((kind, path, entry.get("image"), reason))
    taken = _boards_with_threads(db, {(kind, _slug(path)) for kind, path, _, _ in candidates})
    found = []
    for kind, path, image, reason in candidates:
        if (kind, _slug(path)) in taken:
            continue
        title = titles[(kind, path)]
        pick = openers(kind, title)
        index = len(found) % len(pick)
        found.append(Waiting(kind, title, path, image, reason, {**pick[index], "index": index}))
        if len(found) >= limit:
            break
    return found


# ---------------------------------------------------------------- the finish screen

def talk_for_item(db: Session, kind: str, item) -> Optional[dict]:
    """{"url", "count"} for the board of a library entry's title, if that board can open (the title page exists)."""
    try:
        slug = _slug(title_pages.path_for_item(kind, item))
        path = title_pages.paths_many(db, kind, [slug]).get(slug)
        if not path:
            existing = boards.board_count(db, kind, slug)
            if not existing:
                return None
            return {"url": boards.board_path(kind, slug), "count": existing}
        board_slug = _slug(path)
        return {"url": boards.board_path(kind, board_slug), "count": boards.board_count(db, kind, board_slug)}
    except Exception:
        return None
