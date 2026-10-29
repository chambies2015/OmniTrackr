"""Public binge calculator (/binge-calculator) and its cache-only length lookup."""
from __future__ import annotations

from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from .. import binge_calculator as binge
from ..auth import AUTH_COOKIE_NAME
from ..dependencies import get_db
from .discover import page

router = APIRouter(tags=["binge-calculator"])
CSS_VERSION = "20261029-binge-1"
JS_VERSION = "20261029-binge-1"
SITE = "https://omnitrackr.xyz"
TITLE = "Binge calculator: how long to watch a show or read a series"
DESCRIPTION = ("Work out how many hours a TV show, anime or book series takes and the date you'll finish at your own "
               "pace. Worked examples for Breaking Bad, The Sopranos, Naruto, Harry Potter and more.")
KIND_LABELS = {"tv": "TV", "anime": "Anime", "book": "Books"}


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _hours(minutes: float) -> str:
    hours = minutes / 60
    return f"{hours:.1f}".rstrip("0").rstrip(".") if hours < 10 else f"{round(hours):,}"


def _days(days: int) -> str:
    return f"{days:,} day" if days == 1 else f"{days:,} days"


def _example_rows(kind: str) -> str:
    # A list, not a table: the shared public stylesheet restyles every table on phones.
    rows = []
    for slug, example in binge.EXAMPLES.items():
        if example["kind"] != kind:
            continue
        minutes = binge.example_minutes(example)
        if kind == "book":
            length = f"about {binge.example_pages(example):,} pages"
        else:
            length = f"{example['episodes']:,} episodes × {example['minutes']} min"
        paces = "".join(f"<div><dt>{pace} h a day</dt><dd>{_days(binge.days_at(minutes, pace))}</dd></div>"
                        for pace in binge.EXAMPLE_PACES)
        values = (f'data-episodes="{example["episodes"]}" data-minutes="{example["minutes"]}"' if kind != "book"
                  else f'data-pages="{binge.example_pages(example)}"')
        rows.append(
            f'<li class="bc-item" id="{slug}"><div class="bc-item__title"><h4><button type="button" class="bc-use" data-binge-example '
            f'data-kind="{kind}" {values} data-name="{_e(example["name"])}">{_e(example["name"])}</button></h4>'
            f'<p>{_e(example["note"])}</p></div>'
            f'<dl class="bc-item__numbers"><div><dt>Length</dt><dd>{_e(length)}</dd></div>'
            f'<div class="bc-item__total"><dt>Total</dt><dd>{_hours(minutes)} hours</dd></div>{paces}</dl></li>'
        )
    return f'<ul class="bc-list" aria-label="{_e(KIND_LABELS[kind])} examples">{"".join(rows)}</ul>'


def _tool() -> str:
    return (
        '<section class="bc-tool" id="bingeTool" aria-label="Binge calculator">'
        '<form class="bc-form" data-binge-form novalidate>'
        '<fieldset class="bc-kind"><legend>What are you starting?</legend>'
        '<label><input type="radio" name="kind" value="screen" checked> A show or anime</label>'
        '<label><input type="radio" name="kind" value="book"> A book or series of books</label></fieldset>'
        '<div class="bc-search"><label for="bcSearch">Look up a title members track</label>'
        '<input id="bcSearch" type="search" autocomplete="off" maxlength="80" placeholder="Try Severance, Frieren or Dune">'
        '<div class="bc-search__results" data-binge-results hidden></div>'
        '<p class="muted">Or type the numbers in yourself, or pick one of the examples below.</p></div>'
        '<div class="bc-fields" data-binge-screen>'
        '<label>Episodes<input type="number" name="episodes" min="1" max="20000" inputmode="numeric" value="62"></label>'
        '<label>Minutes per episode<input type="number" name="minutes" min="1" max="600" inputmode="numeric" value="47"></label></div>'
        '<div class="bc-fields" data-binge-book hidden>'
        '<label>Pages<input type="number" name="pages" min="1" max="100000" inputmode="numeric" value="400"></label>'
        f'<label>Pages an hour<input type="number" name="pace" min="5" max="200" inputmode="numeric" value="{binge.PAGES_PER_HOUR}"></label></div>'
        '<div class="bc-fields">'
        '<label>Hours a day<input type="number" name="hours" min="0.25" max="24" step="0.25" inputmode="decimal" value="2"></label>'
        '<label>Days a week<select name="week"><option value="7">Every day</option><option value="5">Weekdays only</option>'
        '<option value="2">Weekends only</option><option value="3">Three days a week</option></select></label>'
        '<label>Starting<input type="date" name="start"></label></div>'
        '<label class="bc-check"><input type="checkbox" name="skip"> Skip intros and recaps (about 2 minutes off each episode)</label>'
        '</form>'
        '<div class="bc-result" data-binge-result role="status" aria-live="polite">'
        '<p class="bc-result__name" data-binge-name>Breaking Bad</p>'
        '<p class="bc-result__total"><strong data-binge-hours>48.6</strong> hours</p>'
        '<p data-binge-finish>At 2 hours a day you would finish in 25 days.</p>'
        '<p class="muted" data-binge-detail>62 episodes at 47 minutes each.</p></div>'
        '<noscript><p>The calculator needs JavaScript. The worked examples below are plain tables and work without it.</p></noscript>'
        '</section>'
    )


GUIDE = (
    '<section class="editorial bc-guide"><h2>How the numbers are worked out</h2>'
    '<p>For a show, the total is episodes times the length of one episode. The episode lengths in the examples are what a '
    'streaming copy runs without ads, including the opening and the credits. A 22-minute sitcom was a 30-minute broadcast slot; '
    'a 47-minute drama was an hour. If you skip intros and "previously on" recaps, tick the box and the calculator takes about two '
    'minutes off each episode, which adds up over a long show: across 236 episodes of Friends it is nearly eight hours.</p>'
    f'<p>For books, the total is pages divided by how many pages you read in an hour. The default is {binge.PAGES_PER_HOUR} pages an hour, '
    f'which is roughly 200 words a minute on a page of about {binge.WORDS_PER_PAGE} words. Page counts change a lot between editions, '
    'so the book examples start from word counts instead. A dense fantasy paperback can carry 400 words a page and a large-print '
    'edition fewer than 250, so if you time yourself for ten minutes and multiply by six you will get a better pace than the default.</p>'
    '<p>The finish date counts the start day as day one and only counts the days of the week you chose. Nobody keeps to a schedule '
    'exactly, so treat the date as a target rather than a promise.</p></section>'
    '<section class="editorial bc-guide"><h2>Three things that change the answer most</h2>'
    '<p><strong>Daily time matters more than anything else.</strong> Going from one hour a day to two halves the number of days. '
    'Going from two to three only cuts a third, and from three to four a quarter, so the first extra hour is the one that counts.</p>'
    '<p><strong>Weekends only stretches things a long way.</strong> Two hours on Saturday and two on Sunday is four hours a week. '
    'At that pace The Wire takes about 15 weeks, against about a month at two hours every evening.</p>'
    '<p><strong>Filler and skippable episodes.</strong> Long-running anime often have filler arcs that are not in the original manga. '
    'Fan-made filler lists can take a big share off the total for shows like Naruto, Bleach and One Piece. Take the filler count '
    'off the episodes box and the calculator does the rest.</p></section>'
    '<section class="editorial bc-guide"><h2>Keep track while you binge</h2>'
    '<p>OmniTrackr is a free tracker for TV, anime, books, manga and more. Save your place episode by episode or page by page, see '
    'how many hours you have spent across your whole library on the Statistics tab, and get the next episode on your home screen '
    'when you come back. <a href="/tv-show-tracker">How TV tracking works</a> · <a href="/anime-tracker">Anime tracking</a> · '
    '<a href="/book-tracker">Book tracking</a> · <a href="/in-order">Franchises in order</a></p></section>'
)

FAQ = (
    ("How long does it take to watch Breaking Bad?",
     "About 49 hours: 62 episodes at around 47 minutes each. At two hours a day that is 25 days."),
    ("How long does it take to read all of Harry Potter?",
     "About 90 hours at 200 words a minute, or about 72 hours at 250. The seven books come to roughly 1.08 million words."),
    ("Does the calculator count ads?",
     "No. Episode lengths are for streaming copies without ad breaks. Add a few minutes per episode if you watch with ads."),
    ("Where do the lengths for looked-up titles come from?",
     "From title pages on OmniTrackr, which read episode lists from TVmaze and MyAnimeList, page counts from Open Library and "
     "other facts from Wikidata. If a title has not been looked up yet, type the numbers in yourself."),
)


def _faq_html() -> str:
    items = "".join(f"<details><summary>{_e(question)}</summary><p>{_e(answer)}</p></details>" for question, answer in FAQ)
    return f'<section class="editorial bc-faq"><h2>Questions</h2>{items}</section>'


def content() -> str:
    return (
        '<header class="hero bc-hero"><p class="eyebrow">BINGE CALCULATOR</p>'
        '<h1>How long will it take to finish?</h1>'
        '<p>Pick a show, anime or book series, say how much time you have each day, and get the total hours and the date '
        "you'll finish. Free, and no account needed.</p></header>"
        + _tool()
        + '<section class="bc-examples" id="examples"><h2>Worked examples</h2>'
          '<p class="muted">Totals for complete series. Click a title to load it into the calculator.</p>'
          '<h3>TV shows</h3>' + _example_rows("tv")
        + '<h3>Anime</h3>' + _example_rows("anime")
        + f'<h3>Books</h3><p class="muted">At {binge.PAGES_PER_HOUR} pages an hour, {binge.WORDS_PER_PAGE} words a page.</p>'
        + _example_rows("book") + '</section>'
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
    ]


@router.get(binge.BASE_PATH, include_in_schema=False)
def binge_calculator_page(request: Request):
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    head = (f'<link rel="stylesheet" href="/static/binge-calculator.css?v={CSS_VERSION}">'
            f'<script src="/static/binge-calculator.js?v={JS_VERSION}" defer></script>')
    if not signed_in:
        head += '<script src="/static/ad-loader.js" defer></script>'
    response = page(TITLE, DESCRIPTION, binge.BASE_PATH, content(), structured_data=_structured(), head=head,
                    member=signed_in)
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

