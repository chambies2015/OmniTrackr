"""OmniTrackr Daily (/daily): a daily guess-the-title game, its archive and the guess API."""
from __future__ import annotations

from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import daily, funnel, pick, title_pages, title_search
from ..auth import AUTH_COOKIE_NAME
from ..dependencies import get_current_user, get_db
from ..progress import lock_progress_owner
from .discover import page

router = APIRouter(tags=["daily"])
CSS_VERSION = "20261015-daily-1"
JS_VERSION = "20261015-daily-1"
GUEST_LIST_JS = "/static/guest-list.js?v=20261012-hero-search-1"
DESCRIPTION = ("OmniTrackr Daily is a free guessing game: one movie, TV show, anime, video game, book or album a day, "
               "six clues that get easier, and six guesses. Share your score and keep your streak going.")
SITE = "https://omnitrackr.xyz"


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _day(number: int) -> str:
    value = daily.date_for(number)
    return f"{value:%B} {value.day}, {value.year}"


def _title_link(entry: dict, db: Session) -> Optional[dict]:
    """The answer's public title page and artwork, when members track it."""
    try:
        index = title_search.index(db)
    except Exception:
        return None
    slug = title_pages.title_slug(entry["title"], entry["year"])
    base = title_pages.slugify(entry["title"])
    best = None
    for item in index:
        if item["kind"] != entry["kind"]:
            continue
        if item["slug"] == slug:
            best = item
            break
        if item["base"] == base and (best is None or item["members"] > best["members"]):
            best = item
    return {"url": f"/titles/{best['kind']}/{best['slug']}", "image": best.get("image")} if best else None


def _tool(number: int, signed_in: bool, view: dict) -> str:
    next_seconds = daily.seconds_to_next() if view["is_today"] else 0
    return (
        f'<section class="dy-tool" id="dailyTool" data-number="{number}" data-kind="{_e(view["kind"])}" '
        f'data-emoji="{_e(view["emoji"])}" data-today="{"true" if view["is_today"] else "false"}" '
        f'data-today-number="{daily.today_number()}" data-next-seconds="{next_seconds}" '
        f'data-signed-in="{"true" if signed_in else "false"}" aria-label="Daily puzzle #{number}">'
        f'<p class="dy-kind"><span aria-hidden="true">{view["emoji"]}</span> This title is <strong>{_e(view["kind_label"])}</strong>.</p>'
        '<ol class="dy-clues" data-daily-clues aria-live="polite">'
        f'<li><span class="dy-clue-n">Clue 1</span>{_e(view["first_clue"])}</li></ol>'
        '<div class="dy-squares" data-daily-squares aria-hidden="true"></div>'
        '<form class="dy-guess" data-daily-form autocomplete="off">'
        f'<label for="dailyGuess">Your guess <span class="muted" data-daily-left>(6 guesses left)</span></label>'
        '<div class="dy-row"><input id="dailyGuess" type="text" maxlength="120" list="dailySuggestions" '
        'placeholder="Type a title" required enterkeyhint="go">'
        '<datalist id="dailySuggestions"></datalist>'
        '<button type="submit" class="button">Guess</button>'
        '<button type="button" class="button button--ghost" data-daily-skip>Skip for a clue</button></div>'
        '<p class="dy-status" data-daily-status role="status" aria-live="polite"></p></form>'
        '<ul class="dy-history" data-daily-history></ul>'
        '<div class="dy-result" data-daily-result hidden tabindex="-1"></div>'
        '<noscript><p>The game needs JavaScript. You can still read the guide and the archive below.</p></noscript>'
        '</section>'
    )


GUIDE = (
    '<section class="editorial dy-guide"><h2>How to play</h2>'
    '<p>Every day there is one title to guess. It can be a movie, a TV show, an anime, a video game, a book or an '
    'album, and the game tells you which before you start. You get one clue to begin with. Each wrong guess, or each '
    'skip, reveals the next clue, and the clues go from vague to obvious: the first is usually the year and the kind of '
    'story, the last names the characters or the people behind it. You have six tries in total.</p>'
    '<p>Type the title the way you would say it. Small differences do not matter: capital letters, punctuation, accents '
    'and a leading "The" are ignored, and common short names are accepted too, so "BOTW" and "Breath of the Wild" both '
    'count for the Zelda game. Suggestions come from the titles OmniTrackr members track, but you can type anything.</p>'
    '<p>When you finish, you can share your result as a row of squares without spoiling the answer: red for a wrong '
    'guess, dark for a skip and green for the right one. A new puzzle starts every day at midnight US Eastern time.</p>'
    '</section>'
    '<section class="editorial dy-guide"><h2>Tips from the editors</h2>'
    '<ul><li><strong>Use the first clue to narrow the decade.</strong> Most people guess something recent, and the year '
    'rules out more than you think.</li>'
    '<li><strong>Skipping is not cheating.</strong> If the clue fits a hundred titles, a skip costs the same as a guess '
    'and is more honest than a wild stab.</li>'
    '<li><strong>Think about who made it.</strong> The second clue is often about the studio, director or author, which '
    'is the fastest way from a genre to a single title.</li>'
    '<li><strong>Play the archive.</strong> Missed a day? Every past puzzle can still be played, and its page explains '
    'the answer, all six clues and why the title is worth your time.</li></ul>'
    '<p>Every puzzle is written by hand by OmniTrackr\'s editors, and no clue contains a word from the answer. If you '
    'think a clue is wrong, <a href="/contact">tell us</a> and we will fix it.</p></section>'
)


def _recent(numbers: list[int], limit: int = 7) -> str:
    if not numbers:
        return ''
    items = "".join(
        f'<li><a href="/daily/{n}">Puzzle #{n}</a><span>{_e(_day(n))} · {_e(daily.KIND_ARTICLE[daily.puzzle(n)["kind"]])}</span></li>'
        for n in numbers[:limit])
    more = '<p><a href="/daily/archive">See every past puzzle →</a></p>' if len(numbers) > limit else ''
    return (f'<section class="editorial dy-recent"><h2>Missed a day?</h2><p>Play earlier puzzles, or read their answers '
            f'and notes.</p><ul class="dy-archive-list">{items}</ul>{more}</section>')


def _cta(signed_in: bool) -> str:
    if signed_in:
        return ''
    return ('<section class="editorial dy-cta"><h2>Track what you guess</h2><p>OmniTrackr is a free tracker for movies, '
            'shows, anime, games, books and music in one library. Save the titles you meet here, rate what you have '
            'finished and see what your friends think. <a href="/#signup">Create a free library</a>.</p></section>')


def _head(signed_in: bool) -> str:
    head = f'<link rel="stylesheet" href="/static/daily.css?v={CSS_VERSION}">'
    if not signed_in:
        head += f'<script src="{GUEST_LIST_JS}" defer></script>'
    return head + f'<script src="/static/daily.js?v={JS_VERSION}" defer></script>'


def _respond(response):
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


@router.get("/daily", include_in_schema=False)
def daily_today(request: Request):
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    number = daily.today_number()
    if number < 1:
        content = ('<header class="hero dy-hero"><p class="eyebrow">OMNITRACKR DAILY</p><h1>Guess the title</h1>'
                   f'<p>The first puzzle starts on {_e(f"{daily.EPOCH:%B} {daily.EPOCH.day}")}.</p></header>' + GUIDE)
        return _respond(page("OmniTrackr Daily: guess the title", DESCRIPTION, "/daily", content, head=_head(signed_in)))
    view = daily.public_view(number)
    content = (
        f'<header class="hero dy-hero"><p class="eyebrow">OMNITRACKR DAILY · #{number} · {_e(_day(number)).upper()}</p>'
        '<h1>Guess today\'s title</h1>'
        '<p>One movie, show, anime, game, book or album a day. Six clues, six guesses, and a new puzzle every midnight. '
        'Free, and no account needed.</p></header>'
        + _tool(number, signed_in, view) + GUIDE + _recent(daily.archive_numbers()) + _cta(signed_in)
    )
    return _respond(page("OmniTrackr Daily: guess the movie, show, anime, game or book", DESCRIPTION, "/daily", content,
                         head=_head(signed_in),
                         structured_data={
                             "@context": "https://schema.org", "@type": "WebApplication",
                             "name": "OmniTrackr Daily", "description": DESCRIPTION, "url": f"{SITE}/daily",
                             "applicationCategory": "GameApplication", "operatingSystem": "Any", "inLanguage": "en-US",
                             "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
                             "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": f"{SITE}/"},
                         }))


@router.get("/daily/archive", include_in_schema=False)
def daily_archive(request: Request):
    numbers = daily.archive_numbers()
    if numbers:
        rows = "".join(
            f'<li><a href="/daily/{n}">Puzzle #{n}</a><span>{_e(_day(n))} · '
            f'{_e(daily.KIND_ARTICLE[daily.puzzle(n)["kind"]])}</span></li>' for n in numbers)
        body = f'<ul class="dy-archive-list dy-archive-list--full">{rows}</ul>'
    else:
        body = '<p>The first puzzle is still running. Finished puzzles appear here the next day.</p>'
    content = (
        '<header class="hero dy-hero"><p class="eyebrow">OMNITRACKR DAILY</p><h1>Every past puzzle</h1>'
        '<p>Play a puzzle you missed, or open it to read the answer, all six clues and the editors\' note on why the '
        'title is worth your time. Answers are hidden until you choose to see them.</p>'
        '<p><a class="button" href="/daily">Play today\'s puzzle</a></p></header>'
        f'<section class="editorial dy-archive">{body}</section>'
    )
    return _respond(page("OmniTrackr Daily archive: every past puzzle", "Every past OmniTrackr Daily puzzle, playable "
                         "again, with its answer, six clues and a note from the editors.", "/daily/archive", content,
                         indexable=bool(numbers)))


@router.get("/daily/{number}", include_in_schema=False)
def daily_past(number: int, request: Request, db: Session = Depends(get_db)):
    if not daily.published(number):
        raise HTTPException(404, "Puzzle not found")
    if number == daily.today_number():
        return RedirectResponse("/daily", status_code=307)
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    entry = daily.puzzle(number)
    canonical = daily.canonical_number(number)
    view = daily.public_view(number)
    link = _title_link(entry, db)
    clues = "".join(f'<li>{_e(clue)}</li>' for clue in entry["clues"])
    meta = " · ".join(str(part) for part in (title_pages.KINDS[entry["kind"]][3], entry["year"], entry["creator"]) if part)
    title_link = (f'<p><a href="{_e(link["url"])}">See {_e(entry["title"])} on OmniTrackr</a>, with member ratings and '
                  'reviews.</p>') if link else ''
    nav = []
    if number > 1:
        nav.append(f'<a href="/daily/{number - 1}">← Puzzle #{number - 1}</a>')
    nav.append('<a href="/daily/archive">All puzzles</a>')
    if number + 1 < daily.today_number():
        nav.append(f'<a href="/daily/{number + 1}">Puzzle #{number + 1} →</a>')
    else:
        nav.append('<a href="/daily">Today\'s puzzle →</a>')
    content = (
        f'<header class="hero dy-hero"><p class="eyebrow">OMNITRACKR DAILY · #{number} · {_e(_day(number)).upper()}</p>'
        f'<h1>Daily puzzle #{number}</h1>'
        f'<p>This puzzle ran on {_e(_day(number))}. Play it now with the same six clues, or open the answer below.</p>'
        '</header>'
        + _tool(number, signed_in, view)
        + '<section class="editorial dy-answer"><details data-daily-spoiler><summary>Show the answer and all six clues</summary>'
        f'<h2>The answer: {_e(entry["title"])}</h2><p class="muted">{_e(meta)}</p>'
        f'<p>{_e(entry["note"])}</p><h3>The six clues</h3><ol>{clues}</ol>{title_link}</details></section>'
        + f'<nav class="dy-pager" aria-label="Other puzzles">{"".join(nav)}</nav>'
        + GUIDE + _cta(signed_in)
    )
    path = f"/daily/{canonical}"
    response = page(f"OmniTrackr Daily #{number}: guess {view['kind_label']} from six clues",
                    f"Daily puzzle #{number} from {_day(number)}: guess {view['kind_label']} from six clues, then read "
                    "the answer and the editors' note.", path, content, indexable=canonical == number,
                    head=_head(signed_in))
    return _respond(response)


class DailyGuess(BaseModel):
    guess: str = Field("", max_length=daily.GUESS_MAX_CHARS)
    attempt: int = Field(..., ge=0, le=daily.MAX_GUESSES - 1)


@router.post("/api/daily/{number}/guess")
def daily_guess(number: int, payload: DailyGuess, request: Request, response: Response,
                db: Session = Depends(get_db)):
    """Check one guess (an empty guess is a skip). Nothing about the player is stored."""
    response.headers["Cache-Control"] = "no-store"
    if not daily.published(number):
        raise HTTPException(404, "Puzzle not found")
    result = daily.check(number, payload.guess, payload.attempt)
    if payload.attempt == 0:
        funnel.record("daily_played", request)
    if result["correct"]:
        funnel.record("daily_solved", request)
    if result["done"]:
        link = _title_link(daily.puzzle(number), db)
        result["answer"]["title_url"] = link["url"] if link else None
        result["answer"]["image"] = link["image"] if link else None
    return result


class DailyAdd(BaseModel):
    id: str = Field(..., min_length=3, max_length=160)


@router.post("/api/daily/add")
def daily_add(payload: DailyAdd, request: Request, response: Response,
              user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a published puzzle's answer to the member's library as not started (title, year and creator only)."""
    response.headers["Cache-Control"] = "private, no-store"
    entry = daily.find_answer_id(payload.id)
    if entry is None:
        raise HTTPException(404, "Puzzle answer not found")
    lock_progress_owner(db, user.id)
    link = _title_link(entry, db)
    state, record = pick.add_to_library(db, user, dict(entry), link["image"] if link else None)
    category = title_pages.KINDS[entry["kind"]][2]
    db.commit()
    return {"state": state, "title": record.title, "category": category,
            "library_url": f"/?library_category={category}&library_item={record.id}"}
