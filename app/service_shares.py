"""Share links for "On your services" (Nov 2026): /on-my-services/<token>.

A member who has picked their streaming services can turn on one link that shows the films, shows
and anime on their list (not finished yet) that stream on those services right now, newest
arrivals first. The page reads the list when it is opened, so it follows the member's list and
the services as they change. It only uses shelves that aren't hidden or private, and it never
shows scores, notes or anything else from the library. The services the member picked show
only as the names next to those titles. The link stops working when the member turns it off,
clears their services, has fewer than three titles left on them, or closes the account. Pages
are never indexed.

Whoever opens the link can tick the services they have and see which of the titles they could
watch too, then save any of them: a visitor to the list kept in their browser (which moves into
a new account), a member straight into their library.

Two images go with every link, drawn with the Rankings share-card helpers: a 1200x630 card that
chat apps show and a 1080x1920 picture for stories.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models, ranking_shares, streaming_services, title_pages

BASE_PATH = "/on-my-services"
TOKEN = re.compile(r"[A-Za-z0-9_-]{16,32}")
MIN_TITLES = 3
PAGE_LIMIT = 30   # titles on the page
PICTURE_SHOWN = 6  # posters on each picture

KIND_WORDS = {"movies": ("film", "films"), "tv-shows": ("show", "shows"), "anime": ("anime", "anime")}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def valid_token(token) -> bool:
    return isinstance(token, str) and TOKEN.fullmatch(token) is not None


def path_for(share: models.ServiceShare) -> str:
    return f"{BASE_PATH}/{share.token}"


def by_token(db: Session, token) -> Optional[models.ServiceShare]:
    if not valid_token(token):
        return None
    return db.query(models.ServiceShare).filter(models.ServiceShare.token == token).first()


def mine(db: Session, user_id: int) -> Optional[models.ServiceShare]:
    return db.query(models.ServiceShare).filter(models.ServiceShare.user_id == user_id).first()


# ---------------------------------------------------------------- what the link shows

def _categories(user: models.User) -> list[str]:
    """Film, TV and anime shelves that are shown in the library and not kept private."""
    return [category for category in streaming_services.CATEGORIES if ranking_shares._shareable(user, category)]


def items_for(db: Session, user: models.User, now: Optional[datetime] = None) -> tuple[list[dict], dict]:
    """(titles, {service id: when picked}): unfinished titles on shareable shelves streaming on the member's services."""
    now = now or _now()
    picked = streaming_services.chosen(streaming_services.get_choice(db, user.id))
    categories = _categories(user)
    if not picked or not categories:
        return [], picked
    entries = streaming_services.entries_for(db, user.id, categories=categories)
    # Every service each title streams on, not only the member's, so a visitor can match their own.
    live = streaming_services._sightings(db, {entry.key for entry in entries})
    items, seen = [], set()
    for entry in entries:
        rows = live.get(entry.key) or []
        theirs = [row for row in rows if row.service in picked]
        if not theirs or entry.key in seen:
            continue
        seen.add(entry.key)
        newest = max((row.first_seen_at for row in theirs if streaming_services._is_new(row, now)), default=None)
        path = title_pages.title_path(entry.kind, entry.title, entry.year)
        image = title_pages._safe_image(entry.poster)
        items.append({
            "category": entry.category,
            "kind": entry.kind,
            "title": entry.title[:200],
            "year": entry.year,
            "label": streaming_services.CATEGORY_LABELS[entry.category],
            "image": image if image and image.startswith("https://") else None,
            "url": path,
            "slug": path.rsplit("/", 1)[-1],
            "services": [{"id": row.service, "name": streaming_services.NAMES[row.service],
                          "new": streaming_services._is_new(row, now)} for row in theirs],
            "all": [row.service for row in rows],
            "new": newest is not None,
            "_order": (0 if newest else 1, -(newest.timestamp() if newest else 0),
                       -(entry.added_at.timestamp() if entry.added_at else 0), -entry.id),
        })
    items.sort(key=lambda item: item["_order"])
    for item in items:
        item.pop("_order")
    return items, picked


def _count(db: Session, user: models.User, picked: dict, categories: list[str]) -> int:
    """How many titles items_for() would list, without building them.

    The home card asks on every refresh, so this reads only the matching keys: items_for() loads every
    sighting on every service and works out each title's link, which doubled the card's time on a big list.
    """
    if not picked or not categories:
        return 0
    keys = sorted({entry.key for entry in streaming_services.entries_for(db, user.id, categories=categories)})
    found = set()
    for chunk in streaming_services._chunks(keys):
        found.update(key for key, in db.query(models.ServiceSighting.title_key).filter(
            models.ServiceSighting.title_key.in_(chunk), models.ServiceSighting.gone_at.is_(None),
            models.ServiceSighting.service.in_(sorted(picked))).distinct())
    return len(found)


def state(db: Session, user: models.User, now: Optional[datetime] = None) -> dict:
    """What the home card shows about the link."""
    share = mine(db, user.id)
    picked = streaming_services.chosen(streaming_services.get_choice(db, user.id))
    categories = _categories(user)
    count = _count(db, user, picked, categories)
    if not picked:
        reason = "services"
    elif count < MIN_TITLES:
        reason = "few"
    else:
        reason = None
    return {
        "path": path_for(share) if share else None,
        "opened": int(share.opened or 0) if share else 0,
        "allowed": reason is None,
        "reason": reason,
        "count": count,
        "story": f"{path_for(share)}/story.png" if share else None,
        # Formats the link leaves out because the shelf is private or hidden; the card still lists them.
        "left_out": [category for category in streaming_services.CATEGORIES if category not in categories],
    }


def turn_on(db: Session, user: models.User) -> models.ServiceShare:
    """The member's link, made if there isn't one. LookupError when there's nothing to share yet."""
    items, picked = items_for(db, user)
    if not picked:
        raise LookupError("Pick your streaming services first.")
    if len(items) < MIN_TITLES:
        raise LookupError("A link needs at least three titles from your list on your services. "
                          "Films, shows and anime on private shelves don't count.")
    share = mine(db, user.id)
    if share is not None:
        return share
    token = secrets.token_urlsafe(12)
    for _ in range(5):
        if by_token(db, token) is None:
            break
        token = secrets.token_urlsafe(12)
    share = models.ServiceShare(user_id=user.id, token=token, opened=0, created_at=_now())
    db.add(share)
    try:
        db.commit()
    except IntegrityError:  # another tab made it a moment ago
        db.rollback()
        share = mine(db, user.id)
        if share is None:
            raise
        return share
    streaming_services.count("link_on")
    return share


def turn_off(db: Session, user: models.User) -> bool:
    share = mine(db, user.id)
    if share is None:
        return False
    db.delete(share)
    db.commit()
    streaming_services.count("link_off")
    return True


def count_open(db: Session, share: models.ServiceShare) -> None:
    try:
        db.query(models.ServiceShare).filter(models.ServiceShare.id == share.id).update(
            {models.ServiceShare.opened: models.ServiceShare.opened + 1}, synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()


def view(db: Session, share: models.ServiceShare, now: Optional[datetime] = None) -> Optional[dict]:
    """What the page and the pictures show, or None when the link no longer shows anything."""
    owner = db.get(models.User, share.user_id)
    if owner is None or not owner.is_active:
        return None
    items, picked = items_for(db, owner, now)
    if len(items) < MIN_TITLES:
        return None
    counts: dict[str, int] = {}
    for item in items:
        for service in item["services"]:
            counts[service["id"]] = counts.get(service["id"], 0) + 1
    # Only services with something on them show; a service picked with nothing on it stays unsaid.
    services = [{"id": service, "name": streaming_services.NAMES[service], "count": counts[service]}
                for service in picked if counts.get(service)]
    kinds = [category for category in streaming_services.CATEGORIES if any(item["category"] == category for item in items)]
    credit = ranking_shares._credit(db, owner)
    result = {
        "owner_id": owner.id,
        "token": share.token,
        "path": path_for(share),
        "items": items[:PAGE_LIMIT],
        "total": len(items),
        "new": sum(1 for item in items if item["new"]),
        "services": services,
        "kinds": kinds,
        "by": credit[0] if credit else None,
        "profile": credit[1] if credit else None,
        "opened": int(share.opened or 0),
    }
    result["fingerprint"] = fingerprint(result)
    return result


def fingerprint(data: dict) -> str:
    # Everything the pictures draw: the services line and the formats line too, not only the first posters.
    parts = [str(data["total"]), str(data["new"]), data.get("by") or "",
             ",".join(service["id"] for service in data["services"]), ",".join(data["kinds"])]
    parts += [f'{item["title"]}|{item.get("year") or ""}|{item.get("image") or ""}|'
              + ",".join(f'{service["id"]}{"*" if service["new"] else ""}' for service in item["services"])
              for item in data["items"][:PICTURE_SHOWN]]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def _and(parts: list[str]) -> str:
    return streaming_services._and(parts)


def service_names(data: dict, most: int = 3) -> str:
    """"Netflix, Hulu and Max", or "Netflix, Hulu and 3 more" past ``most``."""
    names = [service["name"] for service in data["services"]]
    if len(names) > most:
        return f'{", ".join(names[:most - 1])} and {len(names) - most + 1} more'
    return _and(names)


def kind_words(data: dict) -> str:
    """"films, shows and anime" for the formats on the list."""
    words = [KIND_WORDS[category][1] for category in data["kinds"]]
    return _and(words) if words else "titles"


def heading(data: dict) -> str:
    """"nova's watchlist, streaming now", or "My watchlist, streaming now" without a public profile to name."""
    if data.get("by"):
        return f'{data["by"]}\'s watchlist, streaming now'
    return "My watchlist, streaming now"


def summary(data: dict) -> str:
    total = data["total"]
    line = f'{total} {"title" if total == 1 else "titles"} on {service_names(data)}'
    if data["new"]:
        line += f' · {data["new"]} new in the last two weeks'
    return line


# ---------------------------------------------------------------- the pictures

CARD_W, CARD_H = ranking_shares.CARD_W, ranking_shares.CARD_H
STORY_W, STORY_H = ranking_shares.STORY_W, ranking_shares.STORY_H
BG, TEXT, SOFT, MUTED = ranking_shares.BG, ranking_shares.TEXT, ranking_shares.SOFT, ranking_shares.MUTED
ACCENT = (96, 165, 250)
NEW = (52, 211, 153)
STRIPES = (ranking_shares.ACCENTS["movies"], ranking_shares.ACCENTS["tv-shows"], ranking_shares.ACCENTS["anime"])


def _stripes(draw, width: int, height: int) -> None:
    """The top bar in the three formats' colours."""
    step = width / len(STRIPES)
    for index, colour in enumerate(STRIPES):
        draw.rectangle((round(index * step), 0, round((index + 1) * step), height), fill=colour)


def _art(image, draw, box, item: dict, place: int, posters: dict, font) -> None:
    """The poster, or a tile with the title's first letter. ``posters`` maps a place (1 = first) to raw bytes."""
    accent = ranking_shares.ACCENTS.get(item["category"], ACCENT)
    ranking_shares._tile(image, draw, box, {"title": item["title"], "position": place}, accent, posters, font)


def _badge(draw, x: int, y: int, font, pad_x: int, pad_y: int, radius: int) -> None:
    text = "NEW"
    width = draw.textlength(text, font=font)
    bounds = draw.textbbox((0, 0), text, font=font)
    height = bounds[3] - bounds[1]
    draw.rounded_rectangle((x, y, x + width + pad_x * 2, y + height + pad_y * 2), radius=radius, fill=NEW)
    draw.text((x + pad_x, y + pad_y - bounds[1]), text, font=font, fill=BG)


def _where(item: dict) -> tuple[str, bool]:
    """"New on Hulu" when an arrival is new, otherwise "Netflix · Hulu"."""
    fresh = [service["name"] for service in item["services"] if service["new"]]
    if fresh:
        return f"New on {_and(fresh)}", True
    return " · ".join(service["name"] for service in item["services"]), False


def render_card(data: dict, posters: dict) -> bytes:
    """The 1200x630 link preview: heading, then up to six posters with the services they're on."""
    from PIL import Image, ImageDraw
    from .routers.profiles import _fit, _font
    image = Image.new("RGB", (CARD_W, CARD_H), BG)
    draw = ImageDraw.Draw(image)
    _stripes(draw, CARD_W, 8)
    pad = 44
    eyebrow_font = _font(19, bold=True)
    eyebrow = f"ON MY SERVICES · {service_names(data).upper()}"
    draw.text((pad, 32), _fit(draw, eyebrow, eyebrow_font, CARD_W - pad * 2), font=eyebrow_font, fill=ACCENT)
    title_font = _font(44, bold=True)
    draw.text((pad, 60), _fit(draw, heading(data), title_font, CARD_W - pad * 2), font=title_font, fill=TEXT)
    line_font = _font(20)
    line = f'{data["total"]} {kind_words(data)} on the list'
    if data["new"]:
        line += f' · {data["new"]} arrived in the last two weeks'
    draw.text((pad, 116), _fit(draw, line, line_font, CARD_W - pad * 2), font=line_font, fill=MUTED)

    shown = data["items"][:PICTURE_SHOWN]
    columns, gap = PICTURE_SHOWN, 16
    # The gap sits between posters only, so the last one ends at the right margin like the line below.
    cell = (CARD_W - pad * 2 + gap) // columns
    art_w, art_h = cell - gap, (cell - gap) * 3 // 2
    top = 160
    name_font, where_font, letter_font, badge_font = _font(18, bold=True), _font(15, bold=True), _font(60, bold=True), _font(13, bold=True)
    for index, item in enumerate(shown):
        x = pad + index * cell
        _art(image, draw, (x, top, x + art_w, top + art_h), item, index + 1, posters, letter_font)
        where, fresh = _where(item)
        if fresh:
            _badge(draw, x + 8, top + 8, badge_font, 7, 4, 6)
        draw.text((x, top + art_h + 12), _fit(draw, item["title"], name_font, art_w), font=name_font, fill=TEXT)
        draw.text((x, top + art_h + 38), _fit(draw, where, where_font, art_w), font=where_font, fill=NEW if fresh else SOFT)

    draw.line((pad, 534, CARD_W - pad, 534), fill=(46, 42, 72), width=2)
    footer = _font(21, bold=True)
    draw.text((pad, 556), "Which of these can you watch?", font=footer, fill=SOFT)
    brand = "omnitrackr.xyz"
    draw.text((CARD_W - pad - draw.textlength(brand, font=footer), 556), brand, font=footer, fill=TEXT)
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def render_story(data: dict, posters: dict) -> bytes:
    """The 1080x1920 picture for stories: heading, then six posters in two rows of three."""
    from PIL import Image, ImageDraw
    from .routers.profiles import _fit, _font
    image = Image.new("RGB", (STORY_W, STORY_H), BG)
    draw = ImageDraw.Draw(image)
    _stripes(draw, STORY_W, 14)
    pad = 84
    width = STORY_W - pad * 2
    eyebrow_font = _font(30, bold=True)
    # Stories cover the top and bottom of the picture with the app's own bars, so everything sits inside them.
    draw.text((pad, 150), _fit(draw, f"ON MY SERVICES · {service_names(data, 2).upper()}", eyebrow_font, width),
              font=eyebrow_font, fill=ACCENT)
    head_font = _font(68, bold=True)
    lines = ranking_shares._wrap(draw, heading(data), head_font, width, 2)
    for number, line in enumerate(lines):
        draw.text((pad, 196 + number * 80), line, font=head_font, fill=TEXT)
    y = 196 + len(lines) * 80 + 18
    line_font = _font(32)
    line = f'{data["total"]} {kind_words(data)} on the list'
    if data["new"]:
        line += f' · {data["new"]} new'
    draw.text((pad, y), _fit(draw, line, line_font, width), font=line_font, fill=MUTED)
    y += 84

    shown = data["items"][:PICTURE_SHOWN]
    columns, gap = 3, 30
    art_w = (width - gap * (columns - 1)) // columns
    art_h = art_w * 3 // 2
    row_h = art_h + 120
    name_font, where_font, letter_font, badge_font = _font(30, bold=True), _font(25, bold=True), _font(110, bold=True), _font(22, bold=True)
    for index, item in enumerate(shown):
        x = pad + (index % columns) * (art_w + gap)
        top = y + (index // columns) * row_h
        _art(image, draw, (x, top, x + art_w, top + art_h), item, index + 1, posters, letter_font)
        where, fresh = _where(item)
        if fresh:
            _badge(draw, x + 12, top + 12, badge_font, 11, 6, 10)
        draw.text((x, top + art_h + 16), _fit(draw, item["title"], name_font, art_w), font=name_font, fill=TEXT)
        draw.text((x, top + art_h + 58), _fit(draw, where, where_font, art_w), font=where_font, fill=NEW if fresh else SOFT)
    more = data["total"] - len(shown)
    if more > 0:
        rows = (len(shown) + columns - 1) // columns
        more_font = _font(32, bold=True)
        text = f"and {more} more on the list"
        draw.text(((STORY_W - draw.textlength(text, font=more_font)) / 2, y + rows * row_h + 6), text, font=more_font, fill=SOFT)

    footer = _font(32, bold=True)
    ask = "Which of these can you watch?"
    draw.text(((STORY_W - draw.textlength(ask, font=footer)) / 2, STORY_H - 256), ask, font=footer, fill=SOFT)
    brand_font = _font(44, bold=True)
    brand = "omnitrackr.xyz"
    draw.text(((STORY_W - draw.textlength(brand, font=brand_font)) / 2, STORY_H - 208), brand, font=brand_font, fill=TEXT)
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
