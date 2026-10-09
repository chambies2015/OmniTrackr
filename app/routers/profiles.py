"""Opt-in public profiles: /u/<username>, its share card, and the owner's settings."""
from __future__ import annotations

import hashlib
import io
import os
import threading
from collections import OrderedDict
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models, public_profiles
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..site_chrome import apply_site_chrome

router = APIRouter(tags=["profiles"])
SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
CSS_VERSION = "20261008-supporters-1"
TITLE_CSS_VERSION = "20261009-take-1"


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _excerpt(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def _rating(value) -> str:
    if value is None:
        return ""
    return f"{value:g}" if isinstance(value, float) else str(value)


class ProfileSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    bio: Optional[str] = Field(None, max_length=2000)
    show_stats: Optional[bool] = None
    show_favorites: Optional[bool] = None
    show_reviews: Optional[bool] = None
    show_collections: Optional[bool] = None


@router.get("/api/profile/settings")
def profile_settings(response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return public_profiles.settings_payload(user, public_profiles.get_settings(db, user.id))


@router.put("/api/profile/settings")
def update_profile_settings(
    payload: ProfileSettingsUpdate,
    request: Request,
    response: Response,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "private, no-store"
    changes = payload.model_dump(exclude_unset=True)
    try:
        profile = public_profiles.save_settings(db, user, changes)
    except public_profiles.BioError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error))
    _CARD_CACHE.clear_user(user.id)
    return public_profiles.settings_payload(user, profile)


# ---------------------------------------------------------------- page

def _avatar_html(user: models.User) -> str:
    if user.profile_picture_data:
        return f'<img class="profile-hero__avatar" src="/profile-pictures/{user.id}" alt="" width="120" height="120">'
    initial = (user.username or "?")[:1].upper()
    return f'<div class="profile-hero__avatar profile-hero__avatar--empty" aria-hidden="true">{_e(initial)}</div>'


def _supporter_html(view) -> str:
    if not view.supporter:
        return ""
    since = view.supporter.get("since")
    title = f"Supporting OmniTrackr on Ko-fi since {since:%B} {since.year}" if since else "Supports OmniTrackr on Ko-fi"
    return (f'<a class="profile-supporter" href="/supporters" title="{_e(title)}">'
            '<span aria-hidden="true">♥</span> Supporter</a>')


def _hero_class(view) -> str:
    accent = (view.supporter or {}).get("accent")
    classes = "profile-hero"
    if view.supporter:
        classes += " profile-hero--supporter"
    if accent:
        classes += f" profile-hero--accent-{accent}"
    return classes


def _stats_html(view) -> str:
    if not view.stats:
        return ""
    tiles = "".join(
        f'<div class="profile-stat"><strong>{_e(row["total"])}</strong><span>{_e(row["label"])}</span>'
        f'<small>{_e(row["finished"])} {_e(row["verb"])}</small>'
        + (f'<small>avg <b class="profile-rating">{_e(row["average"])}/10</b></small>' if row["average"] is not None else "")
        + "</div>"
        for row in view.stats
    )
    return (f'<section class="title-section" aria-labelledby="profile-stats"><h2 id="profile-stats">Library</h2>'
            f'<div class="profile-stats">{tiles}</div></section>')


def _favorites_html(view) -> str:
    if not view.favorites:
        return ""
    cards = ""
    for item in view.favorites:
        art = (f'<img src="{_e(item["image"])}" alt="" loading="lazy">' if item.get("image")
               else f'<span>{_e(item["title"][:1].upper())}</span>')
        year = f' · {item["year"]}' if item.get("year") else ""
        cards += (f'<a class="title-related" href="{_e(item["url"])}"><span class="title-related__art">{art}</span>'
                  f'<strong>{_e(item["title"])}</strong><small>{_e(item["label"])}{_e(year)} · '
                  f'<span class="profile-rating">{_e(_rating(item["rating"]))}/10</span></small></a>')
    return (f'<section class="title-section" aria-labelledby="profile-favorites"><h2 id="profile-favorites">Favorites</h2>'
            f'<div class="title-related-grid">{cards}</div></section>')


def _reviews_html(view) -> str:
    if not view.reviews:
        return ""
    cards = ""
    for review in view.reviews:
        rating = f'<span class="title-review__rating">{_e(_rating(review["rating"]))}/10</span>' if review["rating"] is not None else ""
        cards += (f'<article class="title-review"><header><a class="profile-review__title" href="{_e(review["title_url"])}">'
                  f'{_e(review["title"])}</a><span class="site-chip">{_e(review["label"])}</span>{rating}</header>'
                  f'<p>{_e(_excerpt(review["review"], 360))}</p>'
                  f'<a href="{_e(review["url"])}">Read the full review <span aria-hidden="true">→</span></a></article>')
    return (f'<section class="title-section" aria-labelledby="profile-reviews"><h2 id="profile-reviews">Reviews</h2>'
            f'<div class="title-reviews">{cards}</div></section>')


def _collections_html(view) -> str:
    if not view.collections:
        return ""
    cards = "".join(
        f'<a class="title-collection" href="{_e(c["url"])}"><strong>{_e(c["name"])}</strong>'
        f'<span>{_e(_excerpt(c["description"], 140) or str(c["items"]) + " titles")}</span></a>'
        for c in view.collections)
    return (f'<section class="title-section" aria-labelledby="profile-collections"><h2 id="profile-collections">Public collections</h2>'
            f'<div class="title-collections">{cards}</div></section>')


def _bio_html(bio: Optional[str]) -> str:
    if not bio:
        return ""
    return "".join(f'<p class="profile-hero__bio">{_e(part)}</p>' for part in bio.split("\n") if part.strip())


def render(view, *, signed_in: bool, is_owner: bool) -> str:
    user, profile = view.user, view.profile
    canonical = SITE_URL + view.path
    name = user.username
    since = f"Member since {user.created_at:%B} {user.created_at.year}" if user.created_at else "OmniTrackr member"
    summary_bits = []
    if view.total_titles:
        summary_bits.append(f"{view.total_titles} title{'s' if view.total_titles != 1 else ''} tracked")
    if view.reviews:
        summary_bits.append(f"{len(view.reviews)} public review{'s' if len(view.reviews) != 1 else ''}")
    if view.collections:
        summary_bits.append(f"{len(view.collections)} collection{'s' if len(view.collections) != 1 else ''}")
    lead = profile.bio or ""
    meta_description = _excerpt(
        (f"{name} on OmniTrackr: " + (", ".join(summary_bits) if summary_bits else "movies, shows, games, music and books"))
        + (f". {lead}" if lead else "."), 158)
    robots = "index, follow" if view.indexable else "noindex, follow"
    card_url = f"{SITE_URL}{view.path}/card.png"
    body = "".join([_stats_html(view), _favorites_html(view), _reviews_html(view), _collections_html(view)])
    if not body:
        body = f'<p class="title-empty">{_e(name)} hasn\'t shared anything here yet.</p>'
    owner_note = ('<p class="profile-owner-note">This is your public profile. Change what it shows from '
                  '<a href="/#public-profile">Account → Public profile</a>.</p>' if is_owner else "")
    cta = ("" if signed_in else
           '<section class="profile-cta site-card"><div><h2>Track your own movies, shows, games, music and books</h2>'
           '<p>OmniTrackr is free. Build your library, rate what you finish and share a profile like this one.</p></div>'
           '<a class="site-btn site-btn--primary" href="/#signup">Start tracking free</a></section>')
    chips = "".join(f'<span class="site-chip">{_e(bit)}</span>' for bit in summary_bits)
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_e(name)} on OmniTrackr</title>
  <meta name="description" content="{_e(meta_description)}">
  <meta name="robots" content="{robots}">
  <link rel="canonical" href="{_e(canonical)}">
  <meta property="og:title" content="{_e(name)} on OmniTrackr">
  <meta property="og:description" content="{_e(meta_description)}">
  <meta property="og:type" content="profile">
  <meta property="og:url" content="{_e(canonical)}">
  <meta property="og:image" content="{_e(card_url)}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">
  <link rel="stylesheet" href="/static/title-page.css?v={TITLE_CSS_VERSION}">
  <link rel="stylesheet" href="/static/profile-page.css?v={CSS_VERSION}">
  <script src="/static/share.js?v=20261004-share-1" defer></script>
</head>
<body class="site title-page profile-page">
  <!--SITE_NAV:-->
  <main>
    <section class="{_e(_hero_class(view))}">
      <div class="site-wrap profile-hero__inner">
        {_avatar_html(user)}
        <div class="profile-hero__copy">
          <p class="site-eyebrow">Public profile</p>
          <h1>{_e(name)}</h1>
          {_supporter_html(view)}
          <p class="profile-hero__meta">{_e(since)}</p>
          {_bio_html(profile.bio)}
          <div class="title-hero__chips">{chips}</div>
          <p class="profile-hero__actions"><button type="button" class="site-btn site-btn--ghost site-btn--sm" data-share data-share-title="{_e(name)} on OmniTrackr">Share profile</button></p>
          {owner_note}
        </div>
      </div>
    </section>
    <div class="site-wrap title-body">
      {body}
      {cta}
      <p class="title-sources">Members choose what their profile shows. Report a review or collection from its own page.</p>
    </div>
  </main>
  <!--SITE_FOOTER-->
</body>
</html>"""
    return apply_site_chrome(page)


def _profile_response(request: Request, db: Session, user: Optional[models.User], current_path: str):
    profile = public_profiles.visible_profile(db, user)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    canonical = public_profiles.profile_path(user)
    if current_path.rstrip("/") != canonical:
        return RedirectResponse(canonical, status_code=301)
    view = public_profiles.build(db, user, profile)
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    is_owner = signed_in and _viewer_id(request, db) == user.id
    response = strict_html_response(render(view, signed_in=signed_in, is_owner=is_owner))
    response.headers["Cache-Control"] = "private, no-store" if signed_in else "public, max-age=300"
    response.headers["Vary"] = "Cookie"
    if not view.indexable:
        response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


def _viewer_id(request: Request, db: Session) -> Optional[int]:
    """The signed-in viewer's account id from the session cookie, or None. Only used for the owner hint."""
    from .. import auth
    payload = auth.decode_access_token(request.cookies.get(AUTH_COOKIE_NAME) or "")
    uid = (payload or {}).get("uid")
    return uid if isinstance(uid, int) and not isinstance(uid, bool) else None


@router.get("/u/id/{user_id:int}", include_in_schema=False)
def profile_by_id(user_id: int, request: Request, db: Session = Depends(get_db)):
    return _profile_response(request, db, public_profiles.find_user_by_id(db, user_id), request.url.path)


@router.get("/u/{handle}", include_in_schema=False)
def profile_page(handle: str, request: Request, db: Session = Depends(get_db)):
    return _profile_response(request, db, public_profiles.find_user(db, handle), request.url.path)


# ---------------------------------------------------------------- share card

class _CardCache:
    """Small in-memory LRU of rendered share cards (PNG bytes)."""

    def __init__(self, size: int = 128):
        self.size = size
        self._items: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            value = self._items.get(key)
            if value is not None:
                self._items.move_to_end(key)
            return value

    def put(self, key, value):
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self.size:
                self._items.popitem(last=False)

    def clear_user(self, user_id: int):
        with self._lock:
            for key in [k for k in self._items if k[0] == user_id]:
                del self._items[key]


_CARD_CACHE = _CardCache()


def _font(size: int, bold: bool = False):
    from PIL import ImageFont
    # A system DejaVu font when the server has one; otherwise Pillow's bundled font.
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover - very old Pillow
        return ImageFont.load_default()


def _fit(draw, text: str, font, width: int) -> str:
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text.rstrip() + "…"


def render_card(view) -> bytes:
    from PIL import Image, ImageDraw
    width, height = 1200, 630
    image = Image.new("RGB", (width, height), (11, 10, 24))
    draw = ImageDraw.Draw(image)
    # Soft violet glow in the corner, drawn as concentric translucent circles.
    glow = Image.new("RGB", (width, height), (11, 10, 24))
    glow_draw = ImageDraw.Draw(glow)
    for step in range(18, 0, -1):
        radius = step * 34
        shade = (int(11 + (124 - 11) * (1 - step / 18) * 0.55), int(10 + (58 - 10) * (1 - step / 18) * 0.55),
                 int(24 + (237 - 24) * (1 - step / 18) * 0.55))
        glow_draw.ellipse((width - 160 - radius, -120 - radius, width - 160 + radius, -120 + radius), fill=shade)
    image = Image.blend(image, glow, 0.85)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, width - 40, height - 40), radius=28, outline=(60, 52, 110), width=2)

    brand = _font(30, bold=True)
    draw.text((84, 78), "OmniTrackr", font=brand, fill=(196, 181, 253))
    name_font = _font(76, bold=True)
    draw.text((84, 150), _fit(draw, view.user.username, name_font, width - 168), font=name_font, fill=(245, 243, 255))
    sub = _font(30)
    since = f"Member since {view.user.created_at:%B} {view.user.created_at.year}" if view.user.created_at else "OmniTrackr member"
    draw.text((86, 248), since, font=sub, fill=(167, 160, 199))

    y = 320
    if view.stats:
        x = 84
        number_font, label_font = _font(48, bold=True), _font(24)
        for row in view.stats[:6]:
            number = str(row["total"])
            label = row["label"]
            block = max(draw.textlength(number, font=number_font), draw.textlength(label, font=label_font)) + 48
            if x + block > width - 84:
                break
            draw.text((x, y), number, font=number_font, fill=(245, 243, 255))
            draw.text((x, y + 60), label, font=label_font, fill=(94, 234, 212))
            x += block
        y += 130
    favorite_titles = [item["title"] for item in view.favorites[:4]]
    if favorite_titles:
        fav_font = _font(28)
        draw.text((84, y), _fit(draw, "Favorites: " + " · ".join(favorite_titles), fav_font, width - 168), font=fav_font, fill=(214, 209, 240))
    elif view.profile.bio:
        bio_font = _font(28)
        draw.text((84, y), _fit(draw, " ".join(view.profile.bio.split()), bio_font, width - 168), font=bio_font, fill=(214, 209, 240))
    foot = _font(24)
    path_text = (SITE_URL.replace("https://", "").replace("http://", "") + view.path)
    draw.text((84, height - 100), _fit(draw, path_text, foot, width - 168), font=foot, fill=(167, 160, 199))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _card_response(db: Session, user: Optional[models.User]):
    profile = public_profiles.visible_profile(db, user)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    view = public_profiles.build(db, user, profile)
    fingerprint = hashlib.sha256(repr((
        user.username, user.created_at, profile.bio,
        [(r["label"], r["total"]) for r in view.stats], [f["title"] for f in view.favorites[:4]],
    )).encode("utf-8")).hexdigest()[:16]
    key = (user.id, fingerprint)
    png = _CARD_CACHE.get(key)
    if png is None:
        try:
            png = render_card(view)
        except Exception:
            raise HTTPException(status_code=404, detail="Card unavailable")
        _CARD_CACHE.put(key, png)
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600", "ETag": f'"{fingerprint}"',
                             "X-Content-Type-Options": "nosniff"})


@router.get("/u/id/{user_id:int}/card.png", include_in_schema=False)
def profile_card_by_id(user_id: int, request: Request, db: Session = Depends(get_db)):
    return _card_response(db, public_profiles.find_user_by_id(db, user_id))


@router.get("/u/{handle}/card.png", include_in_schema=False)
def profile_card(handle: str, request: Request, db: Session = Depends(get_db)):
    return _card_response(db, public_profiles.find_user(db, handle))
