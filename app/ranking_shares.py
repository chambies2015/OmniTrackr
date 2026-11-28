"""Share links for Rankings (Nov 2026): /ranked/<token> shows a member's top ten in one format.

A member turns a link on from the Rankings tab, one link per format. The page reads the ranking
when it is opened, so the link follows the member's list as it changes, and it shows the order
only, never scores. It works without a public profile, but it stops working the moment the
format is hidden or made private, the member's top drops under three, the account closes or the
member turns the link off. Pages are never indexed.

Whoever opens the link can rank the same titles themselves in the page (no account needed) and
see how far they agree. Keeping that ranking takes an account: the titles go into the new
member's library as finished, and into their Rankings in the order they picked if that ranking
was still empty. Nothing already in a library is changed.

Two images go with every link: a 1200x630 card that chat apps and social sites show, and a
1080x1920 picture for stories, both drawn with Pillow.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timezone
from io import BytesIO
from typing import Iterable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models, rankings, title_pages

BASE_PATH = "/ranked"
TOKEN = re.compile(r"[A-Za-z0-9_-]{16,32}")
MIN_RANKED = 3
TOP = rankings.PUBLIC_TOP
MAX_TITLE = 500

# The format colours the site uses (--kind in member-look.css), for the cards.
ACCENTS = {
    "movies": (244, 114, 182), "tv-shows": (96, 165, 250), "anime": (248, 113, 113), "video-games": (52, 211, 153),
    "music": (167, 139, 250), "books": (251, 191, 36), "manga": (251, 146, 60), "podcasts": (45, 212, 191),
    "audiobooks": (232, 121, 249),
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def valid_token(token) -> bool:
    return isinstance(token, str) and TOKEN.fullmatch(token) is not None


def path_for(share: models.RankingShare) -> str:
    return f"{BASE_PATH}/{share.token}"


def by_token(db: Session, token) -> Optional[models.RankingShare]:
    if not valid_token(token):
        return None
    return db.query(models.RankingShare).filter(models.RankingShare.token == token).first()


def mine(db: Session, user_id: int, category: str) -> Optional[models.RankingShare]:
    return db.query(models.RankingShare).filter(models.RankingShare.user_id == user_id,
                                                models.RankingShare.category == category).first()


def _shareable(user: models.User, category: str) -> bool:
    """Shown in the member's library (not hidden) and not a shelf they keep private."""
    from .public_profiles import _visible_categories
    return category in rankings._visible(user) and category in _visible_categories(user)


def state(db: Session, user: models.User, category: str) -> dict:
    """What the Rankings tab shows about the link for one format."""
    share = mine(db, user.id, category)
    allowed = _shareable(user, category)
    return {
        "path": path_for(share) if share else None,
        "opened": int(share.opened or 0) if share else 0,
        "allowed": allowed,
        "card": f"{path_for(share)}/story.png" if share else None,
    }


def turn_on(db: Session, user: models.User, category: str) -> models.RankingShare:
    """The member's link for this format, made if there isn't one. LookupError when it can't be shared."""
    rankings._check_category(category)
    if not _shareable(user, category):
        raise LookupError("This shelf is hidden or private, so it can't be shared. Change that in Settings first.")
    ranked = rankings._tidy(db, user.id, category, rankings._row(db, user.id, category))
    if len(ranked) < MIN_RANKED:
        raise LookupError("Rank at least three to share your top ten.")
    share = mine(db, user.id, category)
    if share is not None:
        return share
    for _ in range(5):
        token = secrets.token_urlsafe(12)
        if by_token(db, token) is None:
            break
    share = models.RankingShare(user_id=user.id, category=category, token=token, opened=0, created_at=_now())
    db.add(share)
    try:
        db.commit()
    except IntegrityError:  # another tab made it a moment ago
        db.rollback()
        share = mine(db, user.id, category)
        if share is None:
            raise
        return share
    rankings.count("link_on")
    return share


def turn_off(db: Session, user: models.User, category: str) -> bool:
    rankings._check_category(category)
    share = mine(db, user.id, category)
    if share is None:
        return False
    db.delete(share)
    db.commit()
    rankings.count("link_off")
    return True


def count_open(db: Session, share: models.RankingShare) -> None:
    try:
        db.query(models.RankingShare).filter(models.RankingShare.id == share.id).update(
            {models.RankingShare.opened: models.RankingShare.opened + 1}, synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()


def _credit(db: Session, user: models.User) -> Optional[tuple[str, str]]:
    """(name, profile link) when the member already shows a public profile; otherwise None."""
    from .public_profiles import profile_path
    profile = db.query(models.PublicProfile).filter(models.PublicProfile.user_id == user.id).first()
    if profile is not None and profile.enabled:
        return user.username, profile_path(user)
    return None


def view(db: Session, share: models.RankingShare) -> Optional[dict]:
    """What the page and the cards show, or None when the link no longer shows anything."""
    owner = db.get(models.User, share.user_id)
    if owner is None or not owner.is_active or share.category not in rankings.categories():
        return None
    if not _shareable(owner, share.category):
        return None
    category = share.category
    ranked = rankings._tidy(db, owner.id, category, rankings._row(db, owner.id, category))
    if len(ranked) < MIN_RANKED:
        return None
    rows = rankings._rows(db, owner.id, category, ranked[:TOP])
    items = []
    for position, item_id in enumerate(ranked[:TOP], start=1):
        if item_id not in rows:
            continue
        item = rankings.card(category, rows[item_id])
        item.pop("score", None)  # the order is shared, never the scores
        item.pop("id", None)     # nor the member's library ids
        item["position"] = position
        items.append(item)
    if len(items) < MIN_RANKED:
        return None
    credit = _credit(db, owner)
    singular, plural = rankings.NOUNS[category]
    result = {
        "owner_id": owner.id,
        "token": share.token,
        "path": path_for(share),
        "category": category,
        "label": rankings.LABELS[category],
        "noun": singular,
        "nouns": plural,
        "verb": rankings.VERBS[category],
        "items": items,
        "total": len(ranked),
        "by": credit[0] if credit else None,
        "profile": credit[1] if credit else None,
        "opened": int(share.opened or 0),
    }
    result["fingerprint"] = fingerprint(result)
    return result


def fingerprint(data: dict) -> str:
    parts = [data["category"], str(data["total"]), data.get("by") or ""]
    parts += [f'{item["title"]}|{item.get("year") or ""}|{item.get("creator") or ""}|{item.get("image") or ""}'
              for item in data["items"]]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def heading(data: dict) -> str:
    """"nova's top 10 films", or "My top 10 films" when the member has no public profile to name."""
    count = len(data["items"])
    if data.get("by"):
        return f'{data["by"]}\'s top {count} {data["nouns"]}'
    return f'My top {count} {data["nouns"]}'


# ---------------------------------------------------------------- keeping a ranking made on the page

def _picked(items: list[dict], titles: Iterable[str], positions: Optional[Iterable] = None) -> list[dict]:
    """The list's items in the order the visitor ranked them, matched by name.

    A top ten can hold two titles with one name (Dune 1984 and Dune 2021), so each name takes the
    next item of that name not used yet, and ``positions`` (the places the page showed, sent along
    with the names) settles which one was meant while that place still holds that name. The list
    can change between ranking and signing up, so a place alone never decides.
    """
    by_name: dict[str, list[dict]] = {}
    for item in items:
        by_name.setdefault(title_pages.normalize(item["title"]), []).append(item)
    at = {item["position"]: item for item in items}
    places = list(positions) if positions is not None else []
    picked, used = [], set()
    for index, title in enumerate(titles):
        if not isinstance(title, str) or len(title) > MAX_TITLE:
            continue
        key = title_pages.normalize(title)
        place = places[index] if index < len(places) else None
        chosen = at.get(place) if type(place) is int else None
        if chosen is None or chosen["position"] in used or title_pages.normalize(chosen["title"]) != key:
            chosen = next((item for item in by_name.get(key, ()) if item["position"] not in used), None)
        if chosen is not None:
            used.add(chosen["position"])
            picked.append(chosen)
    return picked


def take(db: Session, user: models.User, share: models.RankingShare, titles: Iterable[str],
         positions: Optional[Iterable[int]] = None) -> dict:
    """Put titles from someone's shared top ten into this member's library, finished, in the order they picked.

    ``titles`` are names from the page, best first; only ones on the shared list count. Titles the
    member already has are left as they are. The order goes into their Rankings when that format's
    ranking is still empty; otherwise the new titles wait there to be placed against their own.
    """
    from . import essentials, tier_list
    from .progress import lock_progress_owner
    data = view(db, share)
    if data is None:
        raise LookupError("This list isn't shared anymore.")
    if data["owner_id"] == user.id:
        raise PermissionError("This is your own ranking.")
    picked = _picked(data["items"], titles, positions)
    if len(picked) < 2:
        raise LookupError("Rank at least two of the titles on this list first.")
    category = data["category"]
    kind = title_pages.LIBRARY_TO_KIND[category]
    done_field = title_pages.COMPLETE_FIELD[kind]
    lock_progress_owner(db, user.id)
    added = existing = waiting = 0
    order = []
    for item in picked:
        entry = {"id": f"ranked/{data['token']}/{item['position']}", "kind": kind, "slug": "",
                 "title": item["title"], "year": item.get("year"), "creator": item.get("creator")}
        # The poster comes along only from the usual poster hosts, not from any address the sharer typed in.
        image = item.get("image") if tier_list.image_allowed(item.get("image")) else None
        state, record = essentials.add(db, user, entry, True, image)
        if state == "created":
            added += 1
        else:
            existing += 1
        # Only finished titles can be ranked; one already on the member's shelf unfinished stays that way.
        if isinstance(record, rankings._categories()[category][0]) and getattr(record, done_field, False):
            order.append(record.id)
        else:
            waiting += 1
    row = rankings._row_for_write(db, user.id, category)
    ranked = rankings._tidy(db, user.id, category, row)
    order = list(dict.fromkeys(order))
    in_ranking = False
    already = queued = 0
    # They ranked these just now, so none of them stays left out.
    left_out = [value for value in rankings._ids(row.left_out) if value not in set(order)]
    row.left_out = rankings._dump(left_out) if left_out else None
    if not ranked and len(order) >= 2:
        row.ranked = rankings._dump(order[:rankings.MAX_RANKED])
        row.placed_total = (row.placed_total or 0) + len(order)
        rankings._cancel(row)
        in_ranking = True
    else:
        have = set(ranked)
        already = sum(1 for value in order if value in have)
        queued = len(order) - already
    row.updated_at = _now()
    db.commit()
    rankings.count("taken")
    singular, plural = rankings.NOUNS[category]
    return {"category": category, "nouns": plural, "noun": singular, "added": added, "existing": existing,
            "unfinished": waiting, "ranked": in_ranking, "count": len(order), "queued": queued,
            "already_ranked": already}


# ---------------------------------------------------------------- the pictures

CARD_W, CARD_H = 1200, 630
STORY_W, STORY_H = 1080, 1920
POSTER_PIXELS = 12_000_000  # after JPEG draft scaling; a real poster is well under 2 million
BG = (11, 10, 24)
PANEL = (22, 20, 36)
TEXT = (245, 243, 255)
SOFT = (196, 191, 222)
MUTED = (150, 146, 178)
MEDALS = {1: (245, 196, 81), 2: (207, 214, 228), 3: (227, 161, 114)}


def _poster(source: Optional[bytes], size: tuple[int, int]):
    """The poster scaled to fill ``size``, or None for a missing, broken or oversized image."""
    if not source:
        return None
    from PIL import Image, ImageOps
    try:
        with Image.open(BytesIO(source)) as image:
            image.draft("RGB", (size[0] * 2, size[1] * 2))
            width, height = image.size
            # A small file can still decode to hundreds of megabytes (a huge PNG), so those get a drawn tile.
            if not 0 < width * height <= POSTER_PIXELS:
                return None
            return ImageOps.fit(image.convert("RGB"), size)
    except Exception:
        return None


def _tile(image, draw, box, item: dict, accent, posters: dict, font) -> None:
    """A poster at ``box``, or a tile in the format's colour with the title's first letter."""
    x0, y0, x1, y1 = box
    picture = _poster(posters.get(item["position"]), (x1 - x0, y1 - y0))
    if picture is not None:
        image.paste(picture, (x0, y0))
        return
    draw.rectangle(box, fill=tuple(int(value * .42) for value in accent))
    letter = (item["title"].strip()[:1] or "?").upper()
    width = draw.textlength(letter, font=font)
    bounds = draw.textbbox((0, 0), letter, font=font)
    draw.text((x0 + (x1 - x0 - width) / 2, y0 + (y1 - y0 - (bounds[3] - bounds[1])) / 2 - bounds[1]), letter,
              font=font, fill=TEXT)


def _meta(item: dict) -> str:
    return " · ".join(str(part) for part in (item.get("creator"), item.get("year")) if part)


def _place_colour(position: int, accent):
    return MEDALS.get(position, accent)


def _wrap(draw, text: str, font, width: int, lines: int) -> list[str]:
    from .routers.profiles import _fit
    words, result, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width or not line:
            line = trial
        else:
            result.append(line)
            line = word
    if line:
        result.append(line)
    if len(result) > lines:
        result = result[:lines - 1] + [" ".join(result[lines - 1:])]
    return [_fit(draw, part, font, width) for part in result]


def render_card(data: dict, posters: dict) -> bytes:
    """The 1200x630 link preview: #1 large on the left, #2 to #10 in a grid beside it.

    ``posters`` maps a place (1 = top) to the poster's raw bytes.
    """
    from PIL import Image, ImageDraw
    from .routers.profiles import _fit, _font
    accent = ACCENTS.get(data["category"], (139, 92, 246))
    image = Image.new("RGB", (CARD_W, CARD_H), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, CARD_W, 8), fill=accent)
    pad = 44
    items = data["items"]
    eyebrow = f'RANKED ON OMNITRACKR · {data["total"]} {data["nouns"].upper()} IN ORDER'
    draw.text((pad, 32), _fit(draw, eyebrow, _font(19, bold=True), CARD_W - pad * 2), font=_font(19, bold=True), fill=accent)
    title_font = _font(44, bold=True)
    draw.text((pad, 60), _fit(draw, heading(data), title_font, CARD_W - pad * 2), font=title_font, fill=TEXT)

    top = items[0]
    hero = (pad, 134, pad + 248, 134 + 372)
    _tile(image, draw, hero, top, accent, posters, _font(96, bold=True))
    badge = _font(30, bold=True)
    draw.rounded_rectangle((hero[0] + 10, hero[1] + 10, hero[0] + 66, hero[1] + 56), radius=10, fill=MEDALS[1])
    width = draw.textlength("1", font=badge)
    draw.text((hero[0] + 38 - width / 2, hero[1] + 14), "1", font=badge, fill=BG)

    right = hero[2] + 34
    span = CARD_W - pad - right
    draw.text((right, 134), "#1", font=_font(22, bold=True), fill=MEDALS[1])
    big = _font(36, bold=True)
    draw.text((right, 160), _fit(draw, top["title"], big, span), font=big, fill=TEXT)
    meta = _meta(top)
    if meta:
        draw.text((right, 206), _fit(draw, meta, _font(20), span), font=_font(20), fill=MUTED)

    columns, cell_w, cell_h = 3, span // 3, 86
    number_font, name_font, small_font = _font(26, bold=True), _font(19, bold=True), _font(15)
    tile_font = _font(26, bold=True)
    for index, item in enumerate(items[1:10]):
        x = right + (index % columns) * cell_w
        y = 252 + (index // columns) * cell_h
        _tile(image, draw, (x, y, x + 52, y + 78), item, accent, posters, tile_font)
        text_x = x + 64
        room = cell_w - 64 - 12
        draw.text((text_x, y + 2), str(item["position"]), font=number_font, fill=_place_colour(item["position"], accent))
        draw.text((text_x, y + 34), _fit(draw, item["title"], name_font, room), font=name_font, fill=TEXT)
        line = item.get("year") and str(item["year"]) or item.get("creator") or ""
        if line:
            draw.text((text_x, y + 58), _fit(draw, str(line), small_font, room), font=small_font, fill=MUTED)

    draw.line((pad, 534, CARD_W - pad, 534), fill=(46, 42, 72), width=2)
    footer = _font(21, bold=True)
    draw.text((pad, 556), "Rank them yourself and see how much you agree", font=footer, fill=SOFT)
    brand = "omnitrackr.xyz"
    draw.text((CARD_W - pad - draw.textlength(brand, font=footer), 556), brand, font=footer, fill=TEXT)
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def render_story(data: dict, posters: dict) -> bytes:
    """The 1080x1920 picture for stories: #1 poster large, then the rest of the top ten as rows."""
    from PIL import Image, ImageDraw
    from .routers.profiles import _fit, _font
    accent = ACCENTS.get(data["category"], (139, 92, 246))
    image = Image.new("RGB", (STORY_W, STORY_H), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, STORY_W, 14), fill=accent)
    pad = 84
    items = data["items"]
    eyebrow_font = _font(30, bold=True)
    eyebrow = f'RANKED ON OMNITRACKR · {data["total"]} {data["nouns"].upper()}'
    # Stories cover the top and bottom of the picture with the app's own bars, so everything sits inside them.
    draw.text((pad, 150), _fit(draw, eyebrow, eyebrow_font, STORY_W - pad * 2), font=eyebrow_font, fill=accent)
    head_font = _font(68, bold=True)
    lines = _wrap(draw, heading(data), head_font, STORY_W - pad * 2, 2)
    for number, line in enumerate(lines):
        draw.text((pad, 196 + number * 80), line, font=head_font, fill=TEXT)
    y = 196 + len(lines) * 80 + 34

    top = items[0]
    poster_w, poster_h = 290, 435
    x = (STORY_W - poster_w) // 2
    _tile(image, draw, (x, y, x + poster_w, y + poster_h), top, accent, posters, _font(160, bold=True))
    badge = _font(48, bold=True)
    draw.rounded_rectangle((x - 30, y - 22, x + 54, y + 62), radius=18, fill=MEDALS[1])
    width = draw.textlength("1", font=badge)
    draw.text((x + 12 - width / 2, y - 8), "1", font=badge, fill=BG)
    y += poster_h + 30
    title_font = _font(50, bold=True)
    for line in _wrap(draw, top["title"], title_font, STORY_W - pad * 2, 2):
        draw.text(((STORY_W - draw.textlength(line, font=title_font)) / 2, y), line, font=title_font, fill=TEXT)
        y += 60
    meta = _meta(top)
    if meta:
        meta = _fit(draw, meta, _font(30), STORY_W - pad * 2)
        draw.text(((STORY_W - draw.textlength(meta, font=_font(30))) / 2, y + 2), meta, font=_font(30), fill=MUTED)
        y += 44
    y += 30

    rest = items[1:10]
    bottom = STORY_H - 290
    row_h = min(96, (bottom - y) // max(1, len(rest))) if rest else 0
    number_font, name_font, small_font = _font(40, bold=True), _font(34, bold=True), _font(25)
    art_h = max(40, row_h - 14)
    art_w = art_h * 2 // 3
    for item in rest:
        draw.text((pad, y + (row_h - 46) / 2), str(item["position"]), font=number_font,
                  fill=_place_colour(item["position"], accent))
        art_x = pad + 76
        _tile(image, draw, (art_x, y + 4, art_x + art_w, y + 4 + art_h), item, accent, posters, _font(28, bold=True))
        text_x = art_x + art_w + 24
        room = STORY_W - pad - text_x
        line = _meta(item)
        if line and row_h >= 76:
            draw.text((text_x, y + row_h / 2 - 40), _fit(draw, item["title"], name_font, room), font=name_font, fill=TEXT)
            draw.text((text_x, y + row_h / 2 + 2), _fit(draw, line, small_font, room), font=small_font, fill=MUTED)
        else:
            draw.text((text_x, y + row_h / 2 - 22), _fit(draw, item["title"], name_font, room), font=name_font, fill=TEXT)
        y += row_h

    footer = _font(32, bold=True)
    ask = "Rank them yourself at"
    draw.text(((STORY_W - draw.textlength(ask, font=footer)) / 2, STORY_H - 256), ask, font=footer, fill=SOFT)
    brand_font = _font(44, bold=True)
    brand = "omnitrackr.xyz"
    draw.text(((STORY_W - draw.textlength(brand, font=brand_font)) / 2, STORY_H - 208), brand, font=brand_font, fill=TEXT)
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
