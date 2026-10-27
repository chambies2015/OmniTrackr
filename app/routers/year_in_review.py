"""Year in Review: the private recap page, its opt-in public link, and the share card."""
from __future__ import annotations

import hashlib
import io
import json
import os
from datetime import datetime
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import auth, models, supporters, year_in_review
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..site_chrome import apply_site_chrome
from .profiles import _CardCache, _fit, _font

router = APIRouter(tags=["year-in-review"])
SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
ASSET_VERSION = "20261012-support-1"
TITLE_CSS_VERSION = "20261009-take-1"
FIRST_TRACKED_NOTE = {
    2026: "OmniTrackr started keeping a dated journal in September 2026 and add dates in October, "
          "so this year's recap covers the autumn. Next year's will cover all twelve months.",
}
_CARDS = _CardCache(size=96)
STORY_JS_VERSION = "20261019-story-1"
CREATOR_NOUNS = {"movies": "movie", "music": "album", "books": "book", "manga": "series"}
SHELF_NOUNS = {"movies": ("movie", "movies"), "tv-shows": ("show", "shows"), "anime": ("anime", "anime"),
               "video-games": ("game", "games"), "music": ("album", "albums"), "books": ("book", "books"),
               "manga": ("manga", "manga")}


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _rating(value) -> str:
    return "" if value is None else f"{float(value):g}"


def _plural(count: int, word: str, plural: Optional[str] = None) -> str:
    return f"{count} {word if count == 1 else (plural or word + 's')}"


def _valid_year(year: int) -> int:
    if year < 2000 or year > datetime.utcnow().year:
        raise HTTPException(status_code=404, detail="No recap for that year")
    return year


def _cookie_user(request: Request, db: Session) -> Optional[models.User]:
    payload = auth.decode_access_token(request.cookies.get(AUTH_COOKIE_NAME) or "")
    uid = (payload or {}).get("uid")
    if not isinstance(uid, int) or isinstance(uid, bool):
        return None
    user = db.get(models.User, uid)
    if user is None or not user.is_active:
        return None
    fingerprint = (payload or {}).get("pv")
    if fingerprint is not None and fingerprint != auth.password_fingerprint(user.hashed_password):
        return None
    return user


def _share_payload(share: Optional[models.YearInReviewShare]) -> dict:
    if share is None:
        return {"shared": False, "url": None, "updated_at": None}
    return {"shared": True, "url": SITE_URL + year_in_review.share_path(share), "updated_at": share.updated_at}


# ---------------------------------------------------------------- API

@router.get("/api/year-in-review/{year}")
def recap_api(year: int, response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    _valid_year(year)
    return {
        "recap": year_in_review.build(db, user, year),
        "share": _share_payload(year_in_review.get_share(db, user.id, year)),
        "season_year": year_in_review.season_year(),
    }


@router.get("/api/year-in-review-season")
def recap_season(response: Response, user: models.User = Depends(get_current_user)):
    """Which recap the dashboard should promote right now, if any (December and January)."""
    response.headers["Cache-Control"] = "private, no-store"
    year = year_in_review.season_year()
    return {"year": year, "url": f"/year-in-review/{year}" if year else None}


@router.put("/api/year-in-review/{year}/share")
def share_recap(year: int, request: Request, response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Publish (or refresh) the member's snapshot. The link stays the same across refreshes."""
    response.headers["Cache-Control"] = "private, no-store"
    _valid_year(year)
    share = year_in_review.save_share(db, user, year)
    _CARDS.clear_user(user.id)
    return _share_payload(share)


@router.delete("/api/year-in-review/{year}/share")
def unshare_recap(year: int, response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    year_in_review.delete_share(db, user.id, year)
    _CARDS.clear_user(user.id)
    return _share_payload(None)


@router.get("/api/year-in-review/{year}/card.png", include_in_schema=False)
def own_card(year: int, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The owner's card, built the same way a shared one is, so the download shows only shareable data."""
    _valid_year(year)
    recap = year_in_review.build(db, user, year, public=True)
    return _png_response(user.id, user.username, recap, private=True)


@router.get("/api/year-in-review/{year}/story.png", include_in_schema=False)
def own_story(year: int, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The owner's vertical story image, built from shareable data only, like the card."""
    _valid_year(year)
    recap = year_in_review.build(db, user, year, public=True)
    return _png_response(user.id, user.username, recap, private=True, story=True)


# ---------------------------------------------------------------- shared HTML

def _stat_tiles(recap: dict, *, private: bool) -> str:
    tiles = [(recap.get("finished_total", 0), "finished")]
    if recap.get("moments_total"):
        tiles.append((recap["moments_total"], "journal moments"))
    if recap.get("added_total"):
        tiles.append((recap["added_total"], "added" + (" since October" if recap.get("added_partial") else "")))
    if private and recap.get("reflections_total"):
        tiles.append((recap["reflections_total"], "with notes"))
    if recap.get("library_total"):
        tiles.append((recap["library_total"], "in the library"))
    return "".join(f'<div class="recap-stat"><strong>{_e(n)}</strong><span>{_e(label)}</span></div>' for n, label in tiles)


def _highlights(recap: dict) -> str:
    bits = []
    top = recap.get("top_category")
    if top:
        bits.append(f'<div class="recap-highlight"><span>Most finished</span><strong>{_e(top["label"])}</strong>'
                    f'<small>{_e(_plural(top["finished"], "title"))}</small></div>')
    busiest = recap.get("busiest_month")
    if busiest:
        bits.append(f'<div class="recap-highlight"><span>Busiest month</span><strong>{_e(busiest["month"])}</strong>'
                    f'<small>{_e(_plural(busiest["count"], "moment"))}</small></div>')
    first = recap.get("first_finish")
    if first:
        bits.append(f'<div class="recap-highlight"><span>First finish</span><strong>{_e(first["title"])}</strong>'
                    f'<small>{_e(first["label"])} · {_e(first["month"])}</small></div>')
    last = recap.get("last_finish")
    if last:
        bits.append(f'<div class="recap-highlight"><span>Latest finish</span><strong>{_e(last["title"])}</strong>'
                    f'<small>{_e(last["label"])} · {_e(last["month"])}</small></div>')
    streak = recap.get("longest_streak") or 0
    if streak >= 2:
        bits.append(f'<div class="recap-highlight"><span>Longest streak</span><strong>{_e(_plural(streak, "day"))} in a row</strong>'
                    f'<small>{_e(_plural(recap.get("active_days") or 0, "active day"))} in all</small></div>')
    creator = recap.get("top_creator")
    if creator:
        bits.append(f'<div class="recap-highlight"><span>Top {_e(creator["role"])}</span><strong>{_e(creator["name"])}</strong>'
                    f'<small>{_e(_plural(creator["count"], CREATOR_NOUNS.get(creator["category"], "title")))} finished</small></div>')
    ratings = recap.get("ratings")
    if ratings:
        bits.append(f'<div class="recap-highlight"><span>Rating style</span><strong>{_e(ratings["style"])}</strong>'
                    f'<small>{_e(_rating(ratings["average"]))}/10 average over {_e(_plural(ratings["count"], "rating"))}</small></div>')
    return f'<div class="recap-highlights">{"".join(bits)}</div>' if bits else ""


def _persona(recap: dict) -> str:
    persona = recap.get("persona")
    if not persona:
        return ""
    return (f'<section class="recap-persona" aria-labelledby="recap-persona"><p class="site-eyebrow">Your {_e(recap.get("year"))} type</p>'
            f'<h2 id="recap-persona">{_e(persona["name"])}</h2><p>{_e(persona["line"])}</p></section>')


def _badges(recap: dict) -> str:
    rows = recap.get("badges") or []
    if not rows:
        return ""
    items = "".join(f'<li><span aria-hidden="true">{_e(row["emoji"])}</span><strong>{_e(row["name"])}</strong>'
                    f'<small>{_e(row["tier_name"])}</small></li>' for row in rows)
    return (f'<section class="title-section" aria-labelledby="recap-badges"><h2 id="recap-badges">Badges earned this year</h2>'
            f'<ul class="recap-badges">{items}</ul></section>')


def _goals(recap: dict) -> str:
    rows = recap.get("goals") or []
    if not rows:
        return ""
    items = ""
    for goal in rows:
        reached = goal["done"] >= goal["target"]
        status = "Goal reached" if reached else f'{goal["target"] - goal["done"]} to go'
        items += (f'<li class="recap-goal{" recap-goal--done" if reached else ""}">'
                  f'<strong>{_e(goal["done"])} of {_e(goal["target"])} {_e(goal["noun"])}</strong>'
                  f'<span class="recap-goal__track"><span class="recap-goal__fill" style="width: {int(goal["percent"])}%"></span></span>'
                  f'<small>{_e(status)}</small></li>')
    return (f'<section class="title-section" aria-labelledby="recap-goals"><h2 id="recap-goals">Goals</h2>'
            f'<ol class="recap-goals">{items}</ol></section>')


def _months(recap: dict) -> str:
    counts = recap.get("months") or []
    if not any(counts):
        return ""
    peak = max(counts)
    bars = ""
    for index, count in enumerate(counts):
        label = datetime(2000, index + 1, 1).strftime("%b")
        height = max(4, round(100 * count / peak)) if count else 0
        bars += (f'<li><small>{label}</small><span class="recap-bar" style="height: {height}%"></span>'
                 f'<b>{count or ""}</b></li>')
    return (f'<section class="title-section" aria-labelledby="recap-months"><h2 id="recap-months">Month by month</h2>'
            f'<ol class="recap-months" aria-label="Journal moments per month">{bars}</ol></section>')


def _title_list(rows: list, heading: str, anchor: str) -> str:
    if not rows:
        return ""
    items = "".join(
        f'<li><strong>{_e(row["title"])}</strong><span>{_e(row["label"])} · {_e(row["month"])}</span>'
        + (f'<b class="profile-rating">{_e(_rating(row["rating"]))}/10</b>' if row.get("rating") is not None else "")
        + "</li>"
        for row in rows)
    return (f'<section class="title-section" aria-labelledby="{anchor}"><h2 id="{anchor}">{_e(heading)}</h2>'
            f'<ol class="recap-list">{items}</ol></section>')


def _categories(recap: dict) -> str:
    rows = [c for c in recap.get("categories", []) if c["finished"] or c["added"]]
    if not rows:
        return ""
    tiles = "".join(
        f'<div class="profile-stat"><strong>{_e(c["finished"])}</strong><span>{_e(c["label"])}</span>'
        f'<small>{_e(c["verb"])} this year</small>'
        + (f'<small>{_e(c["added"])} added</small>' if c["added"] else "") + "</div>"
        for c in rows)
    return (f'<section class="title-section" aria-labelledby="recap-shelves"><h2 id="recap-shelves">By shelf</h2>'
            f'<div class="profile-stats">{tiles}</div></section>')


def _body(recap: dict, *, private: bool) -> str:
    if recap.get("is_empty"):
        return ('<p class="title-empty">Nothing was logged this year yet. Mark titles finished or add a journal moment '
                'and they will show up here.</p>')
    parts = [
        f'<div class="recap-stats">{_stat_tiles(recap, private=private)}</div>',
        _persona(recap),
        _highlights(recap),
        _goals(recap),
        _badges(recap),
        _title_list(recap.get("top_rated", []), "Highest rated finishes", "recap-top"),
        _title_list(recap.get("favorites", []), "Marked as favorites", "recap-favorites"),
        _categories(recap),
        _months(recap),
    ]
    note = FIRST_TRACKED_NOTE.get(recap.get("year"))
    if note:
        parts.append(f'<p class="title-sources">{_e(note)}</p>')
    return "".join(parts)


# ---------------------------------------------------------------- story mode

def _slide(kind: str, eyebrow: str, big: str, line: str = "", extra: str = "") -> str:
    return (f'<section class="recap-slide recap-slide--{_e(kind)}" data-slide="{_e(kind)}">'
            f'<p class="recap-slide__eyebrow">{_e(eyebrow)}</p><p class="recap-slide__big">{_e(big)}</p>'
            + (f'<p class="recap-slide__line">{_e(line)}</p>' if line else "") + extra + '</section>')


def story_slides(recap: dict, name: str, *, closing: str) -> list[str]:
    """Tap-through slides for the year, one fact each. Slides without data are left out."""
    year = recap.get("year", "")
    slides = [_slide("intro", f"OmniTrackr · {year} in review", f"{name}'s {year} in media",
                     "Tap or press the right arrow to step through your year.")]
    finished = recap.get("finished_total") or 0
    shelves = [c for c in recap.get("categories", []) if c.get("finished")]
    breakdown = "".join(
        f'<li><b>{_e(c["finished"])}</b> {_e(SHELF_NOUNS.get(c["category"], ("title", "titles"))[c["finished"] != 1])}</li>'
        for c in shelves)
    slides.append(_slide("finished", "This year you finished", str(finished), _plural(finished, "title").split(" ", 1)[1],
                         f'<ul class="recap-slide__chips">{breakdown}</ul>' if len(shelves) > 1 else ""))
    top = recap.get("top_category")
    if top and len(shelves) > 1:
        share = round(100 * top["finished"] / finished) if finished else 0
        slides.append(_slide("top", "Your most finished shelf", top["label"], f"{share}% of everything you finished."))
    busiest = recap.get("busiest_month")
    counts = recap.get("months") or []
    if busiest and any(counts):
        peak = max(counts)
        bars = "".join(
            f'<li class="{"is-peak" if count == peak else ""}"><small>{datetime(2000, index + 1, 1).strftime("%b")[0]}</small>'
            f'<span class="recap-bar" style="height: {max(4, round(100 * count / peak)) if count else 0}%"></span></li>'
            for index, count in enumerate(counts))
        slides.append(_slide("month", "Your busiest month", busiest["month"], f'{_plural(busiest["count"], "journal moment")} logged.',
                             f'<ol class="recap-slide__months" aria-hidden="true">{bars}</ol>'))
    streak = recap.get("longest_streak") or 0
    if streak >= 2:
        slides.append(_slide("streak", "Longest streak", _plural(streak, "day"),
                             f'in a row with something logged, out of {_plural(recap.get("active_days") or 0, "active day")}.'))
    rated = recap.get("top_rated") or []
    if rated:
        rows = "".join(f'<li><strong>{_e(row["title"])}</strong><span>{_e(row["label"])} · {_e(_rating(row["rating"]))}/10</span></li>'
                       for row in rated[1:3])
        slides.append(_slide("rated", "Your highest rated finish", rated[0]["title"],
                             f'{rated[0]["label"]} · {_rating(rated[0]["rating"])}/10',
                             f'<ol class="recap-slide__list" start="2">{rows}</ol>' if rows else ""))
    ratings = recap.get("ratings")
    if ratings:
        tens = f' {_plural(ratings["tens"], "perfect ten")}.' if ratings.get("tens") else ""
        slides.append(_slide("ratings", "Your rating style", ratings["style"],
                             f'{_rating(ratings["average"])}/10 average across {_plural(ratings["count"], "rating")}.{tens} {ratings["detail"]}'))
    creator = recap.get("top_creator")
    if creator:
        slides.append(_slide("creator", f'Your top {creator["role"]}', creator["name"],
                             f'{_plural(creator["count"], CREATOR_NOUNS.get(creator["category"], "title"))} finished this year.'))
    goals = recap.get("goals") or []
    if goals:
        reached = sum(1 for goal in goals if goal["done"] >= goal["target"])
        rows = "".join(f'<li><strong>{_e(goal["done"])} of {_e(goal["target"])}</strong><span>{_e(goal["noun"])}</span></li>' for goal in goals[:4])
        slides.append(_slide("goals", f"Your {year} goals", f"{reached} of {len(goals)} reached",
                             "", f'<ul class="recap-slide__list">{rows}</ul>'))
    badges = recap.get("badges") or []
    if badges:
        rows = "".join(f'<li><span aria-hidden="true">{_e(row["emoji"])}</span> {_e(row["name"])} <small>{_e(row["tier_name"])}</small></li>'
                       for row in badges[:6])
        slides.append(_slide("badges", "Badges earned", str(len(badges)), "", f'<ul class="recap-slide__chips">{rows}</ul>'))
    persona = recap.get("persona")
    if persona:
        slides.append(_slide("persona", f"Your {year} type", persona["name"], persona["line"]))
    slides.append(f'<section class="recap-slide recap-slide--end" data-slide="end">{closing}</section>')
    return slides


def _story(recap: dict, name: str, *, closing: str) -> str:
    if recap.get("is_empty"):
        return ""
    slides = "".join(story_slides(recap, name, closing=closing))
    return f"""<div class="recap-story" data-recap-story role="dialog" aria-modal="true" aria-label="{_e(name)}'s {_e(recap.get('year'))} in review" hidden>
    <div class="recap-story__frame">
      <div class="recap-story__bars" data-story-bars></div>
      <button type="button" class="recap-story__close" data-story-close aria-label="Close">×</button>
      <div class="recap-story__slides" aria-live="polite">{slides}</div>
      <button type="button" class="recap-story__nav recap-story__nav--prev" data-story-prev aria-label="Previous"></button>
      <button type="button" class="recap-story__nav recap-story__nav--next" data-story-next aria-label="Next"></button>
    </div>
  </div>"""


def _play_button() -> str:
    return '<button type="button" class="site-btn site-btn--primary" data-story-open hidden>▶ Play your year</button>'


def _page(*, title: str, description: str, canonical: str, card_url: str, eyebrow: str, heading: str,
          lead: str, actions: str, body: str, extra: str = "", script: bool = False, story: str = "") -> str:
    scripts = (f'<script src="/static/year-in-review.js?v={ASSET_VERSION}" defer></script>' if script
               else '<script src="/static/share.js?v=20261004-share-1" defer></script>')
    if story:
        scripts += f'\n  <script src="/static/year-in-review-story.js?v={STORY_JS_VERSION}" defer></script>'
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_e(title)}</title>
  <meta name="description" content="{_e(description)}">
  <meta name="robots" content="noindex, follow">
  <link rel="canonical" href="{_e(canonical)}">
  <meta property="og:title" content="{_e(title)}">
  <meta property="og:description" content="{_e(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{_e(canonical)}">
  <meta property="og:image" content="{_e(card_url)}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">
  <link rel="stylesheet" href="/static/title-page.css?v={TITLE_CSS_VERSION}">
  <link rel="stylesheet" href="/static/profile-page.css?v=20261004-share-1">
  <link rel="stylesheet" href="/static/year-in-review.css?v={STORY_JS_VERSION}">
  {scripts}
</head>
<body class="site title-page profile-page recap-page">
  <!--SITE_NAV:-->
  <main>
    <section class="profile-hero recap-hero">
      <div class="site-wrap profile-hero__inner">
        <div class="profile-hero__copy">
          <p class="site-eyebrow">{_e(eyebrow)}</p>
          <h1>{_e(heading)}</h1>
          <p class="profile-hero__meta">{_e(lead)}</p>
          <p class="profile-hero__actions">{actions}</p>
        </div>
      </div>
    </section>
    <div class="site-wrap title-body">
      {extra}
      {body}
    </div>
  </main>
  {story}
  <!--SITE_FOOTER-->
</body>
</html>"""
    return apply_site_chrome(page)


def _support_box(db: Session, user: models.User, year: int) -> str:
    """Closing note on the owner's recap: a thank-you for supporters, a Ko-fi ask for everyone else."""
    supporter = supporters.get_supporter(db, user.id)
    kofi = _e(supporters.KOFI_URL)
    if supporters.is_active(supporter):
        since = f" since {supporter.since.strftime('%B %Y')}" if supporter.since else ""
        return (f'<section class="site-card recap-support recap-support--thanks" aria-labelledby="recap-support">'
                f'<h2 id="recap-support">Thank you for supporting OmniTrackr</h2>'
                f'<p>Your Ko-fi support{_e(since)} helped pay for the hosting behind this recap, your library and '
                f'everything else you used in {year}. It keeps every tracking feature free for everyone.</p>'
                '<p><a class="site-btn site-btn--ghost" href="/supporters">See what supporters get</a></p></section>')
    if supporter is not None:
        heading = f"Thanks for supporting OmniTrackr in {year}"
        lead = (f"Your Ko-fi support helped keep OmniTrackr running this year. If you'd like your badge back "
                f"for {year + 1}, a one-off tip turns it on for 30 days and a monthly membership keeps it on.")
    else:
        heading = f"Help keep OmniTrackr free in {year + 1}"
        lead = ("OmniTrackr is built and run by one developer as a side project, with no investors and no paywall. "
                "Hosting, email and title data are paid for out of pocket and by members who chip in on Ko-fi. "
                "If this recap was worth a few minutes of your year, a one-off tip or a small monthly membership "
                "helps keep it running next year.")
    code = _e(supporters.supporter_code(user.id))
    return (f'<section class="site-card recap-support" aria-labelledby="recap-support">'
            f'<h2 id="recap-support">{_e(heading)}</h2><p>{_e(lead)}</p>'
            '<p>Every tracking feature stays free either way. Supporters get a badge beside their name on their profile '
            'and reviews, and a profile accent color.</p>'
            f'<p class="recap-support__code">Use the same email on Ko-fi as here, or paste your supporter code '
            f'<code>{code}</code> into the Ko-fi message, and the badge finds your account.</p>'
            f'<p class="recap-support__actions"><a class="site-btn site-btn--primary" href="{kofi}" target="_blank" '
            'rel="noopener noreferrer" data-recap-kofi>Support on Ko-fi ↗</a>'
            '<a class="site-btn site-btn--ghost" href="/supporters">How supporting works</a></p></section>')


def _summary(recap: dict) -> str:
    bits = [f"{_plural(recap.get('finished_total', 0), 'title')} finished"]
    top = recap.get("top_category")
    if top:
        bits.append(f"mostly {top['label'].lower()}")
    if recap.get("top_rated"):
        bits.append(f"top rated: {recap['top_rated'][0]['title']}")
    return ", ".join(bits)


@router.get("/year-in-review", include_in_schema=False)
def recap_home(request: Request, db: Session = Depends(get_db)):
    year = year_in_review.season_year() or datetime.utcnow().year
    return RedirectResponse(f"/year-in-review/{year}", status_code=302)


@router.get("/year-in-review/{year}", include_in_schema=False)
def recap_page(year: int, request: Request, db: Session = Depends(get_db)):
    user = _cookie_user(request, db)
    if user is None:
        return RedirectResponse("/#login", status_code=302)
    _valid_year(year)
    recap = year_in_review.build(db, user, year)
    share = year_in_review.get_share(db, user.id, year)
    state = _share_payload(share)
    years = "".join(
        f'<a class="site-chip{" recap-year--active" if y == year else ""}" href="/year-in-review/{y}">{y}</a>'
        for y in year_in_review.available_years(user))
    so_far = " so far" if year == datetime.utcnow().year and datetime.utcnow().month < 12 else ""
    share_box = f"""<section class="site-card recap-share" data-recap-year="{year}" data-shared="{'true' if state['shared'] else 'false'}">
        <div class="recap-share__copy">
          <h2>Share your year</h2>
          <p>Sharing makes a link anyone can open. It shows the numbers and titles on this page for shelves you haven't
          made private. Journal notes, reviews and private shelves are never included. Stop sharing any time.</p>
          <p class="recap-share__link" data-recap-link{'' if state['shared'] else ' hidden'}><a href="{_e(state['url'] or '')}">{_e(state['url'] or '')}</a></p>
          <p class="recap-share__status" data-recap-status aria-live="polite"></p>
        </div>
        <div class="recap-share__actions">
          <button type="button" class="site-btn site-btn--primary" data-recap-share>{'Update shared recap' if state['shared'] else 'Create share link'}</button>
          <button type="button" class="site-btn site-btn--ghost" data-recap-copy{'' if state['shared'] else ' hidden'}>Copy link</button>
          <a class="site-btn site-btn--ghost" href="/api/year-in-review/{year}/card.png" download="omnitrackr-{year}-in-review.png">Download card</a>
          <a class="site-btn site-btn--ghost" href="/api/year-in-review/{year}/story.png" download="omnitrackr-{year}-story.png">Download story image</a>
          <button type="button" class="site-btn site-btn--ghost" data-recap-unshare{'' if state['shared'] else ' hidden'}>Stop sharing</button>
        </div>
        <img class="recap-share__card" src="/api/year-in-review/{year}/card.png" alt="Your {year} in review card" width="600" height="315" loading="lazy">
      </section>"""
    closing = (f'<p class="recap-slide__eyebrow">That was your {year}</p><p class="recap-slide__big">Pass it on</p>'
               '<p class="recap-slide__line">The story image is sized for Instagram, TikTok and WhatsApp stories. '
               'It shows only shelves you haven\'t made private.</p>'
               f'<p class="recap-slide__actions"><button type="button" class="site-btn site-btn--primary" data-story-share-image '
               f'data-src="/api/year-in-review/{year}/story.png" data-filename="omnitrackr-{year}-story.png">Share story image</button>'
               f'<a class="site-btn site-btn--ghost" href="/api/year-in-review/{year}/story.png" download="omnitrackr-{year}-story.png">Save image</a>'
               '<button type="button" class="site-btn site-btn--ghost" data-story-close>See the full recap</button></p>'
               '<p class="recap-slide__status" data-story-status aria-live="polite"></p>')
    html = _page(
        title=f"Your {year} in review · OmniTrackr",
        description="Your private Year in Review on OmniTrackr.",
        canonical=f"{SITE_URL}/year-in-review/{year}",
        card_url=f"{SITE_URL}/omnitrackr_vortex.png",
        eyebrow="Year in Review · private to you",
        heading=f"Your {year} in media{so_far}",
        lead=_summary(recap) + ".",
        actions=_play_button() + f'<span class="recap-years">{years}</span>',
        body=_body(recap, private=True) + share_box + ("" if recap.get("is_empty") else _support_box(db, user, year)),
        script=True,
        story=_story(year_in_review.build(db, user, year, public=True), user.username, closing=closing),
    )
    response = strict_html_response(html)
    response.headers["Cache-Control"] = "private, no-store"
    return response


@router.get("/recap/{token}", include_in_schema=False)
def shared_recap(token: str, request: Request, db: Session = Depends(get_db)):
    share = year_in_review.find_share(db, token)
    if share is None:
        raise HTTPException(status_code=404, detail="This recap isn't shared anymore")
    recap = year_in_review.snapshot(share)
    name = share.owner.username
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    canonical = SITE_URL + year_in_review.share_path(share)
    cta = (f'<section class="profile-cta site-card"><div><h2>See your own {share.year} in review</h2>'
           '<p>Yours is ready on OmniTrackr, built from what you finished this year.</p></div>'
           f'<a class="site-btn site-btn--primary" href="/year-in-review/{share.year}">Open my recap</a></section>'
           if signed_in else
           f'<section class="profile-cta site-card"><div><h2>Make your own {share.year} in review</h2>'
           '<p>OmniTrackr is a free tracker for movies, shows, anime, games, music and books. '
           'Log what you finish and get a recap like this one every December.</p></div>'
           '<a class="site-btn site-btn--primary" href="/#signup">Start tracking free</a></section>')
    action = (f'<a class="site-btn site-btn--primary" href="/year-in-review/{share.year}">Open my recap</a>' if signed_in
              else '<a class="site-btn site-btn--primary" href="/#signup">Start tracking free</a>')
    closing = (f'<p class="recap-slide__eyebrow">Your turn</p><p class="recap-slide__big">What did your {share.year} look like?</p>'
               '<p class="recap-slide__line">OmniTrackr is free. Track movies, shows, anime, games, music and books, '
               'and get a recap like this one every December.</p>'
               f'<p class="recap-slide__actions">{action}'
               f'<button type="button" class="site-btn site-btn--ghost" data-share data-share-title="{_e(name)}\'s {share.year} in review">Share this recap</button>'
               '<button type="button" class="site-btn site-btn--ghost" data-story-close>See the full recap</button></p>')
    html = _page(
        title=f"{name}'s {share.year} in review · OmniTrackr",
        description=f"{name}'s {share.year} in media on OmniTrackr: {_summary(recap)}.",
        canonical=canonical,
        card_url=f"{canonical}/card.png",
        eyebrow=f"Year in Review · {share.year}",
        heading=f"{name}'s {share.year} in media",
        lead=_summary(recap) + ".",
        actions=(_play_button() + f'<button type="button" class="site-btn site-btn--ghost site-btn--sm" data-share '
                 f'data-share-title="{_e(name)}\'s {share.year} in review">Share</button>'),
        body=_body(recap, private=False) + cta,
        story=_story(recap, name, closing=closing),
    )
    response = strict_html_response(html)
    response.headers["Cache-Control"] = "private, no-store" if signed_in else "public, max-age=300"
    response.headers["Vary"] = "Cookie"
    response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


@router.get("/recap/{token}/card.png", include_in_schema=False)
def shared_card(token: str, request: Request, db: Session = Depends(get_db)):
    share = year_in_review.find_share(db, token)
    if share is None:
        raise HTTPException(status_code=404, detail="This recap isn't shared anymore")
    return _png_response(share.user_id, share.owner.username, year_in_review.snapshot(share))


@router.get("/recap/{token}/story.png", include_in_schema=False)
def shared_story(token: str, request: Request, db: Session = Depends(get_db)):
    share = year_in_review.find_share(db, token)
    if share is None:
        raise HTTPException(status_code=404, detail="This recap isn't shared anymore")
    return _png_response(share.user_id, share.owner.username, year_in_review.snapshot(share), story=True)


# ---------------------------------------------------------------- share card

def render_card(username: str, recap: dict) -> bytes:
    from PIL import Image, ImageDraw
    width, height = 1200, 630
    base = Image.new("RGB", (width, height), (11, 10, 24))
    glow = Image.new("RGB", (width, height), (11, 10, 24))
    glow_draw = ImageDraw.Draw(glow)
    for step in range(18, 0, -1):
        radius, mix = step * 34, (1 - step / 18) * 0.55
        shade = (int(11 + 113 * mix), int(10 + 48 * mix), int(24 + 213 * mix))
        glow_draw.ellipse((width - 160 - radius, -120 - radius, width - 160 + radius, -120 + radius), fill=shade)
    image = Image.blend(base, glow, 0.85)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, width - 40, height - 40), radius=28, outline=(60, 52, 110), width=2)

    year = recap.get("year", "")
    draw.text((84, 78), f"OmniTrackr · {year} in review", font=_font(30, bold=True), fill=(196, 181, 253))
    name_font = _font(72, bold=True)
    draw.text((84, 140), _fit(draw, username, name_font, width - 168), font=name_font, fill=(245, 243, 255))

    stats = [(str(recap.get("finished_total", 0)), "finished")]
    top = recap.get("top_category")
    if top:
        stats.append((top["label"], "most finished"))
    busiest = recap.get("busiest_month")
    if busiest:
        stats.append((busiest["month"], "busiest month"))
    elif recap.get("library_total"):
        stats.append((str(recap["library_total"]), "in the library"))
    x, y = 84, 262
    number_font, label_font = _font(52, bold=True), _font(24)
    for value, label in stats:
        block = max(draw.textlength(value, font=number_font), draw.textlength(label, font=label_font)) + 64
        if x + block > width - 84:
            break
        draw.text((x, y), value, font=number_font, fill=(245, 243, 255))
        draw.text((x, y + 66), label, font=label_font, fill=(94, 234, 212))
        x += block

    line_font = _font(28)
    lines = []
    if recap.get("top_rated"):
        picks = " · ".join(f'{row["title"]} ({_rating(row["rating"])})' for row in recap["top_rated"][:3])
        lines.append("Top rated: " + picks)
    if recap.get("favorites"):
        lines.append("Favorites: " + " · ".join(row["title"] for row in recap["favorites"][:3]))
    if not lines and recap.get("first_finish"):
        lines.append("First finish: " + recap["first_finish"]["title"])
    for index, line in enumerate(lines[:2]):
        draw.text((84, 392 + index * 44), _fit(draw, line, line_font, width - 168), font=line_font, fill=(214, 209, 240))

    foot = _font(24)
    host = SITE_URL.replace("https://", "").replace("http://", "")
    draw.text((84, height - 100), f"{host} · make your own Year in Review", font=foot, fill=(167, 160, 199))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _wrap(draw, text: str, font, width: int, lines: int) -> list[str]:
    words, out, current = (text or "").split(), [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= width or not current:
            current = trial
            continue
        out.append(current)
        current = word
        if len(out) == lines:
            break
    if current and len(out) < lines:
        out.append(current)
    if len(out) == lines and " ".join(out) != " ".join(words):
        out[-1] = _fit(draw, out[-1] + " …", font, width)
    return [_fit(draw, line, font, width) for line in out]


def render_story(username: str, recap: dict) -> bytes:
    """A 1080x1920 image for Instagram, TikTok and WhatsApp stories."""
    from PIL import Image, ImageDraw
    width, height = 1080, 1920
    image = Image.new("RGB", (width, height), (11, 10, 24))
    glow = Image.new("RGB", (width, height), (11, 10, 24))
    glow_draw = ImageDraw.Draw(glow)
    for step in range(22, 0, -1):
        mix = (1 - step / 22) * 0.6
        radius = step * 40
        glow_draw.ellipse((width - 120 - radius, -60 - radius, width - 120 + radius, -60 + radius),
                          fill=(int(11 + 113 * mix), int(10 + 48 * mix), int(24 + 213 * mix)))
    for step in range(16, 0, -1):
        mix = (1 - step / 16) * 0.35
        radius = step * 36
        glow_draw.ellipse((40 - radius, height - 200 - radius, 40 + radius, height - 200 + radius),
                          fill=(int(11 + 34 * mix), int(10 + 202 * mix), int(24 + 167 * mix)))
    image = Image.blend(image, glow, 0.85)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((48, 48, width - 48, height - 48), radius=40, outline=(60, 52, 110), width=3)
    left, inner = 110, width - 220
    white, soft, teal, violet, muted = (245, 243, 255), (214, 209, 240), (94, 234, 212), (196, 181, 253), (167, 160, 199)

    year = recap.get("year", "")
    draw.text((left, 140), f"OMNITRACKR · {year} IN REVIEW", font=_font(34, bold=True), fill=violet)
    name_font = _font(92, bold=True)
    draw.text((left, 200), _fit(draw, username, name_font, inner), font=name_font, fill=white)

    y = 360
    persona = recap.get("persona")
    if persona:
        box_font, line_font = _font(64, bold=True), _font(34)
        lines = _wrap(draw, persona["line"], line_font, inner - 80, 2)
        box_height = 170 + 46 * len(lines)
        draw.rounded_rectangle((left - 20, y, width - left + 20, y + box_height), radius=32, fill=(36, 28, 78),
                               outline=(124, 58, 237), width=3)
        draw.text((left + 20, y + 30), f"Your {year} type", font=_font(30, bold=True), fill=teal)
        draw.text((left + 20, y + 74), _fit(draw, persona["name"], box_font, inner - 40), font=box_font, fill=white)
        for index, line in enumerate(lines):
            draw.text((left + 20, y + 160 + index * 46), line, font=line_font, fill=soft)
        y += box_height + 70
    else:
        y += 40

    finished = str(recap.get("finished_total", 0))
    big = _font(220, bold=True)
    draw.text((left - 8, y), finished, font=big, fill=white)
    draw.text((left, y + 250), "titles finished" if finished != "1" else "title finished", font=_font(46, bold=True), fill=teal)
    y += 360

    tiles = []
    top = recap.get("top_category")
    if top:
        tiles.append(("Most finished", top["label"]))
    busiest = recap.get("busiest_month")
    if busiest:
        tiles.append(("Busiest month", busiest["month"]))
    streak = recap.get("longest_streak") or 0
    if streak >= 2:
        tiles.append(("Longest streak", f"{streak} days"))
    ratings = recap.get("ratings")
    if ratings:
        tiles.append(("Rating style", ratings["style"]))
    creator = recap.get("top_creator")
    if creator and len(tiles) < 4:
        tiles.append((f"Top {creator['role']}", creator["name"]))
    if not tiles and recap.get("library_total"):
        tiles.append(("In the library", str(recap["library_total"])))
    label_font, value_font = _font(28), _font(44, bold=True)
    column = (inner - 40) // 2
    for index, (label, value) in enumerate(tiles[:4]):
        x = left + (index % 2) * (column + 40)
        ty = y + (index // 2) * 160
        draw.text((x, ty), label.upper(), font=label_font, fill=muted)
        draw.text((x, ty + 44), _fit(draw, value, value_font, column), font=value_font, fill=white)
    y += 160 * ((min(len(tiles), 4) + 1) // 2) + 40

    rated = recap.get("top_rated") or []
    picks = rated[:3] if rated else (recap.get("favorites") or [])[:3]
    if picks and y < height - 420:
        draw.text((left, y), "TOP RATED" if rated else "FAVORITES", font=label_font, fill=muted)
        y += 52
        row_font, score_font = _font(40, bold=True), _font(36, bold=True)
        for index, row in enumerate(picks):
            if y > height - 300:
                break
            score = f"{_rating(row['rating'])}/10" if row.get("rating") is not None else ""
            score_width = draw.textlength(score, font=score_font) if score else 0
            draw.text((left, y), f"{index + 1}", font=row_font, fill=violet)
            draw.text((left + 60, y), _fit(draw, row["title"], row_font, inner - 100 - score_width), font=row_font, fill=white)
            if score:
                draw.text((width - left - score_width, y + 4), score, font=score_font, fill=teal)
            y += 70

    host = SITE_URL.replace("https://", "").replace("http://", "")
    draw.text((left, height - 190), host, font=_font(40, bold=True), fill=white)
    draw.text((left, height - 136), "Make your own Year in Review, free", font=_font(32), fill=muted)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _png_response(user_id: int, username: str, recap: dict, *, private: bool = False, story: bool = False):
    fingerprint = hashlib.sha256(json.dumps([username, recap, story], sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    key = (user_id, fingerprint)
    png = _CARDS.get(key)
    if png is None:
        try:
            png = (render_story if story else render_card)(username, recap)
        except Exception:
            raise HTTPException(status_code=404, detail="Card unavailable")
        _CARDS.put(key, png)
    return Response(content=png, media_type="image/png", headers={
        "Cache-Control": "private, no-store" if private else "public, max-age=3600",
        "ETag": f'"{fingerprint}"', "X-Content-Type-Options": "nosniff",
    })
