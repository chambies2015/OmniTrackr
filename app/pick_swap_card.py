"""The 1200x630 image chat apps show for a pick swap invite (/swap/join/<token>/card.png).

Text and shapes only: who's asking, the swap's name, what counts, unwrap day and one
wrapped box per person in it. No picks or draws ever appear on it.
"""
from __future__ import annotations

from io import BytesIO

from .tonight_card import BACKGROUND, EDGE, GOLD, HEIGHT, LEFT, LILAC, MUTED, RIGHT, SOFT, TEAL, VIOLET, WHITE, \
    WIDTH, _glow, _pill, _wrap

PINK = (244, 114, 182)
BOX_COLORS = (VIOLET, TEAL, PINK, (96, 165, 250), (251, 146, 60))
BOXES_DRAWN = 8


def _box(draw, x: float, y: float, size: float, color, ribbon) -> None:
    """A wrapped present: body, lid, a ribbon both ways and a bow."""
    lid = size * 0.26
    draw.rounded_rectangle((x, y + lid, x + size, y + size), radius=8, fill=color)
    draw.rounded_rectangle((x - 6, y + lid * 0.25, x + size + 6, y + lid + 6), radius=8, fill=color, outline=BACKGROUND,
                           width=3)
    middle = x + size / 2
    band = max(8, size * 0.12)
    draw.rectangle((middle - band / 2, y + lid * 0.25, middle + band / 2, y + size), fill=ribbon)
    loop = size * 0.2
    draw.ellipse((middle - loop * 1.6, y - loop * 0.55, middle - 2, y + lid * 0.45), outline=ribbon, width=6)
    draw.ellipse((middle + 2, y - loop * 0.55, middle + loop * 1.6, y + lid * 0.45), outline=ribbon, width=6)


def render(facts: dict) -> bytes:
    """PNG bytes for one swap. ``facts`` comes from pick_swap.card_facts."""
    from PIL import Image, ImageDraw
    from .routers.profiles import _fit, _font
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    image = _glow(image, (WIDTH - 120, -60), GOLD, 0.42)
    image = _glow(image, (60, HEIGHT + 220), VIOLET, 0.6)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, WIDTH - 40, HEIGHT - 40), radius=28, outline=EDGE, width=2)
    span = RIGHT - LEFT
    owner = facts.get("owner") or "A friend"
    state = facts.get("state") or "open"
    eyebrow = f"PICK SWAP · {owner.upper()} INVITED YOU"
    if state in ("drawn", "revealed"):
        eyebrow = "PICK SWAP · NAMES ARE DRAWN"
    elif state == "cancelled":
        eyebrow = "PICK SWAP · CALLED OFF"
    eyebrow_font = _font(26, bold=True)
    draw.text((LEFT, 78), _fit(draw, eyebrow, eyebrow_font, span), font=eyebrow_font, fill=GOLD)

    big = _font(80, bold=True)
    lines = _wrap(draw, facts.get("name") or "Pick swap", big, span, 2)
    if len(lines) == 2:
        big = _font(62, bold=True)
        lines = _wrap(draw, facts.get("name") or "Pick swap", big, span, 2)
    y = 124
    for line in lines:
        draw.text((LEFT, y), line, font=big, fill=WHITE)
        y += big.size + 12
    lead = "Secret Santa, but everyone gives a recommendation"
    draw.text((LEFT, y + 6), _fit(draw, lead, _font(30), span), font=_font(30), fill=SOFT)
    y += 50
    draw.text((LEFT, y + 6), _fit(draw, facts.get("kinds") or "", _font(26), span), font=_font(26), fill=LILAC)

    people = max(1, int(facts.get("people") or 1))
    drawn = min(people, BOXES_DRAWN)
    size = 70
    gap = 34
    top = max(y + 76, 372)
    for index in range(drawn):
        x = LEFT + 8 + index * (size + gap)
        _box(draw, x, top, size, BOX_COLORS[index % len(BOX_COLORS)], GOLD)
    if people > drawn:
        draw.text((LEFT + 8 + drawn * (size + gap), top + size / 2 + 8), f"+{people - drawn}", font=_font(30, bold=True),
                  fill=MUTED, anchor="lm")

    baseline = HEIGHT - 132
    action = "Join the swap" if state == "open" else "Start your own"
    end = _pill(draw, LEFT, baseline, action, _font(26, bold=True), VIOLET, WHITE)
    who = f"Unwrap day {facts.get('reveal') or ''}"
    if people > 1:
        who += f" · {people} people in"
    draw.text((end + 24, baseline + 30), _fit(draw, who, _font(24), RIGHT - end - 260), font=_font(24),
              fill=GOLD if people > 1 else LILAC, anchor="lm")
    brand = "omnitrackr.xyz"
    brand_font = _font(24, bold=True)
    draw.text((RIGHT - draw.textlength(brand, font=brand_font), baseline + 30), brand, font=brand_font, fill=WHITE,
              anchor="lm")
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
