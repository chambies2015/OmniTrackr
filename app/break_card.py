"""The 1200x630 image chat apps show for a shared break plan (/break/s/<token>/card.png).

Text and shapes only, drawn with Pillow like the watch together card: whose break, its name and
dates, one column per day with a block for each thing planned (filled in once it's ticked), and
the totals. Only titles from shelves the member shares publicly are counted (break_plan.card_facts).
"""
from __future__ import annotations

from io import BytesIO

from .tonight_card import BACKGROUND, EDGE, GOLD, HEIGHT, LEFT, LILAC, MUTED, RIGHT, ROW, SOFT, TEAL, VIOLET, WHITE, \
    WIDTH, _glow, _pill, _wrap

DAYS_DRAWN = 16
BLOCKS_DRAWN = 5


def render(facts: dict) -> bytes:
    """PNG bytes for one shared plan. ``facts`` comes from break_plan.card_facts."""
    from PIL import Image, ImageDraw
    from .routers.profiles import _fit, _font
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    image = _glow(image, (WIDTH - 120, -60), GOLD, 0.45)
    image = _glow(image, (60, HEIGHT + 220), VIOLET, 0.6)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, WIDTH - 40, HEIGHT - 40), radius=28, outline=EDGE, width=2)
    span = RIGHT - LEFT

    owner = facts.get("owner") or "A friend"
    eyebrow = f"{owner.upper()}'S BREAK PLAN · {str(facts.get('span') or '').upper()}"
    eyebrow_font = _font(26, bold=True)
    draw.text((LEFT, 78), _fit(draw, eyebrow, eyebrow_font, span), font=eyebrow_font, fill=GOLD)

    big = _font(76, bold=True)
    lines = _wrap(draw, facts.get("name") or "A break", big, span, 2)
    if len(lines) == 2:
        big = _font(60, bold=True)
        lines = _wrap(draw, facts.get("name") or "A break", big, span, 2)
    y = 122
    for line in lines:
        draw.text((LEFT, y), line, font=big, fill=WHITE)
        y += big.size + 10
    titles = int(facts.get("titles") or 0)
    if facts.get("phase") == "after":
        meta = (f"{facts.get('done', 0)} of {facts.get('stretches', 0)} done · {facts.get('finished', 0)} finished · "
                f"about {facts.get('hours')}")
    else:
        meta = f"{titles} {'title' if titles == 1 else 'titles'} · about {facts.get('hours')}"
    draw.text((LEFT, y + 6), _fit(draw, meta, _font(30), span), font=_font(30), fill=SOFT)
    y += 58
    names = [name for name in facts.get("first_titles") or [] if name]
    if names:
        draw.text((LEFT, y + 4), _fit(draw, " · ".join(names), _font(24), span), font=_font(24), fill=LILAC)

    # One column per day; a block for each thing on it, filled in when it's done.
    days = list(facts.get("days") or [])[:DAYS_DRAWN]
    done_days = list(facts.get("done_days") or [])[:DAYS_DRAWN]
    if days:
        gap = 12
        width = (span - gap * (len(days) - 1)) / len(days)
        top = 380
        block = 18
        for index, planned in enumerate(days):
            x0 = LEFT + index * (width + gap)
            draw.rounded_rectangle((x0, top, x0 + width, top + 4), radius=2, fill=EDGE)
            done = done_days[index] if index < len(done_days) else 0
            for slot in range(min(int(planned or 0), BLOCKS_DRAWN)):
                y0 = top + 12 + slot * (block + 6)
                fill = TEAL if slot < done else ROW
                draw.rounded_rectangle((x0, y0, x0 + width, y0 + block), radius=6, fill=fill, outline=EDGE, width=2)

    baseline = HEIGHT - 132
    end = _pill(draw, LEFT, baseline, "Plan your own", _font(26, bold=True), VIOLET, WHITE)
    note = "Filled from your own list, day by day"
    draw.text((end + 24, baseline + 30), _fit(draw, note, _font(24), RIGHT - end - 260), font=_font(24), fill=MUTED,
              anchor="lm")
    brand = "omnitrackr.xyz"
    brand_font = _font(24, bold=True)
    draw.text((RIGHT - draw.textlength(brand, font=brand_font), baseline + 30), brand, font=brand_font, fill=WHITE,
              anchor="lm")
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
