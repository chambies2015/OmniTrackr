"""A shared break plan (/break/s/<token>): planning the same days from it, and its two pictures.

The link itself lives on the plan (break_plans.share_token, see break_plan.share_on). Whoever
opens it sees the plan from the shelves its owner shares publicly. A member can start their own
plan from it at /break?from=<token>: the same days (from today on), the planner's own time
defaults, and any of the plan's titles they tick going in first. Titles they don't have yet are
added to their library with public details only, the same as "+ Add to my list" on a title
page. Nothing else from the owner's library is read, and nothing in it changes.

The pictures are drawn with Pillow from what the share page shows: a 1200x630 card that chat
apps show (up to six covers, each with the day it's planned for) and a 1080x1920 picture for
stories (the plan day by day). Covers only come from the hosts the tier list image proxy
allows (tier_list.image_allowed), because a library cover can be any address a member typed.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from io import BytesIO
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import break_plan, models, ranking_shares, title_pages

CARD_SHOWN = 6         # covers on the link card
STORY_DAYS = 4         # day rows on the story picture
STORY_PER_DAY = 4      # covers on one day row
POSTERS_MAX = 16       # covers fetched for one picture


# ---------------------------------------------------------------- starting a plan from a shared one

def _in_library(db: Session, user: models.User, titles: list[dict]) -> dict[int, str]:
    """index -> "open" or "finished" for the shared titles the member already has (matched by name)."""
    found: dict[int, str] = {}
    by_category: dict[str, dict[str, list[int]]] = {}
    for entry in titles:
        by_category.setdefault(entry["category"], {}).setdefault(title_pages.normalize(entry["title"]), []).append(entry["index"])
    for category, names in by_category.items():
        kind = title_pages.LIBRARY_TO_KIND[category]
        model = title_pages.KINDS[kind][0]
        done_field = title_pages.COMPLETE_FIELD[kind]
        wanted = sorted({name.lower() for name in names})
        rows = db.query(model.title, getattr(model, done_field)).filter(
            model.user_id == user.id, func.lower(func.trim(model.title)).in_(wanted)).all()
        for title, done in rows:
            for index in names.get(title_pages.normalize(title or ""), []):
                if found.get(index) != "open":
                    found[index] = "finished" if done else "open"
    return found


def from_link(db: Session, user: models.User, token: str, today: date) -> dict:
    """What /break?from=<token> shows a member: the plan's days and titles, and which ones they have."""
    plan = break_plan.by_token(db, token, today)
    if plan is None:
        raise break_plan.BreakError("This plan isn't shared anymore. You can still plan your own break.", 404)
    view = break_plan.shared_view(db, plan, today)
    own = plan.user_id == user.id
    mine = _in_library(db, user, view["titles"]) if not own else {}
    current = break_plan.active(db, user.id, today)
    titles = [{"kind": entry["kind"], "slug": entry["slug"], "title": entry["title"], "year": entry["year"],
               "image": entry["image"], "kind_label": entry["kind_label"], "category": entry["category"],
               "when": entry["when"], "url": entry["url"], "mine": mine.get(entry["index"])}
              for entry in view["titles"]]
    if not own:
        break_plan.count("break_from_link_started")
    return {"token": token, "own": own, "by": view["by"], "name": view["name"], "span": view["span"],
            "days": break_plan.same_days(plan, today), "titles": titles, "max_picks": break_plan.MAX_PICKS,
            "has_plan": current is not None and current.ends_on >= today}


def take_titles(db: Session, user: models.User, token: str, wanted: Iterable[tuple[str, str]],
                today: date) -> tuple[list[tuple[str, int]], bool]:
    """(library refs, from someone else's plan) for a plan started from a shared one.

    The refs are the titles the member ticked, added to their library first when they don't have them.
    Only titles the link shows count. A link that stopped working only matters when titles were ticked
    from it. Doesn't commit: the new plan and these titles save together.
    """
    from .routers.titles import add_group_to_library
    wanted = list(dict.fromkeys(wanted))[:break_plan.MAX_PICKS]
    plan = break_plan.by_token(db, token, today)
    if plan is None:
        if wanted:
            raise break_plan.BreakError("The plan you started from isn't shared anymore, so its titles can't come "
                                        "across. Untick them to plan without them.", 404)
        return [], False
    if plan.user_id == user.id:
        return [], False
    offered = {(entry["kind"], entry["slug"]) for entry in break_plan.shared_view(db, plan, today)["titles"]}
    refs = []
    for kind, slug in wanted:
        if (kind, slug) not in offered:
            continue
        group = title_pages.find(db, kind, slug)
        if group is None:
            continue
        _state, record = add_group_to_library(db, user, group)
        if getattr(record, title_pages.COMPLETE_FIELD[kind], False):
            continue  # finished already: nothing to plan
        refs.append((title_pages.KINDS[kind][2], record.id))
    return refs, True


# ---------------------------------------------------------------- the pictures

CARD_W, CARD_H = ranking_shares.CARD_W, ranking_shares.CARD_H
STORY_W, STORY_H = ranking_shares.STORY_W, ranking_shares.STORY_H
BG, TEXT, SOFT, MUTED = ranking_shares.BG, ranking_shares.TEXT, ranking_shares.SOFT, ranking_shares.MUTED
GOLD = (245, 196, 81)
DONE = (52, 211, 153)
RULE = (46, 42, 72)


def fingerprint(facts: dict) -> str:
    return hashlib.sha256(json.dumps(facts, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def heading_words(facts: dict) -> str:
    """The eyebrow: "NOVA'S BREAK PLAN" with a public profile to name, otherwise "MY BREAK PLAN"."""
    return f"{facts['by']}'s break plan" if facts.get("by") else "My break plan"


def meta_line(facts: dict) -> str:
    titles = int(facts.get("titles") or 0)
    if facts.get("phase") == "after":
        finished = int(facts.get("finished") or 0)
        line = f"Got through {facts.get('done', 0)} of {facts.get('stretches', 0)}"
        return line + (f" · finished {finished} {'title' if finished == 1 else 'titles'}" if finished else "")
    if facts.get("phase") == "during":
        return (f"Day {facts.get('day_number')} of {facts.get('day_count')} · {facts.get('done', 0)} of "
                f"{facts.get('stretches', 0)} ticked off")
    days = int(facts.get("day_count") or 0)
    return (f"{titles} {'title' if titles == 1 else 'titles'} over {days} {'day' if days == 1 else 'days'} · "
            f"about {facts.get('hours')}")


def _stripes(draw, width: int, height: int, categories: list[str]) -> None:
    """The top bar in the colours of the formats on the plan."""
    colours = [ranking_shares.ACCENTS.get(category, GOLD) for category in dict.fromkeys(categories)] or [GOLD]
    step = width / len(colours)
    for index, colour in enumerate(colours):
        draw.rectangle((round(index * step), 0, round((index + 1) * step), height), fill=colour)


def _art(image, draw, box, shown: list, place: int, posters: dict, font) -> None:
    title, _image, _when, _done, _finished, category = shown[place - 1]
    accent = ranking_shares.ACCENTS.get(category, GOLD)
    ranking_shares._tile(image, draw, box, {"title": title, "position": place}, accent, posters, font)


def _tick(draw, x: int, y: int, size: int) -> None:
    """A round green tick for a title that's done."""
    draw.ellipse((x, y, x + size, y + size), fill=DONE)
    width = max(2, size // 9)
    draw.line([(x + size * .27, y + size * .52), (x + size * .44, y + size * .69), (x + size * .74, y + size * .33)],
              fill=BG, width=width, joint="curve")


def render_card(facts: dict, posters: dict) -> bytes:
    """The 1200x630 link preview: the plan's name, then up to six covers with the day each one is on."""
    from PIL import Image, ImageDraw
    from .routers.profiles import _fit, _font
    image = Image.new("RGB", (CARD_W, CARD_H), BG)
    draw = ImageDraw.Draw(image)
    shown = facts.get("shown") or []
    _stripes(draw, CARD_W, 8, [entry[5] for entry in shown[:CARD_SHOWN]])
    pad = 44
    eyebrow_font = _font(19, bold=True)
    eyebrow = f"{heading_words(facts).upper()} · {str(facts.get('span') or '').upper()}"
    draw.text((pad, 32), _fit(draw, eyebrow, eyebrow_font, CARD_W - pad * 2), font=eyebrow_font, fill=GOLD)
    title_font = _font(44, bold=True)
    draw.text((pad, 60), _fit(draw, facts.get("name") or "A break", title_font, CARD_W - pad * 2), font=title_font, fill=TEXT)
    line_font = _font(20)
    draw.text((pad, 116), _fit(draw, meta_line(facts), line_font, CARD_W - pad * 2), font=line_font, fill=MUTED)

    columns, gap = CARD_SHOWN, 16
    cell = (CARD_W - pad * 2 + gap) // columns
    art_w, art_h = cell - gap, (cell - gap) * 3 // 2
    top = 160
    name_font, when_font, letter_font = _font(18, bold=True), _font(15, bold=True), _font(60, bold=True)
    for index, entry in enumerate(shown[:CARD_SHOWN]):
        title, _image, when, all_done, finished, _category = entry
        x = pad + index * cell
        _art(image, draw, (x, top, x + art_w, top + art_h), shown, index + 1, posters, letter_font)
        if all_done:
            _tick(draw, x + art_w - 40, top + 8, 32)
        draw.text((x, top + art_h + 12), _fit(draw, title, name_font, art_w), font=name_font, fill=TEXT)
        label = "Finished" if finished else ("Done" if all_done else when)
        draw.text((x, top + art_h + 38), _fit(draw, label, when_font, art_w), font=when_font,
                  fill=DONE if all_done else SOFT)
    if not shown:
        draw.text((pad, top + 40), "Titles from private shelves stay private.", font=_font(26), fill=SOFT)

    draw.line((pad, 534, CARD_W - pad, 534), fill=RULE, width=2)
    footer = _font(21, bold=True)
    draw.text((pad, 556), "Plan your own break from your list", font=footer, fill=SOFT)
    brand = "omnitrackr.xyz"
    draw.text((CARD_W - pad - draw.textlength(brand, font=footer), 556), brand, font=footer, fill=TEXT)
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def story_days(facts: dict) -> tuple[list[int], int]:
    """Which days the story shows (indexes into facts["days"]) and how many more have something on them.

    Days with something planned, from today on while the break is under way, at most STORY_DAYS.
    """
    planned = [index for index, entries in enumerate(facts.get("days") or []) if entries]
    if facts.get("phase") == "during" and facts.get("day_number"):
        ahead = [index for index in planned if index >= int(facts["day_number"]) - 1]
        planned = ahead or planned
    return planned[:STORY_DAYS], max(0, len(planned) - STORY_DAYS)


def render_story(facts: dict, posters: dict) -> bytes:
    """The 1080x1920 picture for stories: the plan's name, then day by day with the covers on each."""
    from PIL import Image, ImageDraw
    from .routers.profiles import _fit, _font
    image = Image.new("RGB", (STORY_W, STORY_H), BG)
    draw = ImageDraw.Draw(image)
    shown = facts.get("shown") or []
    _stripes(draw, STORY_W, 14, [entry[5] for entry in shown[:8]])
    pad = 84
    width = STORY_W - pad * 2
    # Stories cover the top and bottom with the app's own bars, so everything sits inside them.
    eyebrow_font = _font(30, bold=True)
    draw.text((pad, 150), _fit(draw, heading_words(facts).upper(), eyebrow_font, width), font=eyebrow_font, fill=GOLD)
    head_font = _font(68, bold=True)
    lines = ranking_shares._wrap(draw, facts.get("name") or "A break", head_font, width, 2)
    for number, line in enumerate(lines):
        draw.text((pad, 196 + number * 80), line, font=head_font, fill=TEXT)
    y = 196 + len(lines) * 80 + 14
    span_font = _font(34, bold=True)
    draw.text((pad, y), _fit(draw, str(facts.get("span") or ""), span_font, width), font=span_font, fill=SOFT)
    y += 52
    line_font = _font(30)
    draw.text((pad, y), _fit(draw, meta_line(facts), line_font, width), font=line_font, fill=MUTED)
    y += 86

    rows, more = story_days(facts)
    labels = facts.get("day_labels") or []
    days = facts.get("days") or []
    label_w = 170
    gap = 22
    art_w = (width - label_w - gap * (STORY_PER_DAY - 1)) // STORY_PER_DAY
    art_h = art_w * 3 // 2
    # Every row has to end above the footer, so with more days the covers get smaller.
    room = STORY_H - 300 - (56 if more else 0) - y
    if rows:
        art_h = max(120, min(art_h, int(room / len(rows)) - 92))
        art_w = art_h * 2 // 3
    row_h = art_h + 92
    day_font, date_font, name_font, letter_font = _font(44, bold=True), _font(28), _font(22, bold=True), _font(80, bold=True)
    done_counts = facts.get("done_days") or []
    for row, day_index in enumerate(rows):
        top = y + row * row_h
        weekday, when = labels[day_index] if day_index < len(labels) else ("", "")
        draw.text((pad, top + 4), weekday, font=day_font, fill=TEXT)
        draw.text((pad, top + 60), when, font=date_font, fill=MUTED)
        entries = list(dict.fromkeys(days[day_index]))
        planned = len(days[day_index])
        if planned and day_index < len(done_counts) and done_counts[day_index] >= planned:
            _tick(draw, pad, top + 110, 40)
        for slot, index in enumerate(entries[:STORY_PER_DAY]):
            x = pad + label_w + slot * (art_w + gap)
            if slot == STORY_PER_DAY - 1 and len(entries) > STORY_PER_DAY:
                draw.rounded_rectangle((x, top, x + art_w, top + art_h), radius=12, fill=ranking_shares.PANEL)
                extra = f"+{len(entries) - STORY_PER_DAY + 1}"
                extra_font = _font(56, bold=True)
                draw.text((x + (art_w - draw.textlength(extra, font=extra_font)) / 2, top + art_h / 2 - 34), extra,
                          font=extra_font, fill=SOFT)
                continue
            if index >= len(shown):
                continue
            _art(image, draw, (x, top, x + art_w, top + art_h), shown, index + 1, posters, letter_font)
            if shown[index][3]:
                _tick(draw, x + art_w - 46, top + 10, 36)
            draw.text((x, top + art_h + 14), _fit(draw, shown[index][0], name_font, art_w), font=name_font, fill=SOFT)
        if row < len(rows) - 1:
            draw.line((pad, top + row_h - 22, STORY_W - pad, top + row_h - 22), fill=RULE, width=2)
    if not rows:
        draw.text((pad, y), "Titles from private shelves stay private.", font=_font(34), fill=SOFT)
    if more:
        more_font = _font(32, bold=True)
        text = f"and {more} more {'day' if more == 1 else 'days'} on the plan"
        draw.text(((STORY_W - draw.textlength(text, font=more_font)) / 2, y + len(rows) * row_h + 2), text,
                  font=more_font, fill=SOFT)

    footer = _font(32, bold=True)
    ask = "Plan your own break from your list"
    draw.text(((STORY_W - draw.textlength(ask, font=footer)) / 2, STORY_H - 256), ask, font=footer, fill=SOFT)
    brand_font = _font(44, bold=True)
    brand = "omnitrackr.xyz"
    draw.text(((STORY_W - draw.textlength(brand, font=brand_font)) / 2, STORY_H - 208), brand, font=brand_font, fill=TEXT)
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def poster_urls(facts: dict, kind: str) -> dict[int, str]:
    """{place: cover address} for the titles a picture draws, only from hosts the image proxy allows."""
    from . import tier_list
    shown = facts.get("shown") or []
    if kind == "story":
        rows, _ = story_days(facts)
        wanted = []
        for day_index in rows:
            wanted += list(dict.fromkeys(facts["days"][day_index]))[:STORY_PER_DAY]
        places = [index + 1 for index in dict.fromkeys(wanted)]
    else:
        places = list(range(1, min(CARD_SHOWN, len(shown)) + 1))
    found = {}
    for place in places[:POSTERS_MAX]:
        if place > len(shown):
            continue
        url = shown[place - 1][1]
        if url and tier_list.image_allowed(url):
            found[place] = url
    return found
