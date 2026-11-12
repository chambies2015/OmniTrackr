"""The 1200x630 image chat apps show for a group poll link (/tonight/<token>/card.png).

An open poll's card is a ballot: the question and the titles, with no counts, so it
reads the same from the first vote to the last. Once voting closes the card names
the winner. Text only, drawn with Pillow like the other share cards.
"""
from __future__ import annotations

from io import BytesIO

BACKGROUND = (11, 10, 24)
WHITE = (245, 243, 255)
SOFT = (236, 233, 252)
MUTED = (148, 140, 190)
VIOLET = (139, 92, 246)
LILAC = (196, 181, 253)
TEAL = (94, 234, 212)
GOLD = (251, 191, 36)
EDGE = (60, 52, 110)
ROW = (24, 22, 50)
WIDTH, HEIGHT = 1200, 630
LEFT, RIGHT = 84, WIDTH - 84
ROWS_SHOWN = 4


def _glow(image, center, rgb, strength):
    from PIL import Image, ImageDraw
    layer = Image.new("RGB", image.size, BACKGROUND)
    draw = ImageDraw.Draw(layer)
    for step in range(18, 0, -1):
        radius, mix = step * 34, (1 - step / 18) * 0.55
        shade = tuple(int(base + (color - base) * mix) for base, color in zip(BACKGROUND, rgb))
        draw.ellipse((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), fill=shade)
    return Image.blend(image, layer, strength)


def _wrap(draw, text: str, font, width: int, lines_max: int) -> list[str]:
    from .routers.profiles import _fit
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    if len(lines) > lines_max:
        lines = lines[:lines_max - 1] + [" ".join(lines[lines_max - 1:])]
    return [_fit(draw, entry, font, width) for entry in lines]


def _pill(draw, x: int, y: int, text: str, font, fill, color) -> int:
    width = int(draw.textlength(text, font=font)) + 56
    draw.rounded_rectangle((x, y, x + width, y + 60), radius=30, fill=fill)
    draw.text((x + 28, y + 30), text, font=font, fill=color, anchor="lm")
    return x + width


def _meta(label: str, year) -> str:
    return f"{label} · {year}" if year else label


def render(facts: dict) -> bytes:
    """PNG bytes for one poll. ``facts`` comes from tonight_polls.card_facts."""
    from PIL import Image, ImageDraw
    from .routers.profiles import _fit, _font
    winner = facts.get("winner")
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    image = _glow(image, (WIDTH - 120, -60), GOLD if winner else VIOLET, 0.8)
    image = _glow(image, (60, HEIGHT + 220), (45, 212, 191), 0.35)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, WIDTH - 40, HEIGHT - 40), radius=28, outline=EDGE, width=2)
    span = RIGHT - LEFT
    owner = facts["owner"]
    small, label_font = _font(24), _font(22)

    if winner:
        title, kind, year = winner
        draw.text((LEFT, 78), "GROUP POLL · THE VOTES ARE IN", font=_font(26, bold=True), fill=GOLD)
        draw.text((LEFT, 128), _fit(draw, facts["question"], _font(34), span), font=_font(34), fill=LILAC)
        big = _font(84, bold=True)
        lines = _wrap(draw, title, big, span, 2)
        if len(lines) == 2:
            big = _font(68, bold=True)
            lines = _wrap(draw, title, big, span, 2)
        y = 196
        for line in lines:
            draw.text((LEFT, y), line, font=big, fill=WHITE)
            y += big.size + 14
        votes, total = facts["winner_votes"], facts["total"]
        tally = f"{votes} of {total} vote{'' if total == 1 else 's'}"
        draw.text((LEFT, y + 10), f"{_meta(kind, year)} · {tally}", font=_font(30), fill=SOFT)
        others = [name for _, name, _ in facts["options"] if name != title]
        if others and y < 380:
            beat = "Ahead of " + (others[0] if len(others) == 1 else f"{', '.join(others[:-1])} and {others[-1]}")
            draw.text((LEFT, y + 62), _fit(draw, beat, small, span), font=small, fill=MUTED)
        action = "See how the vote went"
    else:
        closed = facts["closed"]
        eyebrow = f"GROUP POLL · {owner.upper()} ASKED" if closed else f"GROUP POLL · {owner.upper()} WANTS YOUR VOTE"
        draw.text((LEFT, 78), _fit(draw, eyebrow, _font(26, bold=True), span), font=_font(26, bold=True), fill=TEAL)
        question_font, step = _font(58, bold=True), 70
        lines = _wrap(draw, facts["question"], question_font, span, 2)
        if len(lines) == 2:
            # A long question gets smaller type so three titles still fit under it.
            question_font, step = _font(50, bold=True), 60
            lines = _wrap(draw, facts["question"], question_font, span, 2)
        y = 122
        for line in lines:
            draw.text((LEFT, y), line, font=question_font, fill=WHITE)
            y += step
        y += 18
        options = facts["options"]
        room = ROWS_SHOWN if len(lines) == 1 else ROWS_SHOWN - 1
        shown = options if len(options) <= room else options[:room - 1]
        row_font = _font(30, bold=True)
        for label, title, year in shown:
            draw.rounded_rectangle((LEFT, y, RIGHT, y + 58), radius=16, fill=ROW, outline=EDGE, width=2)
            draw.ellipse((LEFT + 20, y + 15, LEFT + 48, y + 43), outline=LILAC, width=3)
            meta = _meta(label, year).upper()
            meta_width = draw.textlength(meta, font=label_font)
            draw.text((LEFT + 68, y + 29), _fit(draw, title, row_font, span - 68 - meta_width - 48), font=row_font,
                      fill=SOFT, anchor="lm")
            draw.text((RIGHT - 24 - meta_width, y + 29), meta, font=label_font, fill=MUTED, anchor="lm")
            y += 68
        if len(options) > len(shown):
            draw.text((LEFT + 68, y + 6), f"+ {len(options) - len(shown)} more to choose from", font=small, fill=MUTED)
        action = "Voting has closed" if closed else "Tap to vote"

    baseline = HEIGHT - 132
    end = _pill(draw, LEFT, baseline, action, _font(26, bold=True), VIOLET if not facts["closed"] or winner else EDGE, WHITE)
    if not facts["closed"]:
        draw.text((end + 24, baseline + 30), "No account needed", font=small, fill=LILAC, anchor="lm")
    brand = "omnitrackr.xyz"
    brand_font = _font(24, bold=True)
    draw.text((RIGHT - draw.textlength(brand, font=brand_font), baseline + 30), brand, font=brand_font, fill=WHITE, anchor="lm")
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
