"""Shared tier lists (/tier-list/s/<token>): a ranked board turned into a link (Nov 2026).

Anyone can make a link, with or without an account. The board is copied in as plain
data (title, kind, year, slug, an allowlisted poster URL), so a shared list never
reads or changes anyone's library. Links made without an account have no owner: the
browser that made one holds an edit key, the link stops working after
GUEST_DAYS, and signing up claims it (the key moves it into the new account and the
expiry goes away). Shared pages are always noindex and never listed anywhere.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from . import models, tier_list, title_pages
from .review_quality import EMAIL_PATTERN, PHONE_PATTERN, URL_PATTERN

TOKEN = re.compile(r"^[A-Za-z0-9_-]{16,32}$")
SLUG = re.compile(r"^[a-z0-9-]{1,130}$")
MIN_RANKED = 3
MAX_ITEMS = 150
MAX_LABEL = 24
MAX_NAME = 80
GUEST_DAYS = 30
MEMBER_MAX_LINKS = 100
GUEST_MAX_LINKS = 12  # Live links per browser without an account.
CLAIM_MAX = 30
MINE_SHOWN = 50
# Bare domains the URL check would miss ("cheap-pills.ru"). Kept short on purpose: a
# title like "Dot.com" is rare, a spam link in a shared list is not.
DOMAIN = re.compile(r"\b[a-z0-9-]{2,}\.(?:com|net|org|ru|io|xyz|ly|gg|link|click|top|info|biz|cn|tk|shop|site|online)\b",
                    re.IGNORECASE)


class ShareError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _now() -> datetime:
    return datetime.utcnow()


def valid_token(token) -> bool:
    return isinstance(token, str) and TOKEN.match(token) is not None


def path_for(share: models.TierListShare) -> str:
    return f"/tier-list/s/{share.token}"


def key_hash(key: str) -> str:
    return hashlib.sha256(f"tier-list:{key}".encode("utf-8")).hexdigest()


def key_matches(share: models.TierListShare, key) -> bool:
    return isinstance(key, str) and 20 <= len(key) <= 80 and hmac.compare_digest(share.key_hash, key_hash(key))


def _clean_text(value, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def text_allowed(value: str) -> bool:
    """False for text carrying a link, an email address or a phone number."""
    return not (URL_PATTERN.search(value) or EMAIL_PATTERN.search(value) or PHONE_PATTERN.search(value)
                or DOMAIN.search(value))


def clean_item(raw) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    title = _clean_text(raw.get("title"), 200)
    if not title:
        return None
    kind = raw.get("kind") if raw.get("kind") in title_pages.KINDS else None
    year = raw.get("year")
    year = year if isinstance(year, int) and not isinstance(year, bool) and 1000 <= year <= 2200 else None
    slug = raw.get("slug")
    slug = slug if kind and isinstance(slug, str) and SLUG.match(slug) else None
    image = raw.get("image")
    # Only poster hosts the image proxy already trusts, so a shared page can't carry a tracking pixel.
    image = image if tier_list.image_allowed(image) and str(image).startswith("https://") else None
    return {"title": title, "kind": kind, "year": year, "slug": slug, "image": image}


def clean_board(name, labels, tiers) -> tuple[str, dict, dict, int]:
    """(name, labels, tiers, ranked count) from what a browser sent, or ShareError."""
    name = _clean_text(name, MAX_NAME) or "My tier list"
    clean_labels = {}
    for tier in tier_list.TIERS:
        label = _clean_text((labels or {}).get(tier) if isinstance(labels, dict) else None, MAX_LABEL)
        clean_labels[tier] = label or tier
    clean_tiers = {tier: [] for tier in tier_list.TIERS}
    seen = set()
    total = 0
    source = tiers if isinstance(tiers, dict) else {}
    for tier in tier_list.TIERS:
        rows = source.get(tier)
        for raw in rows if isinstance(rows, list) else []:
            if total >= MAX_ITEMS:
                break
            item = clean_item(raw)
            if item is None:
                continue
            key = (item["title"].casefold(), item["kind"] or "", item["year"] or 0)
            if key in seen:
                continue
            seen.add(key)
            clean_tiers[tier].append(item)
            total += 1
    if total < MIN_RANKED:
        raise ShareError(f"Put at least {MIN_RANKED} titles in tiers before making a link.")
    texts = [name, *clean_labels.values(), *(item["title"] for rows in clean_tiers.values() for item in rows)]
    if not all(text_allowed(text) for text in texts):
        raise ShareError("Links, email addresses and phone numbers can't go on a shared tier list. "
                         "Take them out of the name, the tier labels or the titles and try again.")
    return name, clean_labels, clean_tiers, total


def by_token(db: Session, token, *, lock: bool = False) -> Optional[models.TierListShare]:
    """A live link, or None (unknown, malformed or expired)."""
    if not valid_token(token):
        return None
    query = db.query(models.TierListShare).filter(models.TierListShare.token == token)
    if lock:
        query = query.with_for_update()
    share = query.first()
    if share is None or (share.expires_at is not None and share.expires_at <= _now()):
        return None
    return share


def board(share: models.TierListShare) -> dict:
    try:
        data = json.loads(share.board or "{}")
    except ValueError:
        data = {}
    labels = data.get("labels") if isinstance(data.get("labels"), dict) else {}
    tiers = data.get("tiers") if isinstance(data.get("tiers"), dict) else {}
    return {
        "labels": {tier: str(labels.get(tier) or tier)[:MAX_LABEL] for tier in tier_list.TIERS},
        "tiers": {tier: [item for item in (tiers.get(tier) or []) if isinstance(item, dict) and item.get("title")]
                  for tier in tier_list.TIERS},
    }


def _purge_expired(db: Session) -> None:
    expired = (db.query(models.TierListShare.id)
               .filter(models.TierListShare.expires_at.isnot(None), models.TierListShare.expires_at <= _now())
               .limit(200).all())
    if expired:
        db.query(models.TierListShare).filter(models.TierListShare.id.in_([row.id for row in expired])) \
            .delete(synchronize_session=False)


def _new_token(db: Session) -> str:
    while True:
        token = secrets.token_urlsafe(12)
        if not db.query(models.TierListShare.id).filter(models.TierListShare.token == token).first():
            return token


def create(db: Session, user, visitor: Optional[str], payload: dict) -> tuple[models.TierListShare, str]:
    """A new link and its edit key (the key is shown once, to the browser that made it)."""
    name, labels, tiers, total = clean_board(payload.get("name"), payload.get("labels"), payload.get("tiers"))
    _purge_expired(db)
    now = _now()
    if user is not None:
        mine = db.query(models.TierListShare.id).filter(models.TierListShare.owner_id == user.id).count()
        if mine >= MEMBER_MAX_LINKS:
            raise ShareError(f"You have {MEMBER_MAX_LINKS} shared tier lists. Delete one to make another.", 409)
    else:
        live = (db.query(models.TierListShare.id)
                .filter(models.TierListShare.owner_id.is_(None), models.TierListShare.visitor == visitor).count()
                if visitor else 0)
        if live >= GUEST_MAX_LINKS:
            raise ShareError("This browser already has a lot of tier list links. Create a free account to make more "
                             "and keep them for good.", 409)
    source = by_token(db, payload.get("source"), lock=True) if payload.get("source") else None
    template = payload.get("template")
    template = template if isinstance(template, str) and re.match(r"^[a-z0-9-]{1,60}$", template) else None
    if template is None and source is not None:
        template = source.template_key
    key = secrets.token_urlsafe(24)
    share = models.TierListShare(
        token=_new_token(db), owner_id=user.id if user is not None else None,
        visitor=None if user is not None else visitor, key_hash=key_hash(key), name=name,
        board=json.dumps({"labels": labels, "tiers": tiers}, ensure_ascii=False, separators=(",", ":")),
        item_count=total, template_key=template, source_id=source.id if source is not None else None,
        created_at=now, updated_at=now,
        expires_at=None if user is not None else now + timedelta(days=GUEST_DAYS),
    )
    db.add(share)
    if source is not None and source.id != share.id:
        source.remixes = (source.remixes or 0) + 1
    db.commit()
    db.refresh(share)
    return share, key


def can_edit(share: models.TierListShare, user, key) -> bool:
    if user is not None and share.owner_id == user.id:
        return True
    return key_matches(share, key)


def update(db: Session, share: models.TierListShare, user, payload: dict) -> models.TierListShare:
    if not can_edit(share, user, payload.get("key")):
        raise ShareError("Only the person who made this link can change it.", 403)
    name, labels, tiers, total = clean_board(payload.get("name"), payload.get("labels"), payload.get("tiers"))
    share.name = name
    share.board = json.dumps({"labels": labels, "tiers": tiers}, ensure_ascii=False, separators=(",", ":"))
    share.item_count = total
    share.updated_at = _now()
    db.commit()
    db.refresh(share)
    return share


def delete(db: Session, share: models.TierListShare, user, key) -> None:
    if not can_edit(share, user, key):
        raise ShareError("Only the person who made this link can delete it.", 403)
    db.delete(share)
    db.commit()


def claim(db: Session, user, links) -> int:
    """Move links made in this browser before signing up into the member's account."""
    claimed = 0
    for link in (links if isinstance(links, list) else [])[:CLAIM_MAX]:
        if not isinstance(link, dict):
            continue
        share = by_token(db, link.get("token"), lock=True)
        if share is None or share.owner_id is not None or not key_matches(share, link.get("key")):
            continue
        if db.query(models.TierListShare.id).filter(models.TierListShare.owner_id == user.id).count() >= MEMBER_MAX_LINKS:
            break
        share.owner_id = user.id
        share.visitor = None
        share.expires_at = None
        db.flush()
        claimed += 1
    if claimed:
        db.commit()
    return claimed


def count_view(db: Session, share: models.TierListShare) -> None:
    db.query(models.TierListShare).filter(models.TierListShare.id == share.id) \
        .update({models.TierListShare.views: models.TierListShare.views + 1}, synchronize_session=False)
    db.commit()


def credit(db: Session, share: models.TierListShare) -> Optional[tuple[str, str]]:
    """(name, profile link) when the maker already shows a public profile; otherwise None."""
    if share.owner_id is None:
        return None
    from .public_profiles import profile_path
    row = (db.query(models.User, models.PublicProfile)
           .outerjoin(models.PublicProfile, models.PublicProfile.user_id == models.User.id)
           .filter(models.User.id == share.owner_id, models.User.is_active == True).first())  # noqa: E712
    if row is None:
        return None
    user, profile = row
    if profile is not None and profile.enabled:
        return user.username, profile_path(user)
    return None


def byline(db: Session, share: models.TierListShare) -> str:
    named = credit(db, share)
    if named:
        return named[0]
    return "an OmniTrackr member" if share.owner_id is not None else "someone on OmniTrackr"


def source_of(db: Session, share: models.TierListShare) -> Optional[models.TierListShare]:
    if not share.source_id:
        return None
    source = db.query(models.TierListShare).filter(models.TierListShare.id == share.source_id).first()
    if source is None or (source.expires_at is not None and source.expires_at <= _now()):
        return None
    return source


def public_state(db: Session, share: models.TierListShare) -> dict:
    """What anyone with the link may read: the board, its maker's public name, and the counts."""
    source = source_of(db, share)
    return {
        "token": share.token, "path": path_for(share), "name": share.name, "by": byline(db, share),
        "template": share.template_key, "count": share.item_count, **board(share),
        "views": share.views or 0, "remixes": share.remixes or 0,
        "source": {"name": source.name, "path": path_for(source)} if source is not None else None,
        "updated_at": share.updated_at.isoformat() + "Z" if share.updated_at else None,
    }


def mine(db: Session, user) -> list[dict]:
    rows = (db.query(models.TierListShare).filter(models.TierListShare.owner_id == user.id)
            .order_by(models.TierListShare.updated_at.desc(), models.TierListShare.id.desc()).limit(MINE_SHOWN).all())
    return [{"token": row.token, "path": path_for(row), "name": row.name, "count": row.item_count,
             "views": row.views or 0, "remixes": row.remixes or 0,
             "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else None} for row in rows]


def fingerprint(share: models.TierListShare, by: str) -> str:
    return hashlib.sha256(json.dumps([share.id, share.name, share.board, by]).encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- share card

TIER_RGB = {"S": (244, 114, 182), "A": (251, 146, 60), "B": (250, 204, 21), "C": (74, 222, 128), "D": (96, 165, 250)}
CARD_W, CARD_H = 1200, 630
CARD_PAD = 44
CARD_LABEL = 92
CARD_TILE_W, CARD_TILE_H, CARD_GAP = 50, 74, 6
CARD_TOP, CARD_BOTTOM = 128, 62
CARD_POSTER_PIXELS = 12_000_000  # after JPEG draft scaling; a real poster is well under 2 million


def card_per_row() -> int:
    usable = CARD_W - CARD_PAD * 2 - CARD_LABEL - CARD_GAP
    return (usable + CARD_GAP) // (CARD_TILE_W + CARD_GAP)


def card_items(data: dict) -> list[tuple[str, int, dict]]:
    """(tier, position, item) for every tile the card has room to draw."""
    per_row = card_per_row()
    shown = []
    for tier in tier_list.TIERS:
        items = data["tiers"][tier]
        room = per_row if len(items) <= per_row else per_row - 1
        shown.extend((tier, index, item) for index, item in enumerate(items[:room]))
    return shown


def render_card(name: str, data: dict, by: str, posters: dict) -> bytes:
    """A 1200x630 link-preview card: the five tiers with posters where we have them.

    ``posters`` maps (tier, position) to raw image bytes.
    """
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageOps
    from .routers.profiles import _fit, _font
    image = Image.new("RGB", (CARD_W, CARD_H), (11, 10, 24))
    draw = ImageDraw.Draw(image)
    total = sum(len(items) for items in data["tiers"].values())
    draw.text((CARD_PAD, 30), f"TIER LIST · {total} TITLE{'' if total == 1 else 'S'} · BY {by.upper()}"[:90],
              font=_font(20, bold=True), fill=(94, 234, 212))
    draw.text((CARD_PAD, 60), _fit(draw, name, _font(42, bold=True), CARD_W - CARD_PAD * 2), font=_font(42, bold=True),
              fill=(245, 243, 255))
    rows_height = CARD_H - CARD_TOP - CARD_BOTTOM
    row_h = (rows_height - 4 * 6) // 5
    per_row = card_per_row()
    tile_font = _font(10, bold=True)
    more_font = _font(18, bold=True)
    y = CARD_TOP
    for tier in tier_list.TIERS:
        items = data["tiers"][tier]
        draw.rounded_rectangle((CARD_PAD, y, CARD_PAD + CARD_LABEL, y + row_h), radius=8, fill=TIER_RGB[tier])
        draw.rectangle((CARD_PAD + CARD_LABEL, y, CARD_W - CARD_PAD, y + row_h), fill=(22, 20, 31))
        label = data["labels"].get(tier) or tier
        label_font = _font(40 if len(label) <= 2 else 15, bold=True)
        label_text = _fit(draw, label, label_font, CARD_LABEL - 12)
        width = draw.textlength(label_text, font=label_font)
        box = draw.textbbox((0, 0), label_text, font=label_font)
        draw.text((CARD_PAD + (CARD_LABEL - width) / 2, y + (row_h - (box[3] - box[1])) / 2 - box[1]), label_text,
                  font=label_font, fill=(11, 10, 24))
        room = per_row if len(items) <= per_row else per_row - 1
        tile_y = y + (row_h - CARD_TILE_H) // 2
        for index, item in enumerate(items[:room]):
            x = CARD_PAD + CARD_LABEL + CARD_GAP + index * (CARD_TILE_W + CARD_GAP)
            poster = posters.get((tier, index))
            drawn = False
            if poster:
                try:
                    with Image.open(BytesIO(poster)) as source:
                        source.draft("RGB", (CARD_TILE_W * 2, CARD_TILE_H * 2))
                        width, height = source.size
                        # A small file can still decode to hundreds of megabytes (a huge PNG on
                        # Wikimedia or archive.org), so oversized posters get a text tile instead.
                        if 0 < width * height <= CARD_POSTER_PIXELS:
                            tile = ImageOps.fit(source.convert("RGB"), (CARD_TILE_W, CARD_TILE_H))
                            image.paste(tile, (x, tile_y))
                            drawn = True
                except Exception:
                    drawn = False
            if not drawn:
                draw.rectangle((x, tile_y, x + CARD_TILE_W, tile_y + CARD_TILE_H), fill=(49, 46, 129))
                words, lines, line = item["title"].split(), [], ""
                for word in words:
                    trial = f"{line} {word}".strip()
                    if draw.textlength(trial, font=tile_font) <= CARD_TILE_W - 6 or not line:
                        line = trial
                    else:
                        lines.append(line)
                        line = word
                if line:
                    lines.append(line)
                for number, text in enumerate(lines[:5]):
                    text = _fit(draw, text, tile_font, CARD_TILE_W - 6)
                    draw.text((x + 3, tile_y + 4 + number * 13), text, font=tile_font, fill=(255, 255, 255))
        if len(items) > room:
            x = CARD_PAD + CARD_LABEL + CARD_GAP + room * (CARD_TILE_W + CARD_GAP)
            draw.rounded_rectangle((x, tile_y, x + CARD_TILE_W, tile_y + CARD_TILE_H), radius=6, fill=(38, 34, 64))
            more = f"+{len(items) - room}"
            width = draw.textlength(more, font=more_font)
            draw.text((x + (CARD_TILE_W - width) / 2, tile_y + CARD_TILE_H / 2 - 11), more, font=more_font,
                      fill=(196, 181, 253))
        y += row_h + 6
    footer_font = _font(20, bold=True)
    draw.text((CARD_PAD, CARD_H - 44), "Rank the same titles yourself", font=footer_font, fill=(196, 181, 253))
    brand = "omnitrackr.xyz/tier-list"
    draw.text((CARD_W - CARD_PAD - draw.textlength(brand, font=footer_font), CARD_H - 44), brand, font=footer_font,
              fill=(245, 243, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
