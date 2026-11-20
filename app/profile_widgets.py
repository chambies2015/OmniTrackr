"""Embeddable profile widgets: small images of a public profile for blogs, forums and READMEs.

October 2026 added three PNG widgets (stats, recent, favorites). November 2026 added
"Right now", a forum signature banner and a one-line badge, an SVG copy of every widget
(sharp at any size, with an "auto" theme that follows the reader's light or dark mode),
and a rough count of where each member's widgets get loaded.

Each widget links back to the member's /u/<username> page and only ever shows what that
page already shows:

- nothing at all unless the public profile is switched on,
- ``stats`` (and the counts on the signature and badge) follow "Library counts" and
  private statistics,
- ``recent`` follows the opt-in diary (titles and dates, never notes),
- ``favorites`` shows the pinned showcase, or titles rated 8+ when "Favorites" is on,
- ``now`` follows the opt-in "Right now" shelf (what was started, never how far along),
- private categories are skipped everywhere.

Images are laid out once as a list of shapes and text (``Scene``) and then drawn either
with Pillow (PNG) or as SVG markup, so both files look the same. No remote artwork is
fetched. Rendered files are kept for a few minutes in memory.
"""
from __future__ import annotations

import base64
import hashlib
import io
import os
import re
import threading
import time
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from html import escape
from typing import Optional
from urllib.parse import urlsplit

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import diary, models, public_profiles, supporters

SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
KINDS = ("stats", "recent", "favorites", "now", "signature", "badge")
FORMATS = ("png", "svg")
THEMES = ("dark", "light")            # PNG themes
SVG_THEMES = ("dark", "light", "auto")  # "auto" follows the reader's light or dark mode, so it needs SVG
SCALES = (1, 2)
ROWS = 4
CACHE_SECONDS = 600
WIDTH = 720
WIDTHS = {"stats": WIDTH, "recent": WIDTH, "favorites": WIDTH, "now": WIDTH, "signature": 540}
HEIGHTS = {"stats": 200, "recent": 280, "favorites": 280, "now": 280, "signature": 136, "badge": 20}
LABELS = {
    "stats": ("Library stats", "Library counts across movies, shows, anime, games, albums and books."),
    "recent": ("Recently finished", "The last four finishes and rewatches from the diary."),
    "favorites": ("Favorites", "The pinned showcase, or the highest rated titles."),
    "now": ("Right now", "Titles started from the Up next queue, then what's queued after them."),
    "signature": ("Forum signature", "A 540 by 136 banner that fits most forum signature limits."),
    "badge": ("Small badge", "One line for a README, a link list or the end of a post."),
}
ALT = {
    "stats": "{name}'s library stats on OmniTrackr",
    "recent": "{name}'s recently finished on OmniTrackr",
    "favorites": "{name}'s favorites on OmniTrackr",
    "now": "What {name} is into right now on OmniTrackr",
    "signature": "{name} on OmniTrackr",
    "badge": "{name} on OmniTrackr",
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
    "audiobooks": ((163, 230, 53), (77, 124, 15)),
}
OTHER_COLOR = ((94, 234, 212), (15, 118, 110))
LABEL_TO_CATEGORY = {label: category for category, (_, label, _, _) in diary.CATEGORIES.items()}
PALETTES = {
    "dark": {"bg": (11, 10, 24), "border": (60, 52, 110), "text": (245, 243, 255), "soft": (214, 209, 240),
             "muted": (167, 160, 199), "brand": (196, 181, 253), "rating": (251, 191, 36), "track": (34, 30, 64),
             "badge-left": (40, 34, 74), "badge-right": (124, 58, 237), "badge-text": (255, 255, 255),
             "badge-label": (233, 228, 255), "avatar": (38, 30, 84), "avatar-text": (196, 181, 253)},
    "light": {"bg": (252, 251, 255), "border": (221, 214, 254), "text": (24, 20, 48), "soft": (55, 48, 90),
              "muted": (100, 94, 130), "brand": (109, 40, 217), "rating": (180, 83, 9), "track": (237, 233, 254),
              "badge-left": (237, 233, 254), "badge-right": (109, 40, 217), "badge-text": (255, 255, 255),
              "badge-label": (49, 38, 110), "avatar": (237, 233, 254), "avatar-text": (109, 40, 217)},
}
DEFAULT_ACCENT = ((139, 92, 246), (124, 58, 237))
FONT_STACK = "'DejaVu Sans',Verdana,Geneva,'Segoe UI',sans-serif"
# XML 1.0 can't carry these, and bidi overrides could flip a title around in the image.
_UNSAFE_TEXT = re.compile("[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f​-‏‪-‮⁦-⁩￾￿]")


@dataclass
class WidgetData:
    user: models.User
    kind: str
    stats: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    heading: str = ""
    accent: Optional[tuple] = None
    message: str = ""
    picture: Optional[bytes] = None


def _stats_allowed(user: models.User, profile: models.PublicProfile) -> bool:
    return bool(profile.show_stats and not user.statistics_private)


def available(db: Session, user: models.User, profile: models.PublicProfile) -> list[str]:
    """The widgets this member's profile settings allow, in display order.

    The signature and the badge always work on a public profile: with nothing else
    shared they still show the member's name, which the profile itself shows.
    """
    kinds = []
    if _stats_allowed(user, profile):
        kinds.append("stats")
    if profile.show_diary:
        kinds.append("recent")
    if profile.show_favorites or public_profiles.showcase_items(db, user, limit=1):
        kinds.append("favorites")
    if getattr(profile, "show_now", False):
        kinds.append("now")
    kinds += ["signature", "badge"]
    return kinds


def _accent(db: Session, user_id: int) -> Optional[tuple]:
    from .routers.profiles import CARD_ACCENTS
    badge = supporters.public_badge(db, user_id) or {}
    if badge.get("accent") in CARD_ACCENTS:
        return CARD_ACCENTS[badge["accent"]]
    return (234, 179, 8) if badge.get("founding") else None


def _short_date(value) -> str:
    return f"{value:%b} {value.day}" if value else ""


def _now_rows(db: Session, user: models.User) -> list[dict]:
    shelf = public_profiles._now(db, user)
    rows = []
    for item in shelf.get("current") or []:
        since = f"since {_short_date(item['since'])}" if item.get("since") else ""
        rows.append({"title": item["title"], "label": f"{item['verb']} · {item['label']}", "note": since,
                     "rating": None, "category": item["category"], "tag": item["verb"], "started": True})
    for item in shelf.get("queued") or []:
        rows.append({"title": item["title"], "label": f"Up next · {item['label']}", "note": "", "rating": None,
                     "category": item["category"], "tag": "Up next", "started": False})
    return rows


def _diary_rows(db: Session, user: models.User, visible: list[str], limit: int) -> list[dict]:
    rows = []
    for entry in diary.public_entries(db, user, visible, limit=limit):
        rows.append({"title": entry["title"], "label": entry["label"], "rating": entry["rating"],
                     "note": entry["visit_label"] if entry["repeat"] else _short_date(entry["date"]),
                     "category": LABEL_TO_CATEGORY.get(entry["label"]), "tag": entry["visit_label"]})
    return rows


def _favorite_rows(db: Session, user: models.User, profile: models.PublicProfile, limit: int) -> tuple[str, list]:
    picks = public_profiles.showcase_items(db, user, limit=limit)
    heading = "Showcase" if picks else "Favorites"
    if not picks and profile.show_favorites:
        picks = public_profiles._favorites(db, user)[:limit]
    rows = [{"title": pick["title"], "label": pick["label"], "rating": pick["rating"],
             "note": str(pick["year"]) if pick.get("year") else "", "category": pick.get("category"),
             "tag": "Pinned" if heading == "Showcase" else "Favorite"} for pick in picks]
    return heading, rows


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
        data.rows = _diary_rows(db, user, visible, ROWS)
    elif kind == "favorites":
        data.heading, data.rows = _favorite_rows(db, user, profile, ROWS)
    elif kind == "now":
        data.heading = "Right now"
        data.rows = _now_rows(db, user)[:ROWS]
    elif kind == "signature":
        data.heading = "Signature"
        data.picture = user.profile_picture_data
        if _stats_allowed(user, profile):
            data.stats = public_profiles._stats(db, user)
        # Two lines: what they're on now, then the latest finish, then what's next, then a favorite.
        now = _now_rows(db, user) if getattr(profile, "show_now", False) else []
        lines = [row for row in now if row["started"]][:2]
        if len(lines) < 2 and profile.show_diary:
            lines += _diary_rows(db, user, visible, 1)
        if len(lines) < 2:
            lines += [row for row in now if not row["started"]][:2 - len(lines)]
        if len(lines) < 2 and (profile.show_favorites or public_profiles.showcase_items(db, user, limit=1)):
            lines += _favorite_rows(db, user, profile, 2 - len(lines))[1]
        data.rows = lines[:2]
    else:  # badge
        data.heading = "Badge"
        total = sum(row["total"] for row in public_profiles._stats(db, user)) if _stats_allowed(user, profile) else 0
        data.message = f"{total:,} tracked" if total else (user.username or "member")
    return data


# ---------------------------------------------------------------- text measuring

_FONTS = threading.local()


def _font(size: int, bold: bool = False):
    """A loaded font, kept per thread: a FreeType face shouldn't be used by two threads at once."""
    fonts = getattr(_FONTS, "fonts", None)
    if fonts is None:
        fonts = _FONTS.fonts = {}
    font = fonts.get((size, bold))
    if font is None:
        from .routers.profiles import _font as load_font
        if len(fonts) > 96:
            fonts.clear()
        font = fonts[(size, bold)] = load_font(size, bold=bold)
    return font


def _measure(text: str, size: int, bold: bool = False) -> float:
    try:
        return float(_font(size, bold).getlength(text))
    except Exception:  # A font without getlength (very old Pillow): guess from the size.
        return len(text) * size * 0.6


def _ascent(size: int, bold: bool = False) -> float:
    try:
        return float(_font(size, bold).getmetrics()[0])
    except Exception:
        return size * 0.93


def clean_text(value) -> str:
    return " ".join(_UNSAFE_TEXT.sub("", str(value or "")).split())


def _fit(text: str, size: int, width: float, bold: bool = False) -> str:
    text = clean_text(text)
    if _measure(text, size, bold) <= width:
        return text
    # The longest start of the text that still fits with an ellipsis after it.
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if _measure(text[:middle] + "…", size, bold) <= width:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip() + "…"


def _rating(value) -> str:
    if value is None:
        return ""
    return f"{value:g}/10" if isinstance(value, float) else f"{value}/10"


def host_path(user: models.User) -> str:
    return SITE_URL.replace("https://", "").replace("http://", "") + public_profiles.profile_path(user)


# ---------------------------------------------------------------- layout

@dataclass
class Scene:
    """A widget laid out in CSS pixels. Colors are names, resolved per theme when drawn."""
    width: int
    height: int
    accent: tuple                      # (dark rgb, light rgb)
    ops: list = field(default_factory=list)
    glow: Optional[tuple] = None       # (center x, center y, radius)
    frame: int = 0                     # corner radius of the outline; 0 for none
    title: str = ""

    def rect(self, x, y, w, h, fill, radius=0):
        self.ops.append(("rect", float(x), float(y), float(w), float(h), radius, fill))

    def text(self, x, y, text, size, color, bold=False, anchor="start", limit=None, exact=False):
        """Text with its top-left (or top-right, for anchor="end") corner at x, y.

        ``limit`` is the room it has: longer text is cut with an ellipsis, and an SVG
        reader with a wider font squeezes it to fit. ``exact`` always pins the width.
        """
        text = _fit(text, size, limit, bold) if limit else clean_text(text)
        if not text:
            return 0.0
        width = _measure(text, size, bold)
        pin = exact or bool(limit and width > limit * 0.9)
        self.ops.append(("text", float(x), float(y), text, size, color, bold, anchor, width if pin else None))
        return width

    def avatar(self, x, y, size, picture, initial):
        self.ops.append(("avatar", float(x), float(y), size, picture, initial))


def _category(row) -> str:
    return f"cat:{row.get('category')}" if row.get("category") in CATEGORY_COLORS else "cat:other"


def layout(data: WidgetData) -> Scene:
    accent = (data.accent, data.accent) if data.accent else DEFAULT_ACCENT
    if data.kind == "badge":
        return _layout_badge(data, accent)
    if data.kind == "signature":
        return _layout_signature(data, accent)
    width, height = WIDTHS[data.kind], HEIGHTS[data.kind]
    scene = Scene(width, height, accent, glow=(width - 60, -80, 312), frame=18,
                  title=ALT[data.kind].format(name=clean_text(data.user.username)))
    left, right = 28, width - 28
    brand = scene.text(left, 22, "OMNITRACKR", 15, "brand", bold=True)
    scene.text(left + brand + 6, 22, "· " + data.heading.upper(), 15, "muted", bold=True)
    scene.text(left, 44, data.user.username, 26, "text", bold=True, limit=right - left)
    if data.kind == "stats":
        _layout_stats(scene, data, left, right)
    else:
        _layout_rows(scene, data, left, right)
    foot_y = height - 30
    scene.text(left, foot_y, host_path(data.user), 13, "muted", limit=(right - left) * 2 // 3)
    scene.text(right, foot_y, "Track yours free →", 13, "brand", anchor="end")
    return scene


def _layout_stats(scene: Scene, data: WidgetData, left: int, right: int):
    if not data.stats:
        scene.text(left, 96, "Nothing tracked yet.", 17, "soft")
        return
    total = sum(row["total"] for row in data.stats)
    finished = sum(row["finished"] for row in data.stats)
    scene.text(right, 54, f"{total:,} tracked · {finished:,} finished", 14, "muted", anchor="end")
    x, y = left, 92
    for row in data.stats:
        number = f"{row['total']:,}"
        block = max(_measure(number, 24, True), _measure(row["label"], 13)) + 26
        if x + block > right + 26:
            break
        scene.text(x, y, number, 24, "text", bold=True)
        scene.text(x, y + 30, row["label"], 13, _category(row))
        x += block
    # The mix of the library as one bar.
    bar_y, bar_h = 146, 6
    scene.rect(left, bar_y, right - left, bar_h, "track", radius=bar_h // 2)
    x = left
    for index, row in enumerate(data.stats):
        span = (right - left) * row["total"] / total
        end = right if index == len(data.stats) - 1 else x + span
        if end - x >= 1:
            scene.rect(x, bar_y, end - x, bar_h, _category(row))
        x = end


EMPTY_ROWS = {"recent": "No finishes in the diary yet.", "favorites": "No favorites picked yet.",
              "now": "Nothing started from Up next yet."}


def _layout_rows(scene: Scene, data: WidgetData, left: int, right: int):
    if not data.rows:
        scene.text(left, 100, EMPTY_ROWS.get(data.kind, ""), 17, "soft")
        return
    y = 90
    for row in data.rows[:ROWS]:
        scene.rect(left, y + 3, 4, 28, _category(row), radius=2)
        rating = _rating(row.get("rating"))
        rating_width = _measure(rating, 15, True) if rating else 0
        meta = " · ".join(bit for bit in (row["label"], row.get("note")) if bit)
        meta_width = min(_measure(meta, 13), 230 if data.kind == "now" else 190)
        title_room = right - left - 16 - rating_width - meta_width - 36
        scene.text(left + 16, y + 6, row["title"], 17, "text", bold=True, limit=title_room)
        meta_right = right - rating_width - (16 if rating else 0)
        scene.text(meta_right, y + 9, meta, 13, "muted", anchor="end", limit=meta_width)
        if rating:
            scene.text(right, y + 7, rating, 15, "rating", bold=True, anchor="end")
        y += 36


def _layout_signature(data: WidgetData, accent) -> Scene:
    width, height = WIDTHS["signature"], HEIGHTS["signature"]
    scene = Scene(width, height, accent, glow=(width - 40, -60, 220), frame=14,
                  title=ALT["signature"].format(name=clean_text(data.user.username)))
    pad = 18
    scene.avatar(pad, 20, 60, data.picture, (data.user.username or "?")[:1].upper())
    left, right = pad + 60 + 16, width - pad
    scene.text(left, 14, "OMNITRACKR", 10, "brand", bold=True)
    summary = ""
    if data.stats:
        total = sum(row["total"] for row in data.stats)
        summary = f"{total:,} tracked"
    summary_width = scene.text(right, 14, summary, 11, "muted", bold=True, anchor="end") if summary else 0
    scene.text(left, 27, data.user.username, 20, "text", bold=True,
               limit=right - left - summary_width - (12 if summary else 0))
    y = 60
    if data.rows:
        for row in data.rows[:2]:
            tag = clean_text(row.get("tag") or row.get("label") or "")
            tag_width = scene.text(left, y + 3, tag, 11, _category(row), bold=True, limit=110)
            scene.text(left + tag_width + 8, y, row["title"], 15, "text", bold=True,
                       limit=right - left - tag_width - 8)
            y += 23
    elif data.stats:
        # Nothing to name: the biggest shelves instead.
        shelves = sorted(data.stats, key=lambda row: -row["total"])[:3]
        scene.text(left, y, " · ".join(f"{row['total']:,} {row['label'].lower()}" for row in shelves), 14,
                   "soft", limit=right - left)
    else:
        scene.text(left, y, "Movies, shows, anime, games, books and more.", 14, "soft", limit=right - left)
    foot_y = height - 24
    scene.text(left, foot_y, host_path(data.user), 11, "muted", limit=(right - left) * 3 // 5)
    scene.text(right, foot_y, "Track yours free →", 11, "brand", bold=True, anchor="end")
    return scene


def _layout_badge(data: WidgetData, accent) -> Scene:
    size, pad, height = 11, 7, HEIGHTS["badge"]
    label, message = "OmniTrackr", _fit(data.message, size, 220)
    label_width = _measure(label, size) + pad * 2
    message_width = _measure(message, size) + pad * 2
    width = int(round(label_width + message_width))
    scene = Scene(width, height, accent, title=ALT["badge"].format(name=clean_text(data.user.username)))
    scene.rect(0, 0, width, height, "badge-right", radius=3)
    scene.rect(0, 0, label_width, height, "badge-left", radius=3)
    scene.rect(label_width - 3, 0, 3, height, "badge-left")
    top = (height - size * 1.18) / 2
    scene.text(pad, top, label, size, "badge-label", exact=True)
    scene.text(label_width + pad, top, message, size, "badge-text", exact=True)
    return scene


# ---------------------------------------------------------------- drawing

def _color(scene: Scene, name: str, theme: str) -> tuple:
    dark = theme == "dark"
    if name == "accent":
        return scene.accent[0 if dark else 1]
    if name.startswith("cat:"):
        return CATEGORY_COLORS.get(name[4:], OTHER_COLOR)[0 if dark else 1]
    return PALETTES[theme][name]


def _glow_strength(theme: str) -> float:
    # The PNG glow: twelve rings, each blended 85%, from nothing at the edge to 11/12 of this in the middle.
    return 0.5 if theme == "dark" else 0.22


def _avatar_tile(picture: Optional[bytes], size: int):
    from PIL import Image, ImageOps
    if not picture:
        return None
    try:
        with Image.open(io.BytesIO(picture)) as source:
            return ImageOps.fit(source.convert("RGB"), (size, size))
    except Exception:
        return None


def to_png(scene: Scene, theme: str = "dark", scale: int = 1) -> bytes:
    from PIL import Image, ImageDraw

    s = scale
    bg = _color(scene, "bg", theme)
    width, height = scene.width * s, scene.height * s
    image = Image.new("RGB", (width, height), bg)
    if scene.glow:
        # A soft glow of the member's accent color in the top right corner.
        accent = _color(scene, "accent", theme)
        cx, cy, radius = scene.glow
        glow = Image.new("RGB", (width, height), bg)
        glow_draw = ImageDraw.Draw(glow)
        steps = 12
        for step in range(steps, 0, -1):
            r = step * radius / steps * s
            mix = (1 - step / steps) * _glow_strength(theme)
            shade = tuple(int(bg[i] + (accent[i] - bg[i]) * mix) for i in range(3))
            glow_draw.ellipse((cx * s - r, cy * s - r, cx * s + r, cy * s + r), fill=shade)
        image = Image.blend(image, glow, 0.85)
    draw = ImageDraw.Draw(image)
    if scene.frame:
        draw.rounded_rectangle((1, 1, width - 2, height - 2), radius=scene.frame * s,
                               outline=_color(scene, "border", theme), width=max(1, s))
    for op in scene.ops:
        if op[0] == "rect":
            _, x, y, w, h, radius, fill = op
            box = (x * s, y * s, (x + w) * s - 1, (y + h) * s - 1)
            if radius:
                draw.rounded_rectangle(box, radius=radius * s, fill=_color(scene, fill, theme))
            else:
                draw.rectangle(box, fill=_color(scene, fill, theme))
        elif op[0] == "text":
            _, x, y, text, size, color, bold, anchor, _pinned = op
            font = _font(int(round(size * s)), bold)
            left = x * s - (draw.textlength(text, font=font) if anchor == "end" else 0)
            draw.text((left, y * s), text, font=font, fill=_color(scene, color, theme))
        elif op[0] == "avatar":
            _, x, y, size, picture, initial = op
            box = int(size * s)
            tile = _avatar_tile(picture, box)
            mask = Image.new("L", (box, box), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, box - 1, box - 1), fill=255)
            if tile is None:
                tile = Image.new("RGB", (box, box), _color(scene, "avatar", theme))
                tile_draw = ImageDraw.Draw(tile)
                font = _font(int(size * 0.5 * s), True)
                bounds = tile_draw.textbbox((0, 0), initial, font=font)
                tile_draw.text(((box - (bounds[2] - bounds[0])) / 2 - bounds[0], (box - (bounds[3] - bounds[1])) / 2 - bounds[1]),
                               initial, font=font, fill=_color(scene, "avatar-text", theme))
            image.paste(tile, (int(x * s), int(y * s)), mask)
            draw = ImageDraw.Draw(image)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _hex(rgb: tuple) -> str:
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb)


def _n(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def to_svg(scene: Scene, theme: str = "dark") -> bytes:
    """The scene as a standalone SVG. Colors are classes, so "auto" can switch them for light mode."""
    themes = ("dark", "light") if theme == "auto" else (theme,)
    used: set[str] = set()
    body: list[str] = []
    defs: list[str] = []
    w, h = scene.width, scene.height

    def fill(name: str) -> str:
        used.add(name)
        return "c-" + re.sub(r"[^a-z0-9-]", "-", name)

    if scene.frame:
        defs.append(f'<clipPath id="frame"><rect width="{w}" height="{h}" rx="{scene.frame}"/></clipPath>')
        body.append(f'<g clip-path="url(#frame)"><rect class="{fill("bg")}" width="{w}" height="{h}"/>')
    if scene.glow:
        cx, cy, radius = scene.glow
        for name in themes:
            strength = 11 / 12 * _glow_strength(name) * 0.85
            color = _hex(_color(scene, "accent", name))
            defs.append(f'<radialGradient id="glow-{name}" cx="{cx}" cy="{cy}" r="{radius}" gradientUnits="userSpaceOnUse">'
                        f'<stop offset="0" stop-color="{color}" stop-opacity="{strength:.3f}"/>'
                        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient>')
        body.append(f'<rect class="glow" width="{w}" height="{h}"/>')
    for op in scene.ops:
        if op[0] == "rect":
            _, x, y, rw, rh, radius, color = op
            corner = f' rx="{_n(radius)}"' if radius else ""
            body.append(f'<rect class="{fill(color)}" x="{_n(x)}" y="{_n(y)}" width="{_n(rw)}" height="{_n(rh)}"{corner}/>')
        elif op[0] == "text":
            _, x, y, text, size, color, bold, anchor, pinned = op
            classes = fill(color) + (" b" if bold else "")
            extra = ' text-anchor="end"' if anchor == "end" else ""
            if pinned:
                extra += f' textLength="{_n(pinned)}" lengthAdjust="spacingAndGlyphs"'
            body.append(f'<text class="{classes}" x="{_n(x)}" y="{_n(y + _ascent(size, bold))}" '
                        f'font-size="{size}"{extra}>{escape(text, quote=False)}</text>')
        elif op[0] == "avatar":
            _, x, y, size, picture, initial = op
            tile = _avatar_tile(picture, size * 2)
            half = size / 2
            defs.append(f'<clipPath id="avatar"><circle cx="{_n(x + half)}" cy="{_n(y + half)}" r="{_n(half)}"/></clipPath>')
            if tile is not None:
                buffer = io.BytesIO()
                tile.save(buffer, format="JPEG", quality=82)
                data = base64.b64encode(buffer.getvalue()).decode("ascii")
                body.append(f'<image x="{_n(x)}" y="{_n(y)}" width="{size}" height="{size}" clip-path="url(#avatar)" '
                            f'href="data:image/jpeg;base64,{data}"/>')
            else:
                text_size = int(size * 0.5)
                body.append(f'<circle class="{fill("avatar")}" cx="{_n(x + half)}" cy="{_n(y + half)}" r="{_n(half)}"/>')
                body.append(f'<text class="{fill("avatar-text")} b" x="{_n(x + half)}" y="{_n(y + half + text_size * 0.36)}" '
                            f'font-size="{text_size}" text-anchor="middle">{escape(clean_text(initial), quote=False)}</text>')
    if scene.frame:
        body.append("</g>")
        body.append(f'<rect class="line" x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{scene.frame - .5}"/>')

    def rules(name: str) -> str:
        parts = [f".{fill(color)}{{fill:{_hex(_color(scene, color, name))}}}" for color in sorted(used)]
        if scene.glow:
            parts.append(f".glow{{fill:url(#glow-{name})}}")
        if scene.frame:
            parts.append(f".line{{fill:none;stroke:{_hex(_color(scene, 'border', name))}}}")
        return "".join(parts)

    css = f"text{{font-family:{FONT_STACK}}}.b{{font-weight:700}}" + rules(themes[0])
    if theme == "auto":
        css += f"@media (prefers-color-scheme:light){{{rules('light')}}}"
    title = escape(clean_text(scene.title), quote=False)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
           f'aria-labelledby="t"><title id="t">{title}</title><style>{css}</style>'
           f'<defs>{"".join(defs)}</defs>{"".join(body)}</svg>')
    return svg.encode("utf-8")


def render(data: WidgetData, theme: str = "dark", scale: int = 1) -> bytes:
    """The widget as PNG bytes (kept for callers from before the SVG copy existed)."""
    return to_png(layout(data), theme if theme in THEMES else "dark", scale)


# ---------------------------------------------------------------- cache

class _Cache:
    """A small in-memory LRU of rendered widgets that expire after a few minutes."""

    def __init__(self, size: int = 512, seconds: int = CACHE_SECONDS):
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
            profile.show_diary, bool(getattr(profile, "show_now", False)), profile.updated_at)


def image(db: Session, user: models.User, profile: models.PublicProfile, kind: str, theme: str,
          scale: int, fmt: str = "png") -> Optional[tuple[bytes, str]]:
    """(file bytes, ETag) for the widget, or None when the member's settings keep it off."""
    fmt = fmt if fmt in FORMATS else "png"
    if fmt == "svg":
        theme, scale = (theme if theme in SVG_THEMES else "dark"), 1
    else:
        theme = theme if theme in THEMES else "dark"
    key = (user.id, kind, fmt, theme, scale, privacy_key(user, profile))
    cached = CACHE.get(key)
    if cached is not None:
        return cached
    data = gather(db, user, profile, kind)
    if data is None:
        return None
    scene = layout(data)
    body = to_svg(scene, theme) if fmt == "svg" else to_png(scene, theme, scale)
    result = (body, hashlib.sha256(body).hexdigest()[:16])
    CACHE.put(key, result)
    return result


# ---------------------------------------------------------------- embed snippets

def image_url(user: models.User, kind: str, theme: str = "dark", scale: int = 1, fmt: str = "png") -> str:
    query = []
    if theme != "dark":
        query.append(f"theme={theme}")
    if scale != 1 and fmt == "png":
        query.append(f"scale={scale}")
    return (f"{SITE_URL}{public_profiles.profile_path(user)}/widget/{kind}.{fmt}"
            + ("?" + "&".join(query) if query else ""))


def link_url(user: models.User) -> str:
    return f"{SITE_URL}{public_profiles.profile_path(user)}?{UTM}"


SNIPPET_FORMATS = ("html", "markdown", "bbcode", "anilist", "image")


def snippets(user: models.User, kind: str, theme: str = "dark", fmt: str = "png") -> dict:
    """Copy-and-paste embed code for each place a member might put the widget."""
    if fmt == "png" and theme not in THEMES:
        theme = "dark"
    alt = ALT[kind].format(name=clean_text(user.username))
    link = link_url(user)
    small = image_url(user, kind, theme, 1, fmt)
    sharp = image_url(user, kind, theme, 2, fmt)  # The same address as ``small`` for SVG.
    if kind == "badge":
        size = f'height="{HEIGHTS[kind]}"'
        anilist = f"[ img({small}) ]({link})"
    else:
        size = f'width="{WIDTHS[kind]}" height="{HEIGHTS[kind]}"'
        anilist = f"[ img{WIDTHS[kind]}({sharp}) ]({link})"
    return {
        "html": (f'<a href="{escape(link)}"><img src="{escape(sharp)}" alt="{escape(alt)}" '
                 f'{size} style="max-width:100%;height:auto"></a>'),
        "markdown": f"[![{alt}]({small})]({link})",
        "bbcode": f"[url={link}][img]{small}[/img][/url]",
        "anilist": anilist,
        "image": small,
    }


def variants(user: models.User, kind: str) -> dict:
    """Every theme and file pairing the embed page offers, as {"dark-png": {...}, ...}."""
    found = {}
    for fmt in FORMATS:
        for theme in (THEMES if fmt == "png" else SVG_THEMES):
            codes = snippets(user, kind, theme, fmt)
            codes["preview"] = image_url(user, kind, theme, 2, fmt).removeprefix(SITE_URL)
            found[f"{theme}-{fmt}"] = codes
    return found


# ---------------------------------------------------------------- where widgets get loaded

# Image proxies that fetch on behalf of a page and send no referrer: named by user agent.
PROXY_AGENTS = (
    ("github-camo", "github.com"), ("discordbot", "discord.com"), ("slackbot", "slack.com"),
    ("telegrambot", "telegram.org"), ("twitterbot", "x.com"), ("bluesky", "bsky.app"),
    ("whatsapp", "whatsapp.com"), ("redditbot", "reddit.com"), ("googleimageproxy", "gmail.com"),
    ("yahoomailproxy", "yahoo.com"), ("mastodon", "mastodon"),
)
HOST_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,62}\.)*[a-z0-9-]{1,63}")
HOSTS_PER_MEMBER_DAY = 12
OTHER_HOST = "other"
LOAD_KINDS = KINDS


def embed_host(request) -> Optional[str]:
    """Where a widget image is being shown.

    A site's host name, a known image proxy, "" when the request names nothing, or None
    for loads that aren't someone seeing the widget (OmniTrackr's own preview, crawlers).
    """
    from .site_traffic import BOT_PATTERN, INTERNAL_HOSTS
    agent = (request.headers.get("user-agent") or "").lower()
    for needle, host in PROXY_AGENTS:
        if needle in agent:
            return host
    if BOT_PATTERN.search(agent):
        return None
    referer = (request.headers.get("referer") or "").strip()
    if not referer:
        return ""
    try:
        host = (urlsplit(referer).hostname or "").lower()
    except ValueError:
        return OTHER_HOST
    host = host.removeprefix("www.")
    site_host = (urlsplit(SITE_URL).hostname or "").lower().removeprefix("www.")
    if host in INTERNAL_HOSTS or host == site_host or host.endswith(".omnitrackr.xyz"):
        return None
    if not host:
        return ""
    return host if len(host) <= 64 and HOST_RE.fullmatch(host) else OTHER_HOST


class LoadCounter:
    """Daily load counts per member, widget and host, held in memory and written about once a minute.

    Only the host name of the page showing the widget is kept, never the page address,
    the viewer's IP address or their browser.
    """

    def __init__(self, flush_interval: float = 60.0, flush_threshold: int = 400):
        setting = os.getenv("WIDGET_LOAD_COUNTS", "").strip().lower()
        if setting in ("off", "0", "false", "no"):
            self.enabled = False
        elif setting in ("on", "1", "true", "yes"):
            self.enabled = True
        else:
            self.enabled = os.getenv("TESTING", "").lower() != "true"
        self.flush_interval, self.flush_threshold = flush_interval, flush_threshold
        self._lock = threading.Lock()
        self._pending: Counter = Counter()
        self._hosts: dict = {}
        self._last_flush = time.monotonic()

    def add(self, user_id: int, kind: str, host: str) -> bool:
        if not self.enabled or kind not in LOAD_KINDS or host is None:
            return False
        day = datetime.now(timezone.utc).date()
        with self._lock:
            if len(self._pending) >= 20_000:
                return False
            seen = self._hosts.setdefault((day, user_id), set())
            if host and host not in seen:
                # Someone faking referrers can't fill a member's list with made-up sites.
                if len(seen) >= HOSTS_PER_MEMBER_DAY:
                    host = OTHER_HOST
                else:
                    seen.add(host)
            self._pending[(day, user_id, kind, host)] += 1
        return True

    def pending_for(self, user_id: int) -> Counter:
        with self._lock:
            return Counter({key: amount for key, amount in self._pending.items() if key[1] == user_id})

    def flush_due(self) -> bool:
        return bool(self._pending) and (len(self._pending) >= self.flush_threshold
                                        or time.monotonic() - self._last_flush >= self.flush_interval)

    def flush(self, db: Session) -> int:
        with self._lock:
            pending, self._pending = self._pending, Counter()
            self._last_flush = time.monotonic()
            today = datetime.now(timezone.utc).date()
            self._hosts = {key: hosts for key, hosts in self._hosts.items() if key[0] == today}
        if not pending:
            return 0
        table = models.ProfileWidgetLoad
        try:
            for (day, user_id, kind, host), amount in pending.items():
                updated = db.query(table).filter(table.user_id == user_id, table.day == day, table.kind == kind,
                                                 table.host == host).update({table.loads: table.loads + amount},
                                                                           synchronize_session=False)
                if not updated:
                    db.add(table(user_id=user_id, day=day, kind=kind, host=host, loads=amount))
                    db.flush()
            db.commit()
            return len(pending)
        except Exception:
            db.rollback()
            with self._lock:
                if len(self._pending) + len(pending) <= 20_000:
                    self._pending.update(pending)  # Try again next time.
            return 0


LOADS = LoadCounter()


def record_load(db: Session, user: models.User, kind: str, request) -> None:
    """Count one load of a member's widget. Never raises."""
    try:
        host = embed_host(request)
        if host is None:
            count("preview")
            return
        LOADS.add(user.id, kind, host)
        if LOADS.flush_due():
            LOADS.flush(db)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def host_label(host: str) -> str:
    if host == "":
        return "No site named (apps, email and image caches)"
    if host == OTHER_HOST:
        return "Other sites"
    return host


def owner_summary(db: Session, user_id: int, days: int = 7, today: Optional[date] = None) -> dict:
    """How often the member's widgets were loaded lately, and on which sites."""
    today = today or datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)
    table = models.ProfileWidgetLoad
    totals: Counter = Counter()
    kinds: Counter = Counter()
    try:
        for kind, host, loads in db.query(table.kind, table.host, func.sum(table.loads)).filter(
                table.user_id == user_id, table.day >= start).group_by(table.kind, table.host).all():
            totals[host] += int(loads or 0)
            kinds[kind] += int(loads or 0)
    except Exception:
        db.rollback()
    for (day, _, kind, host), amount in LOADS.pending_for(user_id).items():
        if day >= start:
            totals[host] += amount
            kinds[kind] += amount
    named = [(host, n) for host, n in totals.most_common() if host not in ("", OTHER_HOST)]
    return {"days": days, "loads": sum(totals.values()), "sites": [host for host, _ in named[:5]],
            "by_kind": {kind: kinds[kind] for kind in KINDS if kinds[kind]}}


def summary_sentence(summary: dict) -> str:
    loads = summary.get("loads") or 0
    if not loads:
        return "Nobody has loaded your widgets in the last week. Paste one somewhere and this starts counting."
    times = "once" if loads == 1 else f"{loads:,} times"
    sites = summary.get("sites") or []
    where = ""
    if sites:
        where = f", on {sites[0]}" if len(sites) == 1 else f", on {', '.join(sites[:-1])} and {sites[-1]}"
    return f"Your widgets were loaded {times} in the last {summary.get('days', 7)} days{where}."


# ---------------------------------------------------------------- site-wide counters (no user ids)

COUNTERS = {
    "served_png": "PNG widget images served",
    "served_svg": "SVG widget images served",
    "not_modified": "Images answered with 304 Not Modified",
    "preview": "Previews loaded on OmniTrackr pages",
    "page_owner": "Widget page opened by its owner",
    "page_guest": "Widget page opened by someone else",
    "settings_shown": "Widget panel shown in Settings",
    "settings_copy": "Forum code copied from Settings",
    "copy_html": "HTML copied",
    "copy_markdown": "Markdown copied",
    "copy_bbcode": "BBCode copied",
    "copy_anilist": "AniList code copied",
    "copy_image": "Image link copied",
    "copy_link": "Profile link copied",
    "pick_svg": "Switched to SVG",
    "pick_auto": "Picked auto colors",
}
CLIENT_COUNTERS = {"copy_html", "copy_markdown", "copy_bbcode", "copy_anilist", "copy_image", "copy_link",
                   "pick_svg", "pick_auto", "settings_copy"}


def count(key: str) -> bool:
    """Add 1 to a "widgets" counter for today. Never raises, and stores nothing about who."""
    if key not in COUNTERS:
        return False
    try:
        from .site_traffic import RECORDER
        if not RECORDER.enabled:
            return False
        day = datetime.now(timezone.utc).date()
        with RECORDER._lock:
            RECORDER._pending[(day, "widgets", key)] += 1
            RECORDER._events += 1
        return True
    except Exception:
        return False


def stats(db: Session, days: int, now: datetime) -> dict:
    """Site stats: widget loads, members with live widgets, the sites they're on, and visits they sent."""
    start = (now - timedelta(days=days - 1)).date()
    week = (now - timedelta(days=6)).date()
    daily = models.SiteTrafficDaily
    counts = dict(db.query(daily.key, func.sum(daily.count)).filter(
        daily.kind == "widgets", daily.day >= start).group_by(daily.key).all())
    visits = dict(db.query(daily.kind, func.sum(daily.count)).filter(
        daily.kind.in_(("source", "human_source")), daily.key == "profile-widget", daily.day >= start,
    ).group_by(daily.kind).all())
    loads = models.ProfileWidgetLoad
    total = db.query(func.sum(loads.loads)).filter(loads.day >= start).scalar() or 0
    members = db.query(func.count(func.distinct(loads.user_id))).filter(loads.day >= start).scalar() or 0
    members_week = db.query(func.count(func.distinct(loads.user_id))).filter(loads.day >= week).scalar() or 0
    by_kind = dict(db.query(loads.kind, func.sum(loads.loads)).filter(loads.day >= start).group_by(loads.kind).all())
    hosts = db.query(loads.host, func.sum(loads.loads).label("n"), func.count(func.distinct(loads.user_id))).filter(
        loads.day >= start).group_by(loads.host).order_by(func.sum(loads.loads).desc()).limit(10).all()
    profiles = models.PublicProfile
    return {
        "counts": {key: int(counts.get(key) or 0) for key in COUNTERS},
        "labels": COUNTERS,
        "loads": int(total),
        "members": int(members),
        "members_7d": int(members_week),
        "by_kind": [{"kind": kind, "label": LABELS[kind][0], "count": int(by_kind.get(kind) or 0)} for kind in KINDS],
        "hosts": [{"host": host_label(host), "count": int(n or 0), "members": int(m or 0)} for host, n, m in hosts],
        "visits": int(visits.get("source") or 0),
        "people": int(visits.get("human_source") or 0),
        "now_on": int(db.query(func.count(profiles.id)).filter(profiles.enabled == True,
                                                               profiles.show_now == True).scalar() or 0),
    }
