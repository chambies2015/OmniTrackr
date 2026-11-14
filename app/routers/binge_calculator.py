"""Public binge calculator (/binge-calculator), its "how long" guides and member helpers.

The hub is a free calculator plus a shelf of guides. Each guide page answers
"how long does it take to watch or read X" from hand-checked lengths, reads
completely without scripts, and adds a planner when scripts run. Members see
their own progress and time left; visitors can keep a series on their
browser-only guest list until they sign up.
"""
from __future__ import annotations

import json
from datetime import date
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from .. import binge_calculator as binge
from .. import funnel, in_order, title_pages, title_search
from ..auth import AUTH_COOKIE_NAME
from ..binge_guides import FIRST_PUBLISHED, GUIDES
from ..dependencies import get_current_user, get_db
from ..progress import lock_progress_owner
from .discover import page

router = APIRouter(tags=["binge-calculator"])
CSS_VERSION = "20261110-binge-2"
JS_VERSION = "20261112-sweep-1"
GUEST_LIST_JS = "/static/guest-list.js?v=20261031-browse-1"
SITE = "https://omnitrackr.xyz"
TITLE = "Binge calculator: how long to watch a show or read a series"
DESCRIPTION = ("Work out how many hours a TV show, anime, film series or book series takes and the date you'll finish at "
               "your own pace. Season-by-season guides for Breaking Bad, One Piece, Harry Potter and more.")
PART_WORDS = {"tv": ("season", "seasons"), "anime": ("part", "parts"), "book": ("book", "books"), "film": ("film", "films")}
PART_HEADINGS = {"tv": "Season by season", "anime": "Part by part", "book": "Book by book", "film": "Film by film"}


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _paragraphs(values) -> str:
    return "".join(f"<p>{_e(value)}</p>" for value in values)


def _long_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%B %d, %Y").replace(" 0", " ")


def _plural(number: int, word: str) -> str:
    return f"{number:,} {word}" if number == 1 else f"{number:,} {word}s"


def _hours(minutes: float) -> str:
    """Hours as a headline number: one decimal under ten hours, whole hours above."""
    hours = minutes / 60
    return f"{hours:.1f}".rstrip("0").rstrip(".") if hours < 10 else f"{round(hours):,}"


def _clock(minutes: float) -> str:
    """Exact hours and minutes, for film running times."""
    hours, rest = divmod(round(minutes), 60)
    if not hours:
        return f"{rest} min"
    return f"{hours} h {rest} min" if rest else f"{hours} h"


def _nonstop(minutes: float) -> str:
    hours = minutes / 60
    if hours < 24:
        return f"{_hours(minutes)} hours"
    days, rest = divmod(round(hours), 24)
    return _plural(days, "day") + (f" {_plural(rest, 'hour')}" if rest else "")


def _days(days: int) -> str:
    return _plural(days, "day")


def _length_line(entry: dict) -> str:
    """One sentence that says what the headline total is made of."""
    kind, sums = entry["kind"], binge.totals(entry)
    singular, plural = PART_WORDS[kind]
    if kind == "book":
        return (f"{sums['words']:,} words across {_plural(sums['parts'], 'book')}, about {sums['pages']:,} pages "
                f"at {binge.WORDS_PER_PAGE} words a page.")
    if kind == "film":
        return f"{_plural(sums['parts'], 'film')}, {round(sums['minutes']):,} minutes with credits."
    parts = [part for part in binge.core(entry) if binge.unit(entry, part) == "episode"]
    line = f"{_plural(sums['episodes'], 'episode')}"
    if len(parts) > 1:
        line += f" across {len(parts)} {plural}"
    if sums["extras"]:
        line += f", plus {_plural(sums['extras'], 'feature-length special')}"
    return line + ("." if not entry.get("ongoing") else " so far.")


def _answer(entry: dict) -> str:
    kind, sums = entry["kind"], binge.totals(entry)
    minutes = sums["minutes"]
    figures = [("To " + binge.VERBS[kind], minutes, "")]
    if kind == "book":
        figures.append(("To listen", sums["audio"], "at normal speed"))
    if entry.get("alt"):
        figures[0] = ("Theatrical cuts" if kind == "film" else "Every episode", minutes, "")
        figures.append((entry["alt"]["label"], binge.totals(entry, alt=True)["minutes"], ""))
    totals_html = "".join(
        f'<div class="bc-answer__figure"><dt>{_e(label)}</dt>'
        f'<dd><strong>{_e(_clock(value) if kind == "film" else _hours(value))}</strong>'
        f'{"" if kind == "film" else " hours"}{f"<small>{_e(note)}</small>" if note else ""}</dd></div>'
        for label, value, note in figures)
    paces = "".join(f"<div><dt>{pace} hour{'s' if pace != 1 else ''} a day</dt><dd>{_days(binge.days_at(minutes, pace))}</dd></div>"
                    for pace in binge.PACES)
    return (
        '<section class="bc-answer" id="answer" aria-labelledby="answer-heading">'
        '<p class="eyebrow">THE SHORT ANSWER</p>'
        f'<h2 id="answer-heading" class="bc-answer__heading">{_e(binge.card_name(entry)[:1].upper() + binge.card_name(entry)[1:])} takes '
        f'{"about " if kind != "film" else ""}{_e(_clock(minutes) if kind == "film" else _hours(minutes) + " hours")}'
        f'{" so far" if entry.get("ongoing") else ""}</h2>'
        f'<dl class="bc-answer__figures">{totals_html}</dl>'
        f'<p class="bc-answer__line">{_e(_length_line(entry))}</p>'
        f'<dl class="bc-paces">{paces}<div><dt>Without stopping</dt><dd>{_e(_nonstop(minutes))}</dd></div></dl>'
        '</section>'
    )


def _part_meta(entry: dict, part: dict) -> str:
    kind = entry["kind"]
    if kind == "book":
        return f"{part['words']:,} words{' (estimate)' if part.get('approx') else ''} · about {binge.pages(part):,} pages"
    if kind == "film":
        text = f"{part['year']} · {part['minutes']} min"
        return text + (f" · {part['alt']} min extended" if part.get("alt") else "")
    item = binge.unit(entry, part)
    if item != "episode":
        return f"{_plural(binge.count(part), item)} · {part['total']} min"
    text = _plural(part["episodes"], "episode")
    if "minutes" in part:
        text += f" × {part['minutes']} min"
    if part.get("skip"):
        text += f" · about {part['skip']} filler"
    return text


def _part_time(entry: dict, part: dict) -> str:
    minutes = binge.minutes(entry, part)
    if entry["kind"] == "film":
        return _clock(minutes)
    text = f"{_hours(minutes)} h"
    if entry["kind"] == "book":
        text += f' <small>{_clock(part["audio"])} audio</small>'
    return text


def _parts_list(entry: dict) -> str:
    # A list, not a table: the shared public stylesheet restyles every table on phones.
    longest = max(binge.minutes(entry, part, alt=bool(part.get("alt"))) for part in entry["parts"])
    rows = []
    for index, part in enumerate(entry["parts"]):
        minutes = binge.minutes(entry, part)
        optional = bool(part.get("optional"))
        tag = '<span class="bc-tag">Optional</span>' if optional else ""
        note = f'<small class="bc-part__note">{_e(part["note"])}</small>' if part.get("note") else ""
        rows.append(
            f'<li class="bc-part{" is-optional" if optional else ""}" data-binge-part="{index}">'
            f'<label class="bc-part__label"><input type="checkbox" data-binge-check="{index}"{"" if optional else " checked"} hidden>'
            f'<span class="bc-part__text"><strong>{_e(part["name"])}{tag}</strong>'
            f'<span class="bc-part__meta">{_e(_part_meta(entry, part))}</span>{note}</span></label>'
            # A progress element sizes the bar without an inline style, which the page's CSP would block.
            f'<progress class="bc-part__bar" max="100" value="{round(100 * minutes / longest, 1)}" aria-hidden="true"></progress>'
            f'<span class="bc-part__time" data-binge-part-time>{_part_time(entry, part)}</span></li>'
        )
    return f'<ol class="bc-parts" data-binge-parts>{"".join(rows)}</ol>'


def _week_select() -> str:
    return ('<label>Days a week<select name="week"><option value="7">Every day</option><option value="5">Weekdays only</option>'
            '<option value="2">Weekends only</option><option value="3">Three days a week</option></select></label>')


def _pace_fields() -> str:
    """The "how much time do you have" half of a planner, shared by the hub and the guides."""
    return (
        '<fieldset class="bc-mode"><legend>Plan by</legend>'
        '<label><input type="radio" name="mode" value="time" checked> Time I have each day</label>'
        '<label><input type="radio" name="mode" value="date"> A date to finish by</label></fieldset>'
        '<div class="bc-fields">'
        '<label data-binge-when="time">Hours a day<input type="number" name="hours" min="0.25" max="24" step="0.25" inputmode="decimal" value="2"></label>'
        '<label data-binge-when="date" hidden>Finish by<input type="date" name="by"></label>'
        + _week_select() +
        '<label>Starting<input type="date" name="start"></label></div>'
    )


def _result(name: str, hours: str, finish: str, detail: str) -> str:
    return (
        '<div class="bc-result" data-binge-result role="status" aria-live="polite">'
        f'<p class="bc-result__name" data-binge-name>{_e(name)}</p>'
        f'<p class="bc-result__total"><strong data-binge-hours>{_e(hours)}</strong> <span data-binge-hours-unit>hours</span></p>'
        f'<p class="bc-result__finish" data-binge-finish>{_e(finish)}</p>'
        f'<p class="muted" data-binge-detail>{_e(detail)}</p>'
        '<div class="bc-result__actions" data-binge-actions hidden>'
        '<button type="button" class="bc-link-button" data-binge-copy>Copy a link to this plan</button>'
        '<button type="button" class="bc-link-button" data-binge-calendar>Add the finish date to my calendar</button></div>'
        '<p class="bc-result__status" data-binge-copied role="status" aria-live="polite"></p></div>'
    )


def _guide_planner(entry: dict) -> str:
    kind = entry["kind"]
    sums = binge.totals(entry)
    options = []
    if kind == "book":
        options.append(
            '<fieldset class="bc-mode"><legend>How</legend>'
            '<label><input type="radio" name="how" value="read" checked> Reading</label>'
            '<label><input type="radio" name="how" value="listen"> Listening</label></fieldset>'
            '<div class="bc-fields">'
            f'<label data-binge-how="read">Pages an hour<input type="number" name="pace" min="5" max="200" inputmode="numeric" value="{binge.PAGES_PER_HOUR}"></label>'
            '<label data-binge-how="listen" hidden>Playback speed<select name="speed"><option value="1">1x</option>'
            '<option value="1.25">1.25x</option><option value="1.5">1.5x</option><option value="1.75">1.75x</option>'
            '<option value="2">2x</option></select></label></div>')
    if entry.get("alt"):
        options.append(f'<label class="bc-check"><input type="checkbox" name="alt"> {_e(entry["alt"]["label"])}'
                       f'<small>{_e(entry["alt"]["note"])}</small></label>')
    skip = entry.get("skip_minutes", binge.SKIP_MINUTES.get(kind, 0))
    if skip:
        what = "openings, endings and recaps" if kind == "anime" else "intros, recaps and credits"
        options.append(f'<label class="bc-check"><input type="checkbox" name="skip"> Skip {what}'
                       f'<small>About {_plural(skip, "minute")} off each episode.</small></label>')
    if kind in ("tv", "anime"):
        options.append(
            f'<div class="bc-fields"><label>Episodes you have already seen<input type="number" name="seen" min="0" '
            f'max="{sums["episodes"]}" inputmode="numeric" placeholder="0"></label></div>')
    payload = json.dumps(binge.planner(entry), ensure_ascii=False, separators=(",", ":"))
    hint = {"book": "Untick the books you have read", "film": "Untick the films you have seen"}.get(
        kind, "Untick what you have finished, or type how many episodes you have seen")
    daily = binge.days_at(sums["minutes"], 2)
    return (
        f'<section class="bc-tool bc-tool--guide" id="plan" data-binge-plan="{_e(payload)}" aria-labelledby="plan-heading">'
        '<div class="bc-tool__main"><p class="eyebrow">PLAN IT</p>'
        f'<h2 id="plan-heading">When would you finish?</h2>'
        '<form class="bc-form" data-binge-form novalidate>'
        + "".join(options) + _pace_fields() + '</form></div>'
        + _result(binge.card_name(entry), _hours(sums["minutes"]),
                  f"At 2 hours a day, that is {_days(daily)}.", _length_line(entry))
        + f'<div class="bc-tool__parts"><h3 id="breakdown">{PART_HEADINGS[kind]}</h3>'
        f'<p class="bc-tool__hint" data-binge-hint hidden>{_e(hint)} and the plan counts only what is left.</p>'
        + _parts_list(entry) + '</div>'
        '<noscript><p class="muted">The planner needs JavaScript. The lengths above and the pace table do not.</p></noscript>'
        '</section>'
    )


def _track_panel(slug: str, entry: dict, signed_in: bool) -> str:
    kind = entry["kind"]
    items = [item for item in binge.titles(entry) if not item["optional"]]
    what = (f"all {len(items)} {PART_WORDS[kind][1]}" if len(items) > 1 else binge.card_name(entry))
    if signed_in:
        # Filled in from the member's own library by binge-calculator.js.
        return (f'<section class="bc-track" data-binge-track="{_e(slug)}" aria-labelledby="track-heading" hidden>'
                '<p class="eyebrow">YOUR LIBRARY</p><h2 id="track-heading" data-binge-track-title>Your progress</h2>'
                '<p data-binge-track-text></p>'
                '<div class="bc-track__actions"><button type="button" class="button" data-binge-add hidden></button></div>'
                '<p class="bc-track__status" data-binge-track-status role="status" aria-live="polite"></p></section>')
    buttons = "".join(
        f'<button type="button" hidden data-guest-kind="{_e(fields["kind"])}" data-guest-slug="{_e(fields["slug"])}" '
        f'data-guest-title="{_e(fields["title"])}"></button>' for fields in map(binge.saveable, items))
    doing = "reading" if kind == "book" else "watching"
    return (
        '<section class="bc-track bc-track--guest" aria-labelledby="track-heading"><p class="eyebrow">TRACK IT</p>'
        f'<h2 id="track-heading">Keep your place while you are {doing}</h2>'
        f'<p>Save {_e(what)} to a list now, no account needed. Create a free OmniTrackr account and '
        f'{"they move" if len(items) > 1 else "it moves"} into your library, where you can tick off '
        f'{"episodes" if kind in ("tv", "anime") else PART_WORDS[kind][1]} as you go and this page shows the time you have left.</p>'
        f'<div class="bc-track__actions" data-binge-guest>{buttons}'
        f'<button type="button" class="button" data-binge-guest-save>Save {_e(what)} to my list</button>'
        '<a href="/#signup" class="bc-track__link">Create a free account</a></div>'
        '<p class="bc-track__status" data-binge-track-status role="status" aria-live="polite"></p></section>'
        '<div class="bc-bar" data-guest-bar hidden><p class="bc-bar__count" data-guest-count role="status" aria-live="polite"></p>'
        '<a class="button" href="/#signup">Save my list, free →</a></div>'
    )


def _title_link(entry: dict, details: dict) -> str:
    items = binge.titles(entry)
    if len(items) != 1:
        return ""
    detail = details.get(binge.saveable(items[0])["id"])
    if not detail:
        return ""
    return f' · <a href="{_e(detail["url"])}">{_e(items[0]["title"])} on OmniTrackr</a>'


def _method(entry: dict) -> str:
    kind = entry["kind"]
    if kind == "book":
        counted = (f"Reading time starts from each book's word count, turned into pages at {binge.WORDS_PER_PAGE} words a "
                   f"page and read at {binge.PAGES_PER_HOUR} pages an hour, which is about {binge.WORDS_PER_MINUTE} words a "
                   f"minute. Page counts differ between editions, which is why the page starts from words. "
                   f"{entry['audio']['note']} Lengths are as listed by Audible when the page was checked.")
    elif kind == "film":
        counted = ("Running times are the theatrical versions with credits, as listed on each film's Wikipedia page "
                   "when this page was checked, unless the page says otherwise. Disc and streaming versions can differ "
                   "by a minute or two.")
    else:
        counted = ("Episode counts are for the original broadcast and were checked against TVmaze. Where a part shows "
                   "episodes times minutes, the minutes are a typical episode on a streaming copy without ad breaks, "
                   "opening and credits included. Where it shows only a total, we added up the listed running time of "
                   "each episode. Either way the result is an estimate, good to within a few percent.")
    return (
        '<section id="method" class="guide-sources bc-method" aria-labelledby="method-heading">'
        '<h2 id="method-heading">How we counted</h2>'
        f'<p>{_e(counted)}</p>'
        '<p>The finish date counts the start day as day one and only the days of the week you choose. Prepared by '
        'OmniTrackr and reviewed by the site owner before publishing. If a number here is wrong, tell us and we will fix it.</p>'
        f'<p class="muted">First published {_e(_long_date(FIRST_PUBLISHED))}. Checked {_e(_long_date(entry["reviewed"]))}. '
        '<a href="/contact">Send a correction or suggest a series</a> · <a href="/content-quality">Editorial standards</a></p>'
        '</section>'
    )


def _related(slug: str, entry: dict, details: dict) -> str:
    cards = []
    for other in entry.get("see_also", ()):
        target = GUIDES[other]
        cards.append(f'<article><h3><a href="{binge.path(other)}">{_e(binge.heading(target))}</a></h3>'
                     f'<p>{_e(_card_line(target))}</p></article>')
    if entry.get("in_order") and in_order.guide(entry["in_order"]):
        target = in_order.guide(entry["in_order"])
        cards.append(f'<article><h3><a href="{in_order.path(entry["in_order"])}">{_e(target["name"])} in order</a></h3>'
                     f'<p>{_e(target["summary"])}</p></article>')
    return (
        '<section class="guide-related" aria-labelledby="related-heading"><p class="eyebrow">KEEP GOING</p>'
        f'<h2 id="related-heading">How long is the next one?</h2><div class="guide-related-grid">{"".join(cards)}</div>'
        f'<p class="bc-related__more"><a href="{binge.BASE_PATH}">Every series in the binge calculator</a>'
        f'{_title_link(entry, details)}</p></section>'
    )


def _card_line(entry: dict) -> str:
    kind, sums = entry["kind"], binge.totals(entry)
    if kind == "book":
        return f"{_plural(sums['parts'], 'book')} · about {_hours(sums['minutes'])} hours to read, {_hours(sums['audio'])} to listen"
    if kind == "film":
        return f"{_plural(sums['parts'], 'film')} · {_clock(sums['minutes'])}"
    return f"{_plural(sums['episodes'], 'episode')} · about {_hours(sums['minutes'])} hours{' so far' if entry.get('ongoing') else ''}"


TITLE_ROOM = 62  # what a search result shows before it cuts the title off (the Discover guides keep to it too)


def page_title(entry: dict) -> str:
    """The question and its answer, short enough that a search result shows the answer.

    The full question is used when it fits. A long series name gets the shorter
    "How long to watch ..." so the hours are not the part that is cut off.
    """
    kind, total = entry["kind"], binge.totals(entry)["minutes"]
    answer = _clock(total) if kind == "film" else f"About {_hours(total)} hours{' so far' if entry.get('ongoing') else ''}"
    short = f"How long to {binge.VERBS[kind]} {entry['name']}?"
    choices = (f"{binge.heading(entry).rstrip('?')}? {answer}", f"{short} {answer}", f"{short} {answer.removeprefix('About ')}")
    return next((title for title in choices if len(title) <= TITLE_ROOM), choices[-1])


def guide_content(slug: str, entry: dict, details: dict, signed_in: bool) -> str:
    kind = entry["kind"]
    reviewed = entry["reviewed"]
    jump = [("#answer", "The short answer"), ("#plan", "Plan it"), ("#breakdown", PART_HEADINGS[kind])]
    jump += [(f"#{section_id}", title) for section_id, title, _ in entry["sections"]]
    jump += [("#questions", "Questions"), ("#method", "How we counted")]
    parts = [
        '<article class="trail-guide bc-guide">',
        f'<header class="hero hero--guide"><a href="{binge.BASE_PATH}">← Binge calculator</a>',
        f'<p class="eyebrow">HOW LONG · {_e(binge.KIND_LABELS[kind].upper())}</p>',
        f'<h1>{_e(binge.heading(entry))}</h1><p class="guide-deck">{_e(entry["summary"])}</p>',
        '<p class="guide-byline">By <a href="/about">OmniTrackr</a> · Updated ',
        f'<time datetime="{_e(reviewed)}">{_e(_long_date(reviewed))}</time></p>',
        '<nav class="guide-jump" aria-label="On this page">',
        "".join(f'<a href="{href}">{_e(label)}</a>' for href, label in jump),
        '</nav></header>',
        _answer(entry),
        f'<div class="guide-intro">{_paragraphs(entry["lead"])}</div>',
        _guide_planner(entry),
        _track_panel(slug, entry, signed_in),
    ]
    for section_id, title, paragraphs in entry["sections"]:
        parts.append(f'<section id="{_e(section_id)}" class="editorial bc-notes"><h2>{_e(title)}</h2>{_paragraphs(paragraphs)}</section>')
    parts.append('<section id="questions" class="bc-questions" aria-labelledby="questions-heading">'
                 '<h2 id="questions-heading">Questions</h2>')
    for question, answer in entry["faq"]:
        parts.append(f'<h3>{_e(question)}</h3><p>{_e(answer)}</p>')
    parts.extend(['</section>', _related(slug, entry, details), _method(entry), '</article>'])
    return "".join(parts)


def _guide_structured(slug: str, entry: dict) -> list:
    url = SITE + binge.path(slug)
    return [
        {"@context": "https://schema.org", "@type": "Article", "headline": binge.heading(entry),
         "description": entry["summary"], "datePublished": FIRST_PUBLISHED, "dateModified": entry["reviewed"],
         "mainEntityOfPage": url, "url": url, "inLanguage": "en-US",
         "author": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/about"},
         "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/"},
         "about": {"@type": "CreativeWorkSeries", "name": binge.card_name(entry)}},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": question, "acceptedAnswer": {"@type": "Answer", "text": answer}}
            for question, answer in entry["faq"]]},
    ]


_details_cache: dict = {"index": None, "details": None}


def _details(db: Session) -> dict:
    """{saveable id: {"url", "image"}} for guide titles with a public title page (never raises)."""
    try:
        index = title_search.index(db)
    except Exception:
        return {}
    # The index is one list that is swapped for a new one every ten minutes, so the
    # answer is kept until then and a guide page view no longer walks every title on the site.
    if _details_cache["index"] is index and _details_cache["details"] is not None:
        return _details_cache["details"]
    by_slug = {(row["kind"], row["slug"]): row for row in index}
    details = {}
    for entry in GUIDES.values():
        for item in binge.titles(entry):
            fields = binge.saveable(item)
            match = by_slug.get((fields["kind"], fields["slug"]))
            if match is not None:
                details[fields["id"]] = {"url": f"/titles/{match['kind']}/{match['slug']}", "image": match.get("image")}
    _details_cache["index"], _details_cache["details"] = index, details
    return details


def _head(signed_in: bool, guest_list: bool) -> str:
    head = f'<link rel="stylesheet" href="/static/binge-calculator.css?v={CSS_VERSION}">'
    if guest_list and not signed_in:
        head += f'<script src="{GUEST_LIST_JS}" defer></script>'
    head += f'<script src="/static/binge-calculator.js?v={JS_VERSION}" defer></script>'
    if not signed_in:
        head += '<script src="/static/ad-loader.js" defer></script>'
    return head


# ---------------------------------------------------------------- the hub

def _tool() -> str:
    kinds = (("screen", "A show or anime"), ("film", "Films"), ("book", "A book or series"),
             ("audio", "An audiobook or podcast"), ("game", "A game"))
    radios = "".join(f'<label><input type="radio" name="kind" value="{value}"{" checked" if index == 0 else ""}> {label}</label>'
                     for index, (value, label) in enumerate(kinds))
    return (
        '<section class="bc-tool" id="bingeTool" data-binge-custom aria-label="Binge calculator">'
        '<div class="bc-tool__main"><form class="bc-form" data-binge-form novalidate>'
        f'<fieldset class="bc-kind"><legend>What are you starting?</legend>{radios}</fieldset>'
        '<div class="bc-search"><label for="bcSearch">Look up a title members track</label>'
        '<input id="bcSearch" type="search" autocomplete="off" maxlength="80" placeholder="Try Severance, Frieren or Dune">'
        '<div class="bc-search__results" data-binge-results hidden></div>'
        '<p class="muted">Or type the numbers in yourself, or pick one of the series below.</p></div>'
        '<div class="bc-fields" data-binge-kind="screen">'
        '<label>Episodes<input type="number" name="episodes" min="1" max="20000" inputmode="numeric" value="62"></label>'
        '<label>Minutes per episode<input type="number" name="minutes" min="1" max="600" inputmode="numeric" value="47"></label></div>'
        '<div class="bc-fields" data-binge-kind="film" hidden>'
        '<label>Films<input type="number" name="films" min="1" max="500" inputmode="numeric" value="3"></label>'
        '<label>Minutes per film<input type="number" name="filmMinutes" min="1" max="600" inputmode="numeric" value="120"></label></div>'
        '<div class="bc-fields" data-binge-kind="book" hidden>'
        '<label>Pages<input type="number" name="pages" min="1" max="100000" inputmode="numeric" value="400"></label>'
        f'<label>Pages an hour<input type="number" name="pace" min="5" max="200" inputmode="numeric" value="{binge.PAGES_PER_HOUR}"></label></div>'
        '<div class="bc-fields" data-binge-kind="audio" hidden>'
        '<label>Length in hours<input type="number" name="audioHours" min="0.25" max="5000" step="0.25" inputmode="decimal" value="12"></label>'
        '<label>Playback speed<select name="speed"><option value="1">1x</option><option value="1.25">1.25x</option>'
        '<option value="1.5">1.5x</option><option value="1.75">1.75x</option><option value="2">2x</option></select></label></div>'
        '<div class="bc-fields" data-binge-kind="game" hidden>'
        '<label>Hours to finish<input type="number" name="gameHours" min="0.5" max="5000" step="0.5" inputmode="decimal" value="30"></label></div>'
        '<label class="bc-check" data-binge-kind="screen"><input type="checkbox" name="skip"> Skip intros and recaps'
        '<small>About 2 minutes off each episode.</small></label>'
        + _pace_fields() + '</form></div>'
        + _result("Breaking Bad", "48.6", "At 2 hours a day you would finish in 25 days.", "62 episodes at 47 minutes each.")
        + '<noscript><p>The calculator needs JavaScript. The series guides below are plain pages and work without it.</p></noscript>'
        '</section>'
    )


def _mine_panel(signed_in: bool) -> str:
    if signed_in:
        # Filled in from the member's own library by binge-calculator.js.
        return ('<section class="bc-mine" data-binge-mine aria-labelledby="mine-heading" hidden>'
                '<p class="eyebrow">FROM YOUR LIBRARY</p><h2 id="mine-heading">What you have left</h2>'
                '<p class="bc-mine__summary" data-binge-mine-summary></p>'
                '<ul class="bc-mine__list" data-binge-mine-list></ul>'
                '<p class="muted" data-binge-mine-note></p></section>')
    return (
        '<section class="bc-mine bc-mine--guest" aria-labelledby="mine-heading"><div>'
        '<p class="eyebrow">WITH A FREE ACCOUNT</p><h2 id="mine-heading">See what your whole list adds up to</h2>'
        '<p>Members get this page filled in from their own library: every show, book and game they have not finished, '
        'the hours each one has left, and a plan for any of them in one tap. Tick off episodes as you watch and the '
        'numbers keep up.</p></div>'
        '<a class="button" href="/#signup">Start tracking, free →</a></section>'
    )


def _guide_cards(kind: str) -> str:
    cards = []
    for slug in binge.by_kind()[kind]:
        entry = GUIDES[slug]
        sums = binge.totals(entry)
        load = (f'data-kind="book" data-pages="{sums["pages"]}"' if kind == "book"
                else f'data-kind="film" data-total="{round(sums["minutes"])}" data-count="{sums["parts"]}"' if kind == "film"
                else f'data-kind="screen" data-total="{round(sums["minutes"])}" data-count="{sums["episodes"] + sums["extras"]}"')
        name = binge.card_name(entry)
        cards.append(
            f'<li class="bc-card" id="{slug}"><a class="bc-card__link" href="{binge.path(slug)}">'
            f'<strong>{_e(name[:1].upper() + name[1:])}</strong>'
            f'<span class="bc-card__total">{_e(_clock(sums["minutes"]) if kind == "film" else _hours(sums["minutes"]) + " hours")}</span>'
            f'<span class="bc-card__meta">{_e(_card_line(entry))}</span></a>'
            f'<button type="button" class="bc-use" data-binge-example {load} data-name="{_e(name[:1].upper() + name[1:])}">'
            'Load into the calculator</button></li>'
        )
    return f'<ul class="bc-cards" aria-label="{_e(binge.KIND_LABELS[kind])}">{"".join(cards)}</ul>'


GUIDE = (
    '<section class="editorial bc-explain" id="how-it-works"><h2>How the numbers are worked out</h2>'
    '<p>For a show, the total is episodes times the length of one episode. The episode lengths in the guides are what a '
    'streaming copy runs without ads, including the opening and the credits. A 22-minute sitcom was a 30-minute broadcast slot; '
    'a 47-minute drama was an hour. If you skip intros and "previously on" recaps, tick the box and the calculator takes about two '
    'minutes off each episode, which adds up over a long show: across 327 episodes of Supernatural it is nearly eleven hours.</p>'
    f'<p>For books, the total is pages divided by how many pages you read in an hour. The default is {binge.PAGES_PER_HOUR} pages an hour, '
    f'which is roughly 200 words a minute on a page of about {binge.WORDS_PER_PAGE} words. Page counts change a lot between editions, '
    'so the book guides start from word counts instead. A dense fantasy paperback can carry 400 words a page and a large-print '
    'edition fewer than 250, so if you time yourself for ten minutes and multiply by six you will get a better pace than the default.</p>'
    '<p>Audiobooks and podcasts are the simplest: the listed length divided by your playback speed. A 45-hour audiobook is '
    '30 hours at 1.5x. Games are the least exact, because two people rarely play the same way. When you look up a game, the '
    'hours come from the average playtime RAWG reports, and you should treat it as a starting guess.</p>'
    '<p>The finish date counts the start day as day one and only counts the days of the week you chose. Nobody keeps to a schedule '
    'exactly, so treat the date as a target.</p></section>'
    '<section class="editorial bc-explain"><h2>Three things that change the answer most</h2>'
    '<p><strong>Daily time.</strong> Going from one hour a day to two halves the number of days. '
    'Going from two to three only cuts a third, and from three to four a quarter, so the first extra hour is the one that counts.</p>'
    '<p><strong>Weekends only stretches things a long way.</strong> Two hours on Saturday and two on Sunday is four hours a week. '
    'At that pace The Wire takes about 15 weeks, against about a month at two hours every evening.</p>'
    '<p><strong>Filler and skippable episodes.</strong> Long-running anime often have filler arcs that are not in the original '
    'manga. For Naruto, skipping them takes more than 110 hours off the total. The <a href="/binge-calculator/naruto-and-shippuden">'
    'Naruto guide</a> has a switch for it.</p>'
    '<p>To work backwards from a deadline, choose "A date to finish by". Pick the day a new season starts or the last day '
    'of a holiday, and the calculator tells you how much you need to watch or read each day to be done in time.</p></section>'
    '<section class="editorial bc-explain"><h2>Keep track while you binge</h2>'
    '<p>OmniTrackr is a free tracker for TV, anime, films, books, manga and more. Save your place episode by '
    'episode or page by page, see how many hours you have spent across your whole library on the Statistics tab, and get the next '
    'episode on your home screen when you come back. <a href="/tv-show-tracker">How TV tracking works</a> · '
    '<a href="/anime-tracker">Anime tracking</a> · <a href="/book-tracker">Book tracking</a> · '
    '<a href="/in-order">Franchises in order</a></p></section>'
)

FAQ = (
    ("How long does it take to watch Breaking Bad?",
     "About 49 hours: 62 episodes at around 47 minutes each. At two hours a day that is 25 days."),
    ("How long does it take to read all of Harry Potter?",
     "About 90 hours at 200 words a minute, or about 72 hours at 250. The seven books come to roughly 1.08 million words."),
    ("Does the calculator count ads?",
     "No. Episode lengths are for streaming copies without ad breaks. Add a few minutes per episode if you watch with ads."),
    ("Can it tell me how much to watch each day to finish by a date?",
     "Yes. Choose \"A date to finish by\", pick the date, and it gives the hours and episodes or pages you need each day."),
    ("Where do the lengths for looked-up titles come from?",
     "From title pages on OmniTrackr, which read episode lists from TVmaze and MyAnimeList, page counts from Open Library, "
     "game playtimes from RAWG and other facts from Wikidata. If a title has not been looked up yet, type the numbers in yourself."),
)


def _faq_html() -> str:
    items = "".join(f"<details><summary>{_e(question)}</summary><p>{_e(answer)}</p></details>" for question, answer in FAQ)
    return f'<section class="editorial bc-faq"><h2>Questions</h2>{items}</section>'


def content(signed_in: bool = False) -> str:
    shelves = "".join(
        f'<h3 id="guides-{kind}">{_e(binge.KIND_LABELS[kind])}</h3>{_guide_cards(kind)}' for kind in binge.KIND_ORDER)
    return (
        '<header class="hero bc-hero"><p class="eyebrow">BINGE CALCULATOR</p>'
        '<h1>How long will it take to finish?</h1>'
        '<p>Pick a show, anime, film series, book or game, say how much time you have each day, and get the total hours '
        "and the date you'll finish. Or give it a deadline and it tells you how much to watch each day. Free, and no account needed.</p></header>"
        + _tool() + _mine_panel(signed_in)
        + '<section class="bc-examples" id="examples"><p class="eyebrow">WORKED OUT FOR YOU</p>'
          f'<h2>{len(GUIDES)} series, season by season</h2>'
          '<p class="bc-examples__intro">Each guide breaks a series down by season, arc, book or film, says what the total '
          'leaves out, and has a planner that starts from wherever you are now.</p>'
        + shelves + '</section>'
        + GUIDE + _faq_html()
    )


def _structured() -> list:
    return [
        {"@context": "https://schema.org", "@type": "WebApplication", "name": "OmniTrackr binge calculator",
         "description": DESCRIPTION, "url": SITE + binge.BASE_PATH, "applicationCategory": "EntertainmentApplication",
         "operatingSystem": "Any", "inLanguage": "en-US", "isAccessibleForFree": True,
         "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
         "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/"}},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": question, "acceptedAnswer": {"@type": "Answer", "text": answer}}
            for question, answer in FAQ]},
        {"@context": "https://schema.org", "@type": "ItemList", "name": "How long it takes: series guides",
         "itemListElement": [{"@type": "ListItem", "position": index, "name": binge.heading(entry), "url": SITE + binge.path(slug)}
                             for index, (slug, entry) in enumerate(GUIDES.items(), 1)]},
    ]


@router.get(binge.BASE_PATH, include_in_schema=False)
def binge_calculator_page(request: Request):
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    response = page(TITLE, DESCRIPTION, binge.BASE_PATH, content(signed_in), structured_data=_structured(),
                    head=_head(signed_in, guest_list=False), member=signed_in)
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


@router.get("/api/binge-calculator/length")
def binge_length(request: Request, response: Response, kind: str = Query(..., max_length=10), title: str = Query(..., min_length=1, max_length=200),
                 year: Optional[int] = Query(None, ge=1800, le=2100), db: Session = Depends(get_db)):
    """Cached lengths for one title. Anyone can call it; nothing outside is fetched."""
    if kind not in binge.LOOKUP_KINDS:
        raise HTTPException(status_code=400, detail="Unsupported kind")
    response.headers["Cache-Control"] = "public, max-age=600"
    return binge.lookup(db, kind, title.strip(), year)


@router.get("/api/binge-calculator/mine")
def binge_mine(request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """The member's unfinished titles and the time each has left, from their own library."""
    response.headers["Cache-Control"] = "private, no-store"
    return binge.mine(db, user)


@router.get(binge.BASE_PATH + "/{slug}", include_in_schema=False)
def binge_guide_page(slug: str, request: Request, db: Session = Depends(get_db)):
    entry = binge.guide(slug)
    if entry is None:
        raise HTTPException(404, "Guide not found")
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    response = page(page_title(entry), entry["summary"], binge.path(slug), guide_content(slug, entry, _details(db), signed_in),
                    indexable=binge.is_indexable(entry), structured_data=_guide_structured(slug, entry),
                    head=_head(signed_in, guest_list=True), member=signed_in)
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


@router.get("/api/binge-calculator/{slug}/progress")
def binge_progress(slug: str, request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Where the member is in a guide's series, read from their own library."""
    response.headers["Cache-Control"] = "private, no-store"
    entry = binge.guide(slug)
    if entry is None:
        raise HTTPException(404, "Guide not found")
    return binge.progress(db, user.id, entry)


@router.post("/api/binge-calculator/{slug}/add")
def binge_add(slug: str, request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a guide's main titles to the member's library as not started (title, year and creator only)."""
    response.headers["Cache-Control"] = "private, no-store"
    entry = binge.guide(slug)
    if entry is None:
        raise HTTPException(404, "Guide not found")
    lock_progress_owner(db, user.id)
    details = _details(db)
    added, existing = binge.add_titles(db, user, entry, image_for=lambda fields: details.get(fields["id"], {}).get("image"))
    db.commit()
    if added:
        funnel.record("binge_saved", request)
    return {"added": added, "existing": existing, "progress": binge.progress(db, user.id, entry)}
