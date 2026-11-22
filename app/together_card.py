"""The 1200x630 image chat apps show for a watch together invite (/together/join/<token>/card.png).

Text and shapes only, drawn with Pillow like the group poll card: who's asking, the title,
the pace and a row of weeks. Nobody's place or notes ever appear on it.
"""
from __future__ import annotations

from io import BytesIO

from .tonight_card import BACKGROUND, EDGE, GOLD, HEIGHT, LEFT, LILAC, MUTED, RIGHT, ROW, SOFT, TEAL, VIOLET, WHITE, \
    WIDTH, _glow, _pill, _wrap

WEEKS_DRAWN = 12


def render(facts: dict) -> bytes:
    """PNG bytes for one plan. ``facts`` comes from together.card_facts."""
    from PIL import Image, ImageDraw
    from .routers.profiles import _fit, _font
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    image = _glow(image, (WIDTH - 140, -40), TEAL, 0.55)
    image = _glow(image, (80, HEIGHT + 200), VIOLET, 0.6)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, WIDTH - 40, HEIGHT - 40), radius=28, outline=EDGE, width=2)
    span = RIGHT - LEFT

    verb = facts.get("verb") or "Watch"
    owner = facts.get("owner") or "A friend"
    eyebrow = f"{verb.upper()} TOGETHER · {owner.upper()} INVITED YOU"
    if facts.get("ended"):
        eyebrow = f"{verb.upper()} TOGETHER · FINISHED"
    eyebrow_font = _font(26, bold=True)
    draw.text((LEFT, 78), _fit(draw, eyebrow, eyebrow_font, span), font=eyebrow_font, fill=TEAL)

    big = _font(80, bold=True)
    lines = _wrap(draw, facts["title"], big, span, 2)
    if len(lines) == 2:
        big = _font(64, bold=True)
        lines = _wrap(draw, facts["title"], big, span, 2)
    y = 124
    for line in lines:
        draw.text((LEFT, y), line, font=big, fill=WHITE)
        y += big.size + 12
    meta = " · ".join(part for part in (facts.get("label"), facts.get("scope"), facts.get("length")) if part)
    draw.text((LEFT, y + 6), _fit(draw, meta, _font(30), span), font=_font(30), fill=SOFT)
    y += 62

    # One block per week, like the track on the plan page.
    weeks = max(1, int(facts.get("weeks") or 1))
    drawn = min(weeks, WEEKS_DRAWN)
    gap = 10
    block = (span - gap * (drawn - 1)) / drawn
    top = max(y + 16, 350)
    for index in range(drawn):
        x0 = LEFT + index * (block + gap)
        fill = VIOLET if index == 0 else ROW
        draw.rounded_rectangle((x0, top, x0 + block, top + 26), radius=10, fill=fill, outline=EDGE, width=2)
    if weeks > drawn:
        draw.text((RIGHT, top + 40), f"+ {weeks - drawn} more weeks", font=_font(22), fill=MUTED, anchor="ra")
    pace = facts.get("pace") or ""
    starts = facts.get("starts") or ""
    week_word = "week" if weeks == 1 else "weeks"
    draw.text((LEFT, top + 40), _fit(draw, f"{pace} · {weeks} {week_word} · starts {starts}", _font(26), span - 220),
              font=_font(26), fill=LILAC)

    baseline = HEIGHT - 132
    action = "Join in" if not facts.get("ended") else "See the plan"
    end = _pill(draw, LEFT, baseline, action, _font(26, bold=True), VIOLET, WHITE)
    people = int(facts.get("people") or 1)
    if not facts.get("ended"):
        who = "Notes stay hidden until you get there"
        if people > 1:
            who = f"{people} people in · notes stay hidden until you get there"
        draw.text((end + 24, baseline + 30), _fit(draw, who, _font(24), RIGHT - end - 260), font=_font(24),
                  fill=GOLD if people > 1 else LILAC, anchor="lm")
    brand = "omnitrackr.xyz"
    brand_font = _font(24, bold=True)
    draw.text((RIGHT - draw.textlength(brand, font=brand_font), baseline + 30), brand, font=brand_font, fill=WHITE,
              anchor="lm")
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
