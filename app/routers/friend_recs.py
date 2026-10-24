"""Recommend to a friend: send a title (with a short note) to a friend's inbox, or share a link.

* ``POST /api/friend-recs`` sends a title from the member's library (or a title page) to friends.
* ``POST /api/friend-recs/link`` makes a share link (``/r/<token>``) for someone not on OmniTrackr.
  The page names the sender, shows the note and signs the visitor up through the sender's
  invite link, so they become friends; once signed in, the title lands in their inbox.
* The inbox lists what friends sent; each one is added to the library (optionally Next Up)
  or dismissed with one tap. Nothing enters a library without that tap.

Recommendations copy only public facts about a title, never the sender's rating, review or notes.
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta
from html import escape
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import funnel, models, title_pages
from ..auth import AUTH_COOKIE_NAME
from ..crud.friends import are_friends
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..for_you import CREATOR_FIELD, LABELS, LIBRARY
from ..integer_bounds import PositiveDatabaseId
from ..progress import lock_progress_owner
from ..site_chrome import apply_site_chrome, message_page
from .next_up import enqueue

router = APIRouter(tags=["friend-recs"])
SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
PAGE_CSS_VERSION = "20261024-friend-recs-1"
PAGE_JS_VERSION = "20261024-friend-recs-1"
NOTE_MAX = 280
MAX_FRIENDS_PER_SEND = 20
DAILY_SEND_LIMIT = 100
DAILY_LINK_LIMIT = 30
LINK_DAYS = 60
INBOX_LIMIT = 30
INBOX_LINK = "/#friend-recs"
COMPLETE_FIELD = {"movies": "watched", "tv-shows": "watched", "anime": "watched",
                  "video-games": "played", "music": "listened", "books": "read"}
VERB = {"movies": "watch", "tv-shows": "watch", "anime": "watch", "video-games": "play", "music": "hear", "books": "read"}


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _clean_note(value: Optional[str]) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    return value or None


class RecSource(BaseModel):
    """Either an item in the sender's own library, or a public title page."""
    category: Optional[str] = Field(None, max_length=20)
    item_id: Optional[PositiveDatabaseId] = None
    kind: Optional[str] = Field(None, max_length=10)
    slug: Optional[str] = Field(None, max_length=130)
    note: Optional[str] = Field(None, max_length=NOTE_MAX * 2)

    @field_validator("note")
    @classmethod
    def _note(cls, value):
        value = _clean_note(value)
        if value and len(value) > NOTE_MAX:
            raise ValueError(f"Keep the note under {NOTE_MAX} characters")
        return value


class RecSend(RecSource):
    friend_ids: list[PositiveDatabaseId] = Field(..., min_length=1, max_length=MAX_FRIENDS_PER_SEND)


class RecAdd(BaseModel):
    next_up: bool = False


def _details(category: str, item) -> dict:
    details = {}
    for field in LIBRARY[category][1]:
        value = getattr(item, field, None)
        if field in ("poster_url", "cover_art_url", "rawg_link"):
            value = title_pages._safe_image(value)
        elif isinstance(value, datetime):
            value = value.isoformat()
        if value is not None and value != "":
            details[field] = value
    details["title"] = (item.title or "").strip()
    return details


def _resolve(db: Session, user, body: RecSource) -> dict:
    """The title being recommended, as public facts only."""
    if body.category is not None or body.item_id is not None:
        if body.category not in LIBRARY or body.item_id is None:
            raise HTTPException(400, "Choose a title from your library")
        model = LIBRARY[body.category][0]
        item = db.query(model).filter(model.id == body.item_id, model.user_id == user.id).first()
        if item is None or not (item.title or "").strip():
            raise HTTPException(404, "That title isn't in your library")
        category = body.category
        kind = title_pages.LIBRARY_TO_KIND[category]
        path = title_pages.path_for_item(kind, item)
        group = title_pages.find(db, kind, path.rsplit("/", 1)[1])
        path = group.path if group is not None else None
    elif body.kind in title_pages.KINDS and body.slug:
        group = title_pages.find(db, body.kind, body.slug)
        if group is None:
            raise HTTPException(404, "Title not found")
        kind, category, path = body.kind, title_pages.KINDS[body.kind][2], group.path
        fields = LIBRARY[category][1]
        item = max(group.items, key=lambda entry: sum(bool(getattr(entry, f, None)) for f in fields))
    else:
        raise HTTPException(400, "Choose a title to recommend")
    details = _details(category, item)
    if group is not None and path:
        details["title"] = group.title
    image = details.get(title_pages.IMAGE_FIELD[kind])
    return {"category": category, "title": details["title"][:300], "details": details,
            "image": image, "title_path": path}


def _sent_today(db: Session, user_id: int, links: bool) -> int:
    query = db.query(func.count(models.FriendRecommendation.id)).filter(
        models.FriendRecommendation.sender_id == user_id,
        models.FriendRecommendation.source_id.is_(None),
        models.FriendRecommendation.created_at > datetime.utcnow() - timedelta(days=1),
    )
    recipient = models.FriendRecommendation.recipient_id
    query = query.filter(recipient.is_(None) if links else recipient.isnot(None))
    return int(query.scalar() or 0)


def _same_title(column, title: str):
    return func.lower(func.trim(column)) == title.strip().lower()


@router.post("/api/friend-recs")
def send_recommendation(body: RecSend, request: Request, response: Response,
                        user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Send a title to one or more friends' inboxes."""
    _private(response)
    rec = _resolve(db, user, body)
    friend_ids = [fid for fid in dict.fromkeys(body.friend_ids) if fid != user.id]
    friends = [fid for fid in friend_ids if are_friends(db, user.id, fid)]
    if not friends:
        raise HTTPException(403, "You can only recommend titles to your friends")
    if _sent_today(db, user.id, links=False) + len(friends) > DAILY_SEND_LIMIT:
        raise HTTPException(429, "That's a lot of recommendations for one day. Try again tomorrow.")
    now = datetime.utcnow()
    sent, already = [], []
    names = {u.id: u.username for u in db.query(models.User).filter(models.User.id.in_(friends))}
    for friend_id in friends:
        existing = db.query(models.FriendRecommendation).filter(
            models.FriendRecommendation.sender_id == user.id,
            models.FriendRecommendation.recipient_id == friend_id,
            models.FriendRecommendation.category == rec["category"],
            models.FriendRecommendation.status == "pending",
            _same_title(models.FriendRecommendation.title, rec["title"]),
        ).first()
        if existing is not None:
            # Sending again only refreshes the note; the friend isn't pinged twice.
            if body.note:
                existing.note = body.note
            already.append(names.get(friend_id))
            continue
        db.add(models.FriendRecommendation(
            sender_id=user.id, recipient_id=friend_id, category=rec["category"], title=rec["title"],
            details=json.dumps(rec["details"]), image=rec["image"], title_path=rec["title_path"],
            note=body.note, created_at=now,
        ))
        db.add(models.Notification(
            user_id=friend_id, type="friend_recommendation", link=INBOX_LINK,
            message=f"{user.username} thinks you'd love {rec['title']}." + (f" “{_short(body.note)}”" if body.note else ""),
        ))
        sent.append(names.get(friend_id))
    db.commit()
    if sent:
        funnel.record("friend_rec_sent", request)
    return {"sent": len(sent), "already": len(already), "friends": [n for n in sent + already if n], "title": rec["title"]}


def _short(note: str, limit: int = 90) -> str:
    return note if len(note) <= limit else note[:limit].rsplit(" ", 1)[0] + "…"


@router.post("/api/friend-recs/link")
def share_link(body: RecSource, request: Request, response: Response,
               user=Depends(get_current_user), db: Session = Depends(get_db)):
    """A link that recommends the title to anyone, and invites them to join as a friend."""
    _private(response)
    rec = _resolve(db, user, body)
    now = datetime.utcnow()
    link = db.query(models.FriendRecommendation).filter(
        models.FriendRecommendation.sender_id == user.id,
        models.FriendRecommendation.recipient_id.is_(None),
        models.FriendRecommendation.token.isnot(None),
        models.FriendRecommendation.category == rec["category"],
        _same_title(models.FriendRecommendation.title, rec["title"]),
        models.FriendRecommendation.expires_at > now + timedelta(days=7),
    ).order_by(models.FriendRecommendation.id.desc()).first()
    if link is not None and (link.note or None) != body.note:
        link = None
    if link is None:
        if _sent_today(db, user.id, links=True) >= DAILY_LINK_LIMIT:
            raise HTTPException(429, "You've made a lot of links today. Try again tomorrow.")
        link = models.FriendRecommendation(
            sender_id=user.id, token=secrets.token_urlsafe(18), category=rec["category"], title=rec["title"],
            details=json.dumps(rec["details"]), image=rec["image"], title_path=rec["title_path"],
            note=body.note, created_at=now, expires_at=now + timedelta(days=LINK_DAYS),
        )
        db.add(link)
        db.commit()
    from .. import friend_invites
    friend_invites.link_for(db, user)  # The page signs visitors up as the sender's friend.
    verb = VERB[rec["category"]]
    text = f"I think you'd love {rec['title']}." + (f" {body.note}" if body.note else f" You have to {verb} it.")
    return {"url": f"{SITE_URL}/r/{link.token}", "title": f"{rec['title']} on OmniTrackr", "text": text,
            "expires_at": link.expires_at.isoformat()}


def _in_library(db: Session, user_id: int, entries) -> set[int]:
    """Ids of the entries whose title the member already tracks."""
    found = set()
    by_category: dict[str, list] = {}
    for entry in entries:
        by_category.setdefault(entry.category, []).append(entry)
    for category, group in by_category.items():
        if category not in LIBRARY:
            continue
        model = LIBRARY[category][0]
        wanted = {entry.title.strip().lower() for entry in group}
        owned = {row[0] for row in db.query(func.lower(func.trim(model.title))).filter(
            model.user_id == user_id, func.lower(func.trim(model.title)).in_(wanted))}
        found.update(entry.id for entry in group if entry.title.strip().lower() in owned)
    return found


def _serialize(entry: models.FriendRecommendation, sender, owned: set[int]) -> dict:
    try:
        details = json.loads(entry.details or "{}")
    except ValueError:
        details = {}
    kind = title_pages.LIBRARY_TO_KIND.get(entry.category)
    year = details.get("year")
    if not year and details.get("release_date"):
        year = str(details["release_date"])[:4]
    return {
        "id": entry.id,
        "sender": sender.username,
        "category": entry.category,
        "category_label": LABELS.get(entry.category, ""),
        "kind": kind,
        "title": entry.title,
        "year": int(year) if str(year or "").isdigit() else None,
        "creator": details.get(CREATOR_FIELD.get(entry.category, ""), None) or None,
        "image": title_pages._safe_image(entry.image),
        "note": entry.note,
        "title_path": entry.title_path,
        "in_library": entry.id in owned,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


def _pending(db: Session, user_id: int):
    return db.query(models.FriendRecommendation, models.User).join(
        models.User, models.User.id == models.FriendRecommendation.sender_id,
    ).filter(
        models.FriendRecommendation.recipient_id == user_id,
        models.FriendRecommendation.status == "pending",
        models.User.is_active.is_(True),
    )


@router.get("/api/friend-recs/inbox")
def inbox(response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Titles friends recommended that are still waiting for a yes or no, newest first."""
    _private(response)
    query = _pending(db, user.id)
    total = query.count()
    rows = query.order_by(models.FriendRecommendation.created_at.desc(),
                          models.FriendRecommendation.id.desc()).limit(INBOX_LIMIT).all()
    owned = _in_library(db, user.id, [entry for entry, _ in rows])
    return {"count": total, "items": [_serialize(entry, sender, owned) for entry, sender in rows]}


def _own_pending(db: Session, user_id: int, rec_id: int) -> models.FriendRecommendation:
    entry = db.query(models.FriendRecommendation).filter(
        models.FriendRecommendation.id == rec_id,
        models.FriendRecommendation.recipient_id == user_id,
    ).with_for_update().first()
    if entry is None:
        raise HTTPException(404, "Recommendation not found")
    if entry.status != "pending":
        raise HTTPException(409, "You've already answered that recommendation")
    return entry


def _new_item(user_id: int, category: str, details: dict):
    model, fields = LIBRARY[category]
    payload = {field: details.get(field) for field in fields if details.get(field) not in (None, "")}
    payload["title"] = details.get("title") or ""
    if "release_date" in payload:
        try:
            payload["release_date"] = datetime.fromisoformat(str(payload["release_date"]))
        except ValueError:
            payload.pop("release_date")
    for field in ("year", "seasons", "episodes"):
        if field in payload and not isinstance(payload[field], int):
            payload.pop(field)
    if category == "movies":
        payload.setdefault("director", "")
    payload[COMPLETE_FIELD[category]] = False
    return model(user_id=user_id, review_public=False, **payload)


@router.post("/api/friend-recs/{rec_id}/add")
def add_recommendation(rec_id: PositiveDatabaseId, request: Request, response: Response, body: RecAdd | None = None,
                       user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Put a recommended title in the library (and Next Up when asked). Tells the friend who sent it."""
    _private(response)
    lock_progress_owner(db, user.id)
    entry = _own_pending(db, user.id, rec_id)
    if entry.category not in LIBRARY:
        raise HTTPException(400, "This kind of title can't be added")
    model = LIBRARY[entry.category][0]
    item = db.query(model).filter(model.user_id == user.id, _same_title(model.title, entry.title)).first()
    created = item is None
    if created:
        try:
            details = json.loads(entry.details or "{}")
        except ValueError:
            details = {}
        details["title"] = entry.title
        item = _new_item(user.id, entry.category, details)
        db.add(item)
        db.flush()
    queued = False
    if body and body.next_up and not getattr(item, COMPLETE_FIELD[entry.category], False):
        queued = enqueue(db, user.id, entry.category, item.id)
    in_queue = queued or bool(body and body.next_up and db.query(models.NextUpItem.id).filter(
        models.NextUpItem.user_id == user.id, models.NextUpItem.category == entry.category,
        models.NextUpItem.item_id == item.id).first())
    entry.status = "queued" if in_queue else "added"
    entry.item_id = item.id
    entry.acted_at = datetime.utcnow()
    sender = db.get(models.User, entry.sender_id)
    if sender is not None and sender.is_active and are_friends(db, user.id, sender.id):
        if in_queue:
            message = f"{user.username} added {entry.title} to their Next Up from your recommendation."
        elif created:
            message = f"{user.username} added {entry.title} to their library from your recommendation."
        else:
            message = f"{user.username} already had {entry.title} in their library. Thanks for the pick!"
        db.add(models.Notification(user_id=sender.id, type="friend_recommendation_added", message=message))
    result = {"status": entry.status, "item_id": item.id, "category": entry.category,
              "created": created, "queued": queued, "title": entry.title}
    db.commit()
    funnel.record("friend_rec_added", request)
    return result


@router.post("/api/friend-recs/{rec_id}/dismiss")
def dismiss_recommendation(rec_id: PositiveDatabaseId, response: Response,
                           user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Not for me: take it out of the inbox. The sender isn't told."""
    _private(response)
    entry = _own_pending(db, user.id, rec_id)
    entry.status = "dismissed"
    entry.acted_at = datetime.utcnow()
    db.commit()
    return {"status": "dismissed"}


def _live_link(db: Session, token: str):
    """A share link that hasn't expired, with its (active) sender, or (None, None)."""
    if not token or len(token) > 48 or not all(c.isalnum() or c in "-_" for c in token):
        return None, None
    link = db.query(models.FriendRecommendation).filter(
        models.FriendRecommendation.token == token,
        models.FriendRecommendation.recipient_id.is_(None),
    ).first()
    if link is None or link.expires_at is None or link.expires_at <= datetime.utcnow():
        return None, None
    sender = db.get(models.User, link.sender_id)
    if sender is None or not sender.is_active:
        return None, None
    return link, sender


@router.post("/api/friend-recs/claim/{token}")
def claim_link(token: str, request: Request, response: Response,
               user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Put a shared recommendation into the signed-in member's inbox (once)."""
    _private(response)
    link, sender = _live_link(db, token)
    if link is None:
        raise HTTPException(404, "This recommendation link has expired")
    if sender.id == user.id:
        return {"claimed": False, "own": True, "sender": sender.username, "title": link.title}
    existing = db.query(models.FriendRecommendation).filter(
        models.FriendRecommendation.source_id == link.id,
        models.FriendRecommendation.recipient_id == user.id,
    ).first()
    if existing is not None:
        return {"claimed": False, "own": False, "sender": sender.username, "title": link.title, "id": existing.id}
    copy = models.FriendRecommendation(
        sender_id=sender.id, recipient_id=user.id, source_id=link.id, category=link.category, title=link.title,
        details=link.details, image=link.image, title_path=link.title_path, note=link.note,
    )
    db.add(copy)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # A second tab claimed it at the same moment.
        return {"claimed": False, "own": False, "sender": sender.username, "title": link.title}
    funnel.record("friend_rec_claimed", request)
    return {"claimed": True, "own": False, "sender": sender.username, "title": link.title, "id": copy.id}


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True).replace("{", "&#123;").replace("}", "&#125;")


def render_link_page(link: models.FriendRecommendation, sender, invite_token: Optional[str], signed_in: bool) -> str:
    try:
        details = json.loads(link.details or "{}")
    except ValueError:
        details = {}
    name, title = sender.username, link.title
    label = LABELS.get(link.category, "Title")
    year = details.get("year") or (str(details.get("release_date") or "")[:4] or None)
    creator = details.get(CREATOR_FIELD.get(link.category, ""))
    meta = " · ".join(str(part) for part in (label, year, creator) if part)
    image = title_pages._safe_image(link.image)
    cover = (f'<img class="rec-card__cover" src="{_e(image)}" alt="{_e(title)} cover" width="200" height="300" referrerpolicy="no-referrer">'
             if image else f'<div class="rec-card__cover rec-card__cover--empty" aria-hidden="true">{_e(title[:1].upper())}</div>')
    note = (f'<blockquote class="rec-card__note"><p>{_e(link.note)}</p><footer>{_e(name)}</footer></blockquote>'
            if link.note else "")
    details_link = (f'<a class="site-btn site-btn--ghost" href="{_e(link.title_path)}">Read reviews and details</a>'
                    if link.title_path else "")
    here = f"/r/{link.token}"
    if signed_in:
        friend = (f'<a class="site-btn site-btn--ghost" href="/join/{_e(invite_token)}">Add {_e(name)} as a friend</a>'
                  if invite_token else "")
        actions = (f'<button type="button" class="site-btn site-btn--primary" data-friend-rec-claim data-token="{_e(link.token)}">'
                   'Save it to my recommendations</button>' + friend + details_link)
        pitch = ""
    else:
        join = f"/?invite={quote(invite_token)}#signup" if invite_token else "/#signup"
        actions = (f'<a class="site-btn site-btn--primary" href="{_e(join)}">Join free and save it</a>'
                   f'<a class="site-btn site-btn--ghost" href="/?next={_e(quote(here, safe=""))}#login">I already have an account</a>'
                   + details_link)
        pitch = (
            '<section class="rec-pitch" aria-labelledby="rec-pitch-title">'
            f'<h2 id="rec-pitch-title">What is OmniTrackr?</h2>'
            '<p>A free tracker for the movies, shows, anime, games, music and books you love, all in one library. '
            f'Join through this link and you and {_e(name)} become friends, so {_e(title)} is waiting in your inbox, '
            'and you can trade picks, compare your taste with a Taste Match and see what each other is into.</p>'
            '<ul><li>Free to use, no credit card</li><li>Rate, review and plan what to try next</li>'
            '<li>Import from Letterboxd, Goodreads, MyAnimeList and more</li></ul></section>'
        )
    og_image = f'<meta property="og:image" content="{_e(image)}">' if image else ""
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="robots" content="noindex, nofollow">
  <title>{_e(name)} recommends {_e(title)} - OmniTrackr</title>
  <meta name="description" content="{_e(name)} thinks you'd love {_e(title)}. See why on OmniTrackr.">
  <meta property="og:title" content="{_e(name)} thinks you'd love {_e(title)}">
  <meta property="og:description" content="{_e(link.note or f'A {label.lower()} recommendation from {name} on OmniTrackr.')}">
  <meta property="og:type" content="website">
  {og_image}
  <meta name="twitter:card" content="summary">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">
  <link rel="stylesheet" href="/static/friend-recs.css?v={PAGE_CSS_VERSION}">
  <script src="/static/friend-rec-page.js?v={PAGE_JS_VERSION}" defer></script>
</head>
<body class="site rec-page" data-rec-token="{_e(link.token)}" data-signed-in="{'1' if signed_in else '0'}">
  <!--SITE_NAV:-->
  <main class="site-wrap rec-page__main">
    <article class="rec-card">
      {cover}
      <div class="rec-card__copy">
        <p class="site-eyebrow">A recommendation from {_e(name)}</p>
        <h1>{_e(name)} thinks you'd love <span class="rec-card__title">{_e(title)}</span></h1>
        {f'<p class="rec-card__meta">{_e(meta)}</p>' if meta else ''}
        {note}
        <div class="rec-card__actions">{actions}</div>
        <p class="rec-card__status" data-friend-rec-status role="status" aria-live="polite"></p>
      </div>
    </article>
    {pitch}
  </main>
  <!--SITE_FOOTER-->
</body>
</html>"""
    return apply_site_chrome(page)


@router.get("/r/{token}", include_in_schema=False)
def link_page(token: str, request: Request, db: Session = Depends(get_db)):
    link, sender = _live_link(db, token)
    if link is None:
        page = message_page("Recommendation expired", "This recommendation has expired",
                            "Ask your friend to send it again, or start your own free library now.",
                            actions=(("Start tracking for free", "/#signup"), ("Browse popular titles", "/titles")))
        response = strict_html_response(page, status_code=404)
    else:
        signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
        invite = db.query(models.FriendInvite).filter(models.FriendInvite.user_id == sender.id).first()
        response = strict_html_response(render_link_page(link, sender, invite.token if invite else None, signed_in))
        if not signed_in:
            funnel.record("friend_rec_link_opened", request)
    _private(response)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Vary"] = "Cookie"
    return response
