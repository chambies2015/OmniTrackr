"""Embeddable profile widgets: small images of a public profile for blogs, forums and READMEs (Oct 2026).

Each widget is a PNG that links back to the member's /u/<username> page. They only
ever show what that page already shows:

- nothing at all unless the public profile is switched on,
- ``stats`` follows "Library counts" and private statistics,
- ``recent`` follows the opt-in diary (titles and dates, never notes),
- ``favorites`` shows the pinned showcase, or titles rated 8+ when "Favorites" is on,
- private categories are skipped everywhere.

Nothing new is stored. Images are drawn with Pillow from text only (no remote
artwork is fetched), and kept for a few minutes in memory.
"""
from __future__ import annotations

import hashlib
import io
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from . import diary, models, public_profiles, supporters

SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
KINDS = ("stats", "recent", "favorites")
THEMES = ("dark", "light")
SCALES = (1, 2)
ROWS = 4
CACHE_SECONDS = 600
WIDTH = 720
HEIGHTS = {"stats": 200, "recent": 280, "favorites": 280}
LABELS = {
    "stats": ("Library stats", "Library counts across movies, shows, anime, games, albums and books."),
    "recent": ("Recently finished", "The last four finishes and rewatches from the diary."),
    "favorites": ("Favorites", "The pinned showcase, or the highest rated titles."),
}
UTM = "utm_source=profile-widget"

# Category colors on the widgets (dark theme, light theme).
CATEGORY_COLORS = {
    "movies": ((244, 114, 182), (190, 24, 93)),
    "tv-shows": ((56, 189, 248), (3, 105, 161)),
    "anime": ((251, 146, 60), (194, 65, 12)),
    "video-games": ((52, 211, 153), (4, 120, 87)),
    "music": ((250, 204, 21), (161, 98, 7)),
    "books": ((167, 139, 250), (109, 40, 217)),
    "manga": ((251, 113, 133), (190, 18, 60)),
    "podcasts": ((56, 189, 248), (3, 105, 161)),
}
LABEL_TO_CATEGORY = {label: category for category, (_, label, _, _) in diary.CATEGORIES.items()}
PALETTES = {
    "dark": {"bg": (11, 10, 24), "border": (60, 52, 110), "text": (245, 243, 255), "soft": (214, 209, 240),
             "muted": (167, 160, 199), "brand": (196, 181, 253), "rating": (251, 191, 36), "track": (34, 30, 64)},
    "light": {"bg": (252, 251, 255), "border": (221, 214, 254), "text": (24, 20, 48), "soft": (55, 48, 90),
              "muted": (100, 94, 130), "brand": (109, 40, 217), "rating": (180, 83, 9), "track": (237, 233, 254)},
}


@dataclass
class WidgetData:
    user: models.User
    kind: str
    stats: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    heading: str = ""
    accent: Optional[tuple] = None


def available(db: Session, user: models.User, profile: models.PublicProfile) -> list[str]:
    """The widgets this member's profile settings allow, in display order."""
    kinds = []
    if profile.show_stats and not user.statistics_private:
        kinds.append("stats")
    if profile.show_diary:
        kinds.append("recent")
    if profile.show_favorites or public_profiles.showcase_items(db, user, limit=1):
        kinds.append("favorites")
    return kinds


def _accent(db: Session, user_id: int) -> Optional[tuple]:
    from .routers.profiles import CARD_ACCENTS
    badge = supporters.public_badge(db, user_id) or {}
    if badge.get("accent") in CARD_ACCENTS:
        return CARD_ACCENTS[badge["accent"]]
    return (234, 179, 8) if badge.get("founding") else None


def gather(db: Session, user: models.User, profile: models.PublicProfile, kind: str) -> Optional[WidgetData]:
    """What the widget shows, or None when the member's settings keep it off."""
    if kind not in KINDS or kind not in available(db, user, profile):
        return None
    data = WidgetData(user=user, kind=kind, accent=_accent(db, user.id))
    visible = public_profiles._visible_categories(user)
    if kind == "stats":
        data.stats = public_profiles._stats(db, user)
        data.heading = "Library"
    elif kind == "recent":
        data.heading = "Recently finished"
        for entry in diary.public_entries(db, user, visible, limit=ROWS):
            data.rows.append({"title": entry["title"], "label": entry["label"], "rating": entry["rating"],
                              "note": entry["visit_label"] if entry["repeat"] else f"{entry['date']:%b} {entry['date'].day}",
                              "category": LABEL_TO_CATEGORY.get(entry["label"])})
    else:
        picks = public_profiles.showcase_items(db, user, limit=ROWS)
        data.heading = "Showcase" if picks else "Favorites"
        if not picks and profile.show_favorites:
            picks = public_profiles._favorites(db, user)[:ROWS]
        for pick in picks:
            data.rows.append({"title": pick["title"], "label": pick["label"], "rating": pick["rating"],
                              "note": str(pick["year"]) if pick.get("year") else "",
                              "category": pick.get("category")})
    return data


# ---------------------------------------------------------------- drawing

def _rating(value) -> str:
    if value is None:
        return ""
    return f"{value:g}/10" if isinstance(value, float) else f"{value}/10"


def host_path(user: models.User) -> str:
    return SITE_URL.replace("https://", "").replace("http://", "") + public_profiles.profile_path(user)


def render(data: WidgetData, theme: str = "dark", scale: int = 1) -> bytes:
    from PIL import Image, ImageDraw
    from .routers.profiles import _fit, _font

    s = scale
    colors = PALETTES[theme]
    dark = theme == "dark"
    accent = data.accent or ((139, 92, 246) if dark else (124, 58, 237))
    width, height = WIDTH * s, HEIGHTS[data.kind] * s
    image = Image.new("RGB", (width, height), colors["bg"])
    # A soft glow of the member's accent color in the top right corner.
    glow = Image.new("RGB", (width, height), colors["bg"])
    glow_draw = ImageDraw.Draw(glow)
    bg = colors["bg"]
    for step in range(12, 0, -1):
        radius = step * 26 * s
        mix = (1 - step / 12) * (0.5 if dark else 0.22)
        shade = tuple(int(bg[i] + (accent[i] - bg[i]) * mix) for i in range(3))
        glow_draw.ellipse((width - 60 * s - radius, -80 * s - radius, width - 60 * s + radius, -80 * s + radius), fill=shade)
    image = Image.blend(image, glow, 0.85)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1, 1, width - 2, height - 2), radius=18 * s, outline=colors["border"], width=max(1, s))

    left, right = 28 * s, width - 28 * s
    brand_font = _font(15 * s, bold=True)
    name_font = _font(26 * s, bold=True)
    draw.text((left, 22 * s), "OMNITRACKR", font=brand_font, fill=colors["brand"])
    brand_width = draw.textlength("OMNITRACKR", font=brand_font)
    draw.text((left + brand_width + 6 * s, 22 * s), "· " + data.heading.upper(), font=brand_font, fill=colors["muted"])
    draw.text((left, 44 * s), _fit(draw, data.user.username, name_font, right - left), font=name_font, fill=colors["text"])

    if data.kind == "stats":
        _draw_stats(draw, data, colors, s, left, right, dark)
    else:
        _draw_rows(draw, data, colors, s, left, right, dark)

    foot_font = _font(13 * s)
    foot_y = height - 30 * s
    draw.text((left, foot_y), _fit(draw, host_path(data.user), foot_font, (right - left) * 2 // 3), font=foot_font,
              fill=colors["muted"])
    cta = "Track yours free →"
    draw.text((right - draw.textlength(cta, font=foot_font), foot_y), cta, font=foot_font, fill=colors["brand"])

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _draw_stats(draw, data, colors, s, left, right, dark):
    from .routers.profiles import _font
    if not data.stats:
        draw.text((left, 96 * s), "Nothing tracked yet.", font=_font(17 * s), fill=colors["soft"])
        return
    total = sum(row["total"] for row in data.stats)
    finished = sum(row["finished"] for row in data.stats)
    summary_font = _font(14 * s)
    summary = f"{total:,} tracked · {finished:,} finished"
    draw.text((right - draw.textlength(summary, font=summary_font), 54 * s), summary, font=summary_font,
              fill=colors["muted"])
    number_font, label_font = _font(24 * s, bold=True), _font(13 * s)
    x, y = left, 92 * s
    for row in data.stats:
        number = f"{row['total']:,}"
        block = max(draw.textlength(number, font=number_font), draw.textlength(row["label"], font=label_font)) + 26 * s
        if x + block > right + 26 * s:
            break
        color = CATEGORY_COLORS.get(row["category"], ((94, 234, 212), (15, 118, 110)))[0 if dark else 1]
        draw.text((x, y), number, font=number_font, fill=colors["text"])
        draw.text((x, y + 30 * s), row["label"], font=label_font, fill=color)
        x += block
    # The mix of the library as one bar.
    bar_y, bar_h = 146 * s, 6 * s
    draw.rounded_rectangle((left, bar_y, right, bar_y + bar_h), radius=bar_h // 2, fill=colors["track"])
    x = left
    for index, row in enumerate(data.stats):
        span = (right - left) * row["total"] / total
        end = right if index == len(data.stats) - 1 else x + span
        color = CATEGORY_COLORS.get(row["category"], ((94, 234, 212), (15, 118, 110)))[0 if dark else 1]
        if end - x >= 1:
            draw.rectangle((x, bar_y, end, bar_y + bar_h), fill=color)
        x = end


def _draw_rows(draw, data, colors, s, left, right, dark):
    from .routers.profiles import _fit, _font
    if not data.rows:
        empty = "No finishes in the diary yet." if data.kind == "recent" else "No favorites picked yet."
        draw.text((left, 100 * s), empty, font=_font(17 * s), fill=colors["soft"])
        return
    title_font, meta_font, rating_font = _font(17 * s, bold=True), _font(13 * s), _font(15 * s, bold=True)
    y = 90 * s
    for row in data.rows[:ROWS]:
        color = CATEGORY_COLORS.get(row.get("category"), ((94, 234, 212), (15, 118, 110)))[0 if dark else 1]
        draw.rounded_rectangle((left, y + 3 * s, left + 4 * s, y + 31 * s), radius=2 * s, fill=color)
        rating = _rating(row.get("rating"))
        rating_width = draw.textlength(rating, font=rating_font) if rating else 0
        meta = " · ".join(bit for bit in (row["label"], row.get("note")) if bit)
        meta_width = min(draw.textlength(meta, font=meta_font), 190 * s)
        title_room = right - left - 16 * s - rating_width - meta_width - 36 * s
        draw.text((left + 16 * s, y + 6 * s), _fit(draw, row["title"], title_font, title_room), font=title_font,
                  fill=colors["text"])
        meta_x = right - rating_width - (16 * s if rating else 0) - meta_width
        draw.text((meta_x, y + 9 * s), _fit(draw, meta, meta_font, meta_width), font=meta_font, fill=colors["muted"])
        if rating:
            draw.text((right - rating_width, y + 7 * s), rating, font=rating_font, fill=colors["rating"])
        y += 36 * s


# ---------------------------------------------------------------- cache

class _Cache:
    """A small in-memory LRU of rendered widgets that expire after a few minutes."""

    def __init__(self, size: int = 256, seconds: int = CACHE_SECONDS):
        self.size, self.seconds = size, seconds
        self._items: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            found = self._items.get(key)
            if found is None:
                return None
            if time.monotonic() - found[0] > self.seconds:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return found[1]

    def put(self, key, value):
        with self._lock:
            self._items[key] = (time.monotonic(), value)
            self._items.move_to_end(key)
            while len(self._items) > self.size:
                self._items.popitem(last=False)

    def clear_user(self, user_id: int):
        with self._lock:
            for key in [k for k in self._items if k[0] == user_id]:
                del self._items[key]


CACHE = _Cache()


def privacy_key(user: models.User, profile: models.PublicProfile) -> tuple:
    """Everything that decides what a widget may show, so a change to any of it skips the cache."""
    flags = tuple(bool(getattr(user, flag, False)) for _, flag, _, _ in public_profiles.CATEGORIES.values())
    return (user.username, bool(user.statistics_private), flags, profile.show_stats, profile.show_favorites,
            profile.show_diary, profile.updated_at)


def image(db: Session, user: models.User, profile: models.PublicProfile, kind: str, theme: str,
          scale: int) -> Optional[tuple[bytes, str]]:
    """(PNG bytes, ETag) for the widget, or None when the member's settings keep it off."""
    key = (user.id, kind, theme, scale, privacy_key(user, profile))
    cached = CACHE.get(key)
    if cached is not None:
        return cached
    data = gather(db, user, profile, kind)
    if data is None:
        return None
    png = render(data, theme, scale)
    result = (png, hashlib.sha256(png).hexdigest()[:16])
    CACHE.put(key, result)
    return result


# ---------------------------------------------------------------- embed snippets

def image_url(user: models.User, kind: str, theme: str = "dark", scale: int = 1) -> str:
    query = []
    if theme != "dark":
        query.append(f"theme={theme}")
    if scale != 1:
        query.append(f"scale={scale}")
    return f"{SITE_URL}{public_profiles.profile_path(user)}/widget/{kind}.png" + ("?" + "&".join(query) if query else "")


def link_url(user: models.User) -> str:
    return f"{SITE_URL}{public_profiles.profile_path(user)}?{UTM}"


def snippets(user: models.User, kind: str, theme: str = "dark") -> dict:
    """Copy-and-paste embed code for each place a member might put the widget."""
    from html import escape
    alt = f"{user.username}'s {LABELS[kind][0].lower()} on OmniTrackr"
    link, small, sharp = link_url(user), image_url(user, kind, theme), image_url(user, kind, theme, 2)
    height = HEIGHTS[kind]
    return {
        "html": (f'<a href="{escape(link)}"><img src="{escape(sharp)}" alt="{escape(alt)}" '
                 f'width="{WIDTH}" height="{height}" style="max-width:100%;height:auto"></a>'),
        "markdown": f"[![{alt}]({small})]({link})",
        "bbcode": f"[url={link}][img]{small}[/img][/url]",
        "image": small,
    }
