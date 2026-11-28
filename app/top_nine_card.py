"""Pictures of a top nine (app/top_nine.py): a 3:4 post, a 1080x1920 story and a 1200x630 link preview.

Posters arrive as raw bytes (fetched by the router through the tier list's image proxy,
allowlisted hosts only). A square without a usable poster is drawn in its format's colour
with the title written on it, and an empty square stays a faint outline.
"""
from __future__ import annotations

import threading
import zlib
from functools import lru_cache
from io import BytesIO
from typing import Optional

POST_W, POST_H = 1080, 1440
STORY_W, STORY_H = 1080, 1920
CARD_W, CARD_H = 1200, 630
POSTER_PIXELS = 12_000_000  # after JPEG draft scaling; a real poster is well under 2 million
SITE = "omnitrackr.xyz/top-nine"

# bg top, bg bottom, square outline, text, soft text, accent
PALETTES = {
    "night": {"top": (20, 16, 44), "bottom": (8, 7, 20), "line": (52, 46, 92), "text": (246, 244, 255),
              "soft": (190, 184, 224), "accent": (167, 139, 250)},
    "paper": {"top": (250, 245, 235), "bottom": (238, 229, 212), "line": (214, 202, 182), "text": (32, 27, 22),
              "soft": (98, 88, 76), "accent": (196, 72, 44)},
    "berry": {"top": (74, 16, 64), "bottom": (30, 6, 34), "line": (110, 44, 96), "text": (255, 241, 247),
              "soft": (244, 190, 216), "accent": (255, 196, 92)},
}
# The site's format colours (--fmt-* in site.css), darkened for a square.
KIND_RGB = {"movie": (244, 114, 182), "tv": (96, 165, 250), "anime": (248, 113, 113), "game": (52, 211, 153),
            "album": (167, 139, 250), "book": (251, 191, 36), "manga": (251, 146, 60), "podcast": (45, 212, 191),
            "audiobook": (232, 121, 249)}
KIND_WORD = {"movie": "FILM", "tv": "SHOW", "anime": "ANIME", "game": "GAME", "album": "ALBUM", "book": "BOOK",
             "manga": "MANGA", "podcast": "PODCAST", "audiobook": "AUDIOBOOK"}


def _fonts():
    from .routers.profiles import _fit, _font
    return _font, _fit


# Pictures render on several threads; the shared probe font is used by one at a time.
_probe_lock = threading.Lock()


@lru_cache(maxsize=2)
def _probe(bold: bool):
    """(font, the mask it draws for a character it has no glyph for), or None when that can't be told."""
    font, _ = _fonts()
    probe = font(32, bold=bold)
    try:
        with _probe_lock:
            missing = probe.getmask("\U0010fffd")
        return probe, (missing.size, bytes(missing))
    except Exception:
        return None


@lru_cache(maxsize=4096)
def _has_glyph(char: str, bold: bool) -> bool:
    found = _probe(bold)
    if found is None or char.isspace():
        return True
    probe, missing = found
    try:
        with _probe_lock:
            mask = probe.getmask(char)
    except Exception:
        return False
    return (mask.size, bytes(mask)) != missing


def _ink(text, bold: bool = True) -> str:
    """The text as the pictures can draw it: no emoji or scripts the font lacks (they'd be empty boxes),
    no control characters, direction overrides or stacked accents. May come back empty."""
    from .top_nine import tidy
    kept = "".join(char for char in tidy(text) if _has_glyph(char, bold))
    return " ".join(kept.split())


def _background(size: tuple[int, int], palette: dict):
    from PIL import Image
    width, height = size
    top, bottom = palette["top"], palette["bottom"]
    strip = Image.new("RGB", (1, height))
    for y in range(height):
        share = y / max(1, height - 1)
        strip.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * share) for i in range(3)))
    return strip.resize((width, height))


def _open(source: Optional[bytes], hint: tuple[int, int]):
    if not source:
        return None
    from PIL import Image
    try:
        with Image.open(BytesIO(source)) as image:
            image.draft("RGB", (hint[0] * 2, hint[1] * 2))
            width, height = image.size
            # A small file can still decode to hundreds of megabytes (a huge PNG), so those get a drawn square.
            if not 0 < width * height <= POSTER_PIXELS:
                return None
            return image.convert("RGB")
    except Exception:
        return None


def _picture(source: Optional[bytes], size: tuple[int, int]):
    """The poster filling ``size``. Square art (albums, podcasts) sits whole on a blurred copy of itself."""
    from PIL import ImageFilter, ImageOps
    image = _open(source, size)
    if image is None:
        return None
    width, height = size
    if image.width / max(1, image.height) >= 0.9 and width / height < 0.9:
        backdrop = ImageOps.fit(image, size).filter(ImageFilter.GaussianBlur(radius=max(8, width // 14)))
        backdrop = backdrop.point(lambda value: int(value * 0.55))
        art = image.resize((width, max(1, round(image.height * width / image.width))))
        if art.height > height:
            art = ImageOps.fit(image, (width, height))
        backdrop.paste(art, (0, (height - art.height) // 2))
        return backdrop
    return ImageOps.fit(image, size, centering=(0.5, 0.42))


def _mask(size: tuple[int, int], radius: int):
    from PIL import Image, ImageDraw
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def _wrap(draw, text: str, font, width: int, lines: int) -> list[str]:
    _, fit = _fonts()
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
    return [fit(draw, part, font, width) for part in result]


def _diagonal(size: tuple[int, int], start: tuple, end: tuple):
    """A top-left to bottom-right gradient between two colours."""
    from PIL import Image
    small = Image.new("RGB", (16, 16))
    for x in range(16):
        for y in range(16):
            share = (x + y) / 30
            small.putpixel((x, y), tuple(int(start[i] + (end[i] - start[i]) * share) for i in range(3)))
    return small.resize(size, Image.BILINEAR)


def _text_square(size: tuple[int, int], tile: dict, scale: float):
    """A square with no poster: the format's colour, its name small at the top, the title large."""
    from PIL import Image, ImageDraw
    font, _ = _fonts()
    width, height = size
    base = KIND_RGB.get(tile.get("kind"), (120, 110, 200))
    # Two squares of the same format shouldn't look identical: the shade moves a little with the title.
    shade = 0.3 + (zlib.crc32(tile["title"].encode("utf-8")) % 9) / 50
    square = _diagonal(size, tuple(int(value * (shade + 0.1)) for value in base), tuple(int(value * shade * 0.7) for value in base))
    draw = ImageDraw.Draw(square)
    # A lighter band across the top third, in the format's colour.
    draw.rectangle((0, 0, width, int(height * 0.06)), fill=tuple(int(value * 0.75) for value in base))
    pad = max(10, int(16 * scale))
    label = font(max(11, int(18 * scale)), bold=True)
    draw.text((pad, int(height * 0.06) + pad), KIND_WORD.get(tile.get("kind"), ""), font=label,
              fill=tuple(min(255, int(value * 1.25)) for value in base))
    size_px = max(14, int(34 * scale))
    title_font = font(size_px, bold=True)
    lines = _wrap(draw, _ink(tile["title"]), title_font, width - pad * 2, 5)
    line_h = int(size_px * 1.18)
    y = height - pad - line_h * len(lines) - (int(22 * scale) if tile.get("year") else 0)
    for line in lines:
        draw.text((pad, y), line, font=title_font, fill=(255, 255, 255))
        y += line_h
    if tile.get("year"):
        draw.text((pad, y + int(4 * scale)), str(tile["year"]), font=font(max(11, int(18 * scale))),
                  fill=(225, 222, 240))
    return square


def _square(canvas, box: tuple[int, int, int, int], tile: Optional[dict], poster: Optional[bytes], palette: dict,
            radius: int, scale: float) -> None:
    from PIL import ImageDraw
    x0, y0, x1, y1 = box
    size = (x1 - x0, y1 - y0)
    if not tile:
        ImageDraw.Draw(canvas).rounded_rectangle(box, radius=radius, outline=palette["line"], width=max(2, int(3 * scale)))
        return
    picture = _picture(poster, size) or _text_square(size, tile, scale)
    canvas.paste(picture, (x0, y0), _mask(size, radius))


def _grid(canvas, origin: tuple[int, int], cell: tuple[int, int], gap: int, tiles: list, posters: dict,
          palette: dict, radius: int, scale: float) -> None:
    for index in range(9):
        row, column = divmod(index, 3)
        x = origin[0] + column * (cell[0] + gap)
        y = origin[1] + row * (cell[1] + gap)
        tile = tiles[index] if index < len(tiles) else None
        _square(canvas, (x, y, x + cell[0], y + cell[1]), tile, posters.get(index), palette, radius, scale)


def _save(image, fmt: str) -> bytes:
    buffer = BytesIO()
    if fmt == "JPEG":
        image.save(buffer, format="JPEG", quality=88, optimize=True, progressive=True)
    else:
        image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _eyebrow(year: int) -> str:
    return f"TOP NINE · {year}"


def _name(data: dict) -> str:
    return _ink(data["name"]) or f"My {data['year']}"


def render_post(data: dict, posters: dict) -> bytes:
    """1080x1440 (3:4, the shape Instagram's grid shows): the name, the nine squares, the address."""
    from PIL import ImageDraw
    font, fit = _fonts()
    palette = PALETTES.get(data.get("theme"), PALETTES["night"])
    image = _background((POST_W, POST_H), palette)
    draw = ImageDraw.Draw(image)
    pad = 60
    draw.text((pad, 58), _eyebrow(data["year"]), font=font(28, bold=True), fill=palette["accent"])
    name_font = font(66, bold=True)
    draw.text((pad, 96), fit(draw, _name(data), name_font, POST_W - pad * 2), font=name_font, fill=palette["text"])
    gap = 16
    cell_w = (POST_W - pad * 2 - gap * 2) // 3
    top = 206
    cell_h = (POST_H - top - 96 - gap * 2) // 3
    _grid(image, (pad, top), (cell_w, cell_h), gap, data["tiles"], posters, palette, 18, 1.0)
    footer = font(26, bold=True)
    y = POST_H - 70
    draw.text((pad, y), "Made on OmniTrackr", font=footer, fill=palette["soft"])
    draw.text((POST_W - pad - draw.textlength(SITE, font=footer), y), SITE, font=footer, fill=palette["text"])
    return _save(image, "JPEG")


def render_story(data: dict, posters: dict) -> bytes:
    """1080x1920, with the name and the grid kept clear of Instagram's top and bottom bars."""
    from PIL import ImageDraw
    font, fit = _fonts()
    palette = PALETTES.get(data.get("theme"), PALETTES["night"])
    image = _background((STORY_W, STORY_H), palette)
    draw = ImageDraw.Draw(image)
    eyebrow = font(32, bold=True)
    text = _eyebrow(data["year"])
    draw.text(((STORY_W - draw.textlength(text, font=eyebrow)) / 2, 236), text, font=eyebrow, fill=palette["accent"])
    name_font = font(76, bold=True)
    name = fit(draw, _name(data), name_font, STORY_W - 120)
    draw.text(((STORY_W - draw.textlength(name, font=name_font)) / 2, 282), name, font=name_font, fill=palette["text"])
    gap = 16
    cell_w, cell_h = 296, 386
    left = (STORY_W - cell_w * 3 - gap * 2) // 2
    top = 410
    _grid(image, (left, top), (cell_w, cell_h), gap, data["tiles"], posters, palette, 20, 0.98)
    footer = font(30, bold=True)
    line = f"Make yours at {SITE}"
    draw.text(((STORY_W - draw.textlength(line, font=footer)) / 2, top + cell_h * 3 + gap * 2 + 34), line,
              font=footer, fill=palette["soft"])
    return _save(image, "JPEG")


def render_card(data: dict, posters: dict) -> bytes:
    """1200x630 link preview: the name and the first titles on the left, the grid on the right."""
    from PIL import ImageDraw
    font, fit = _fonts()
    palette = PALETTES.get(data.get("theme"), PALETTES["night"])
    image = _background((CARD_W, CARD_H), palette)
    draw = ImageDraw.Draw(image)
    gap = 10
    cell_w, cell_h = 136, 176
    grid_w = cell_w * 3 + gap * 2
    left = CARD_W - 44 - grid_w
    top = (CARD_H - (cell_h * 3 + gap * 2)) // 2
    _grid(image, (left, top), (cell_w, cell_h), gap, data["tiles"], posters, palette, 10, 0.45)
    pad = 52
    width = left - pad - 40
    draw.text((pad, 58), _eyebrow(data["year"]), font=font(22, bold=True), fill=palette["accent"])
    name_font = font(54, bold=True)
    lines = _wrap(draw, _name(data), name_font, width, 2)
    y = 92
    for line in lines:
        draw.text((pad, y), line, font=name_font, fill=palette["text"])
        y += 64
    y += 18
    item_font = font(24)
    shown = [tile for tile in data["tiles"] if tile][:5]
    for number, tile in enumerate(shown, start=1):
        title = _ink(tile["title"], bold=False) or KIND_WORD.get(tile.get("kind"), "").capitalize()
        draw.text((pad, y), fit(draw, f"{number}. {title}", item_font, width), font=item_font, fill=palette["soft"])
        y += 36
    rest = sum(1 for tile in data["tiles"] if tile) - len(shown)
    if rest > 0:
        draw.text((pad, y), f"and {rest} more", font=item_font, fill=palette["soft"])
    if data.get("ask", True):
        draw.text((pad, CARD_H - 108), "How many have you seen?", font=font(26, bold=True), fill=palette["accent"])
    footer = font(22, bold=True)
    draw.text((pad, CARD_H - 70), f"Make yours: {SITE}", font=footer, fill=palette["text"])
    return _save(image, "PNG")


RENDERERS = {"post": render_post, "story": render_story, "card": render_card}
