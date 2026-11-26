"""The 1200x630 image chat apps show for a yearbook link (/yearbook/<token>/card.png).

Text and shapes only: the class year, the name on the cover, the quote, how many notes are in
and the top vote. No notes, names of people who signed, or library titles ever appear on it.
"""
from __future__ import annotations

from io import BytesIO

from .tonight_card import BACKGROUND, EDGE, GOLD, HEIGHT, LEFT, LILAC, MUTED, RIGHT, SOFT, VIOLET, WHITE, WIDTH, \
    _glow, _pill, _wrap

NOTE_TINTS = ((253, 248, 236), (254, 243, 199), (237, 233, 254), (220, 252, 231))


def _note(draw, x: float, y: float, w: float, h: float, tint) -> None:
    """A small paper note with two lines of "writing" and a strip of tape."""
    draw.rounded_rectangle((x, y, x + w, y + h), radius=10, fill=tint)
    for index, width in enumerate((0.72, 0.5)):
        line_y = y + 26 + index * 20
        draw.rounded_rectangle((x + 16, line_y, x + 16 + (w - 32) * width, line_y + 7), radius=4, fill=(196, 186, 224))
    draw.rounded_rectangle((x + w / 2 - 22, y - 9, x + w / 2 + 22, y + 9), radius=3, fill=(245, 196, 81))


def render(facts: dict) -> bytes:
    """PNG bytes for one yearbook. ``facts`` comes from yearbook.card_facts."""
    from PIL import Image, ImageDraw
    from .routers.profiles import _fit, _font
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    image = _glow(image, (WIDTH - 140, -80), GOLD, 0.38)
    image = _glow(image, (40, HEIGHT + 240), VIOLET, 0.6)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, WIDTH - 40, HEIGHT - 40), radius=28, outline=EDGE, width=2)
    span = RIGHT - LEFT - 300
    year = facts.get("year") or ""
    state = facts.get("state") or "open"
    eyebrow = f"CLASS OF {year} · SIGN MY YEARBOOK" if state == "open" else f"CLASS OF {year} · YEARBOOK"
    eyebrow_font = _font(26, bold=True)
    draw.text((LEFT, 78), _fit(draw, eyebrow, eyebrow_font, RIGHT - LEFT), font=eyebrow_font, fill=GOLD)

    cover = facts.get("cover") or "My yearbook"
    big = _font(92, bold=True)
    lines = _wrap(draw, cover, big, span, 2)
    if len(lines) == 2:
        big = _font(66, bold=True)
        lines = _wrap(draw, cover, big, span, 2)
    y = 126
    for line in lines:
        draw.text((LEFT, y), line, font=big, fill=WHITE)
        y += big.size + 10
    quote = (facts.get("quote") or "").strip()
    if quote:
        quote_font = _font(30)
        for line in _wrap(draw, f"“{quote}”", quote_font, span, 2):
            draw.text((LEFT, y + 10), line, font=quote_font, fill=SOFT)
            y += quote_font.size + 8
    top = (facts.get("top") or "").strip()
    if top:
        voted = _font(26, bold=True)
        y += 24
        for line in _wrap(draw, f"Voted: {top}", voted, span, 2):
            draw.text((LEFT, y), line, font=voted, fill=LILAC)
            y += voted.size + 8

    # A little stack of notes on the right: one per note in, up to five, or blank ones waiting.
    notes = max(0, int(facts.get("notes") or 0))
    shown = max(3, min(5, notes))
    for index in range(shown):
        x = RIGHT - 250 + (index % 2) * 46
        top_y = 120 + index * 62
        _note(draw, x, top_y, 200, 84, NOTE_TINTS[index % len(NOTE_TINTS)] if index < max(notes, 1) else (58, 52, 92))

    baseline = HEIGHT - 132
    action = "Sign it" if state == "open" else "Make your own"
    end = _pill(draw, LEFT, baseline, action, _font(26, bold=True), VIOLET, WHITE)
    if notes:
        who = f"{notes} note{'' if notes == 1 else 's'} so far" if state == "open" else f"{notes} note{'' if notes == 1 else 's'}"
    else:
        who = "Be the first to sign"
    if state == "open" and facts.get("closes"):
        who += f" · Signing closes after {facts['closes']}"
    draw.text((end + 24, baseline + 30), _fit(draw, who, _font(24), RIGHT - end - 260), font=_font(24),
              fill=GOLD if notes else MUTED, anchor="lm")
    brand = "omnitrackr.xyz"
    brand_font = _font(24, bold=True)
    draw.text((RIGHT - draw.textlength(brand, font=brand_font), baseline + 30), brand, font=brand_font, fill=WHITE,
              anchor="lm")
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


STORY_W, STORY_H = 1080, 1920


def render_story(facts: dict) -> bytes:
    """The 1080x1920 picture an owner posts to a story: the cover, the top votes and a pile of notes.
    Stories cover the top and bottom with their own bars, so the words sit inside them."""
    from PIL import Image, ImageDraw
    from .routers.profiles import _fit, _font
    image = Image.new("RGB", (STORY_W, STORY_H), (14, 22, 44))
    image = _glow(image, (STORY_W - 80, 120), GOLD, 0.34)
    image = _glow(image, (60, STORY_H - 160), VIOLET, 0.55)
    draw = ImageDraw.Draw(image)
    gold_line = (245, 196, 81)
    draw.rounded_rectangle((48, 130, STORY_W - 48, STORY_H - 150), radius=36, outline=gold_line, width=3)
    draw.rounded_rectangle((62, 144, STORY_W - 62, STORY_H - 164), radius=28, outline=(91, 77, 48), width=2)
    pad = 110
    width = STORY_W - pad * 2
    middle = STORY_W / 2
    year = facts.get("year") or ""
    state = facts.get("state") or "open"
    eyebrow_font = _font(34, bold=True)
    draw.text((middle, 250), f"CLASS OF {year}", font=eyebrow_font, fill=GOLD, anchor="mm")

    cover = facts.get("cover") or "My yearbook"
    big = _font(150, bold=True)
    lines = _wrap(draw, cover, big, width, 2)
    if len(lines) == 2 or draw.textlength(lines[0], font=big) > width:
        big = _font(104, bold=True)
        lines = _wrap(draw, cover, big, width, 2)
    y = 330
    for line in lines:
        draw.text((middle, y + big.size / 2), line, font=big, fill=WHITE, anchor="mm")
        y += big.size + 18
    kind_font = _font(30, bold=True)
    draw.text((middle, y + 24), "Y E A R B O O K", font=kind_font, fill=(251, 227, 161), anchor="mm")
    y += 90
    quote = (facts.get("quote") or "").strip()
    if quote:
        quote_font = _font(42)
        for line in _wrap(draw, f"“{quote}”", quote_font, width, 3):
            draw.text((middle, y + 24), line, font=quote_font, fill=SOFT, anchor="mm")
            y += quote_font.size + 14
        y += 20

    votes = list(facts.get("votes") or [])[:3]
    vote_font = _font(32, bold=True)
    count_font = _font(28, bold=True)
    y += 40
    if votes:
        draw.text((middle, y), "VOTED BY THE CLASS", font=_font(28, bold=True), fill=GOLD, anchor="mm")
        y += 50
        for label, votes_for in votes:
            text_lines = _wrap(draw, label, vote_font, width - 160, 2)
            height = 40 + len(text_lines) * 42
            draw.rounded_rectangle((pad, y, STORY_W - pad, y + height), radius=28, fill=(32, 45, 82),
                                   outline=(140, 112, 48), width=2)
            draw.text((pad + 40, y + height / 2), str(votes_for), font=_font(44, bold=True), fill=GOLD, anchor="lm")
            text_y = y + 20
            for line in text_lines:
                draw.text((pad + 110, text_y + 21), line, font=vote_font, fill=WHITE, anchor="lm")
                text_y += 42
            y += height + 18

    # A pile of notes, one per note in (up to six), in whatever room is left above the words at the bottom.
    baseline = STORY_H - 330
    notes = max(0, int(facts.get("notes") or 0))
    region_top, region_bottom = y + 30, baseline - 80
    pile, step, note_h = max(3, min(6, notes)), 64, 120
    while pile > 1 and (pile - 1) * step + note_h > region_bottom - region_top:
        pile -= 1
    pile_h = (pile - 1) * step + note_h
    if pile_h <= region_bottom - region_top:
        top = region_top + (region_bottom - region_top - pile_h) / 2
        for index in range(pile):
            x = middle - 230 + (60 if index % 2 else -60)
            tint = NOTE_TINTS[index % len(NOTE_TINTS)] if index < max(notes, 1) else (58, 52, 92)
            _note(draw, x, top + index * step, 460, note_h, tint)

    if state == "open":
        line = f"{notes} note{'' if notes == 1 else 's'} so far" if notes else "Be the first to sign"
        action = "Tap the link to sign it"
        closes = facts.get("closes")
        small = f"Signing closes after {closes}" if closes else ""
    else:
        line = f"{notes} note{'' if notes == 1 else 's'}"
        action = "Make your own at omnitrackr.xyz"
        small = ""
    draw.text((middle, baseline), action, font=_font(46, bold=True), fill=WHITE, anchor="mm")
    draw.text((middle, baseline + 64), _fit(draw, " · ".join(part for part in (line, small) if part), count_font, width),
              font=count_font, fill=GOLD, anchor="mm")
    brand_font = _font(30, bold=True)
    draw.text((middle, baseline + 128), "omnitrackr.xyz", font=brand_font, fill=MUTED, anchor="mm")
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
