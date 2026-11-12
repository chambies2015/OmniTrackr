"""Awards season: the calendar at /awards, a guide and ballot per show, the member API and shared ballots."""
from __future__ import annotations

import json
from datetime import date, datetime
from html import escape
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import awards, awards_data, funnel, models, title_pages
from ..admin_access import is_site_admin
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..progress import lock_progress_owner
from .profiles import _CardCache

router = APIRouter(tags=["awards"])
_CARDS = _CardCache(size=64)
CSS_VERSION = "20261112-awards-1"
JS_VERSION = "20261112-awards-1"
COMPLETE_WORDS = {"movie": "Watched", "tv": "Watched", "anime": "Watched", "game": "Played", "album": "Listened", "book": "Read"}
MAX_CATEGORIES = 80


class PicksBody(BaseModel):
    picks: dict[str, Optional[str]] = Field(..., min_length=1, max_length=MAX_CATEGORIES)


class ResultBody(BaseModel):
    category: str = Field(..., min_length=1, max_length=80)
    nominee: Optional[str] = Field(None, max_length=120)


class AddBody(BaseModel):
    id: str = Field(..., min_length=3, max_length=160)


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _paragraphs(values) -> str:
    return "".join(f"<p>{_e(value)}</p>" for value in values)


def _long_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%B %d, %Y").replace(" 0", " ")


def _show_or_404(slug: str) -> dict:
    show = awards.get(slug)
    if show is None:
        raise HTTPException(status_code=404, detail="No awards show at that address.")
    return show


def _signup_path(slug: str) -> str:
    return "/?next=" + quote(f"{awards.path(slug)}#ballot", safe="") + "#landing-auth"


# ---------------------------------------------------------------- member API

@router.get("/api/awards/card")
def ballot_card(request: Request, response: Response, user: models.User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """The dashboard card. ``show`` is false when no ballot is open and no score is fresh."""
    _no_store(response)
    return awards.card_payload(db, user)


@router.get("/api/awards/{slug}")
def ballot_state(slug: str, request: Request, response: Response, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    _no_store(response)
    _show_or_404(slug)
    return awards.payload(db, user, slug)


@router.put("/api/awards/{slug}/ballot")
def save_ballot(slug: str, body: PicksBody, request: Request, response: Response,
                user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Set or clear picks. Categories left out keep the pick they have."""
    _no_store(response)
    _show_or_404(slug)
    user_id = user.id
    try:
        _, first = awards.save_picks(db, user_id, slug, body.picks)
    except awards.BallotLocked as error:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(error))
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error))
    if first:
        funnel.record("ballot_started", request)
    _CARDS.clear_user(user_id)
    return awards.payload(db, user, slug)


@router.delete("/api/awards/{slug}/ballot")
def clear_ballot(slug: str, request: Request, response: Response, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """Delete the ballot, its share link and any reminder."""
    _no_store(response)
    _show_or_404(slug)
    user_id = user.id
    if not awards.clear(db, user_id, slug):
        raise HTTPException(status_code=404, detail="You don't have a ballot for this show.")
    _CARDS.clear_user(user_id)
    return awards.payload(db, user, slug)


@router.put("/api/awards/{slug}/follow")
def follow_show(slug: str, request: Request, response: Response, user: models.User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """Ask for a note when the nominees are in."""
    _no_store(response)
    _show_or_404(slug)
    awards.follow(db, user.id, slug)
    return awards.payload(db, user, slug)


def _ballot_or_404(db: Session, user: models.User, slug: str) -> models.AwardBallot:
    show = _show_or_404(slug)
    row = awards.get_ballot(db, user.id, slug)
    if row is None or not awards.picks_of(row, show):
        raise HTTPException(status_code=404, detail="Pick at least one winner first.")
    return row


@router.put("/api/awards/{slug}/share")
def share_ballot(slug: str, request: Request, response: Response, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """Make the public link and card for this ballot. It shows the picks and nothing from the library."""
    _no_store(response)
    row = _ballot_or_404(db, user, slug)
    first = not row.share_token
    awards.share(db, row)
    if first:
        funnel.record("ballot_link_created", request)
    return awards.payload(db, user, slug)


@router.delete("/api/awards/{slug}/share")
def unshare_ballot(slug: str, request: Request, response: Response, user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    _no_store(response)
    _show_or_404(slug)
    user_id = user.id
    row = awards.get_ballot(db, user_id, slug)
    if row is None:
        raise HTTPException(status_code=404, detail="You don't have a ballot for this show.")
    awards.unshare(db, row)
    _CARDS.clear_user(user_id)
    return awards.payload(db, user, slug)


@router.post("/api/awards/{slug}/add")
def add_nominee(slug: str, body: AddBody, request: Request, response: Response,
                user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a nominee (or one of last year's winners) to the member's library as not started."""
    _no_store(response)
    show = _show_or_404(slug)
    lock_progress_owner(db, user.id)
    try:
        state, record, item = awards.add_title(db, user, show, body.id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    category = title_pages.KINDS[item["kind"]][2]
    result = {"state": state, "title": record.title,
              "library_url": f"/?library_category={category}&library_item={record.id}"}
    db.commit()
    if state == "created":
        funnel.record("ballot_title_added", request)
    return result


@router.put("/api/awards/{slug}/results")
def mark_winner(slug: str, body: ResultBody, request: Request, response: Response,
                user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Site admins record a category's winner as it is announced (null clears a mistake)."""
    _no_store(response)
    _show_or_404(slug)
    if not is_site_admin(user):
        raise HTTPException(status_code=403, detail="Only the site owner can enter winners.")
    try:
        decided = awards.set_result(db, slug, body.category, body.nominee)
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error))
    return {"results": decided}


# ---------------------------------------------------------------- page pieces

def _status_line(show: dict, state: str, today: date) -> str:
    """The small capital line above the heading."""
    if state == "coming":
        return f"NOMINEES DUE {show['nominees_label'].upper()}"
    if state == "open":
        days = awards.days_left(show)
        if days == 0:
            return "BALLOT OPEN · LOCKS TODAY"
        return f"BALLOT OPEN · LOCKS IN {days} DAY{'' if days == 1 else 'S'}"
    if state == "locked":
        return "PICKS LOCKED · WINNERS COMING IN"
    return "THE WINNERS"


def _countdown(show: dict, today: date) -> str:
    days = (date.fromisoformat(show["ceremony_day"]) - today).days
    if days > 1:
        return f"{days} days to go"
    if days == 1:
        return "Tomorrow"
    if days == 0:
        return "Today"
    return "Finished"


def _art(item: Optional[dict], details: dict, name: str) -> str:
    image = title_pages._safe_image((details.get(item["id"]) or {}).get("image")) if item else None
    if image:
        return (f'<span class="aw-nom__art"><img src="{_e(image)}" alt="" width="56" height="84" loading="lazy" '
                'decoding="async" referrerpolicy="no-referrer"></span>')
    initial = next((char for char in name if char.isalnum()), "?").upper()
    return f'<span class="aw-nom__art aw-nom__art--blank" aria-hidden="true">{_e(initial)}</span>'


def _library_chip(item: Optional[dict], states: Optional[dict], details: dict, member: bool) -> str:
    """What a member sees beside a trackable title: its place in their library, or a button to add it."""
    parts = []
    if item and member:
        match = (states or {}).get(item["id"])
        if match and match["state"] == "done":
            parts.append(f'<a class="aw-chip aw-chip--done" href="{_e(match["library_url"])}">'
                         f'{_e(COMPLETE_WORDS[item["kind"]])} ✓</a>')
        elif match:
            parts.append(f'<a class="aw-chip" href="{_e(match["library_url"])}">In your library ✓</a>')
        else:
            parts.append(f'<button type="button" class="aw-add" data-award-add="{_e(item["id"])}" '
                         f'aria-label="Add {_e(item["title"])} to my library">+ Add to library</button>')
    detail = details.get(item["id"]) if item else None
    if detail and detail.get("url"):
        parts.append(f'<a class="aw-nom__link" href="{_e(detail["url"])}">Title page</a>')
    return "".join(parts)


def _category_html(index: int, category: dict, *, picks: dict, decided: dict, tallies: dict, states: Optional[dict],
                   details: dict, member: bool, locked: bool, admin: bool) -> str:
    key = category["key"]
    winner = decided.get(key)
    picked = picks.get(key)
    shares = tallies.get(key) or {}
    rows = []
    for nominee in category["nominees"]:
        is_pick = picked == nominee["key"]
        classes = ["aw-nom"]
        if is_pick:
            classes.append("aw-nom--picked")
        if winner == nominee["key"]:
            classes.append("aw-nom--winner")
        input_id = f"pick-{key}-{nominee['key']}"
        radio = (f'<input type="radio" id="{_e(input_id)}" name="{_e(key)}" value="{_e(nominee["key"])}"'
                 f'{" checked" if is_pick else ""}{" disabled" if locked else ""}>')
        detail = f'<small>{_e(nominee["detail"])}</small>' if nominee["detail"] else ""
        badge = '<span class="aw-nom__won">Winner</span>' if winner == nominee["key"] else ""
        if winner and is_pick and winner != nominee["key"]:
            badge = '<span class="aw-nom__yours">Your pick</span>'
        share = (f'<span class="aw-nom__share">{_e(shares[nominee["key"]])}% of ballots</span>'
                 if nominee["key"] in shares else "")
        tools = _library_chip(nominee["item"], states, details, member) + share
        if admin:
            pressed = "true" if winner == nominee["key"] else "false"
            tools += (f'<button type="button" class="aw-admin" data-award-winner="{_e(nominee["key"])}" '
                      f'data-award-category="{_e(key)}" aria-pressed="{pressed}">'
                      f'{"Undo winner" if winner == nominee["key"] else "Mark winner"}</button>')
        rows.append(
            f'<div class="{" ".join(classes)}" data-nominee="{_e(nominee["key"])}">'
            f'<label class="aw-nom__pick" for="{_e(input_id)}">{radio}{_art(nominee["item"], details, nominee["name"])}'
            f'<span class="aw-nom__text"><strong>{_e(nominee["name"])}</strong>{detail}</span>{badge}'
            '<span class="aw-nom__mark" aria-hidden="true"></span></label>'
            + (f'<div class="aw-nom__tools">{tools}</div>' if tools else "") + '</div>'
        )
    outcome = ""
    if winner:
        winner_name = next(nominee["name"] for nominee in category["nominees"] if nominee["key"] == winner)
        if picked == winner:
            outcome = f'<p class="aw-cat__outcome aw-cat__outcome--hit">You called it: {_e(winner_name)}.</p>'
        elif picked:
            outcome = f'<p class="aw-cat__outcome aw-cat__outcome--miss">Winner: {_e(winner_name)}.</p>'
        else:
            outcome = f'<p class="aw-cat__outcome">Winner: {_e(winner_name)}.</p>'
    clear = ("" if locked else
             f'<button type="button" class="aw-cat__clear" data-award-clear="{_e(key)}"{"" if picked else " hidden"}>'
             'Clear pick</button>')
    blurb = f'<p class="aw-cat__blurb">{_e(category["blurb"])}</p>' if category["blurb"] else ""
    return (
        f'<fieldset class="aw-cat{" aw-cat--decided" if winner else ""}" id="cat-{_e(key)}" data-category="{_e(key)}">'
        f'<legend><span class="aw-cat__n">{index:02d}</span><span class="aw-cat__name">{_e(category["name"])}</span></legend>'
        f'{blurb}<div class="aw-noms">{"".join(rows)}</div>'
        f'<div class="aw-cat__foot">{outcome}{clear}</div></fieldset>'
    )


def _score_banner(marks: dict, total: int, final: bool) -> str:
    if not marks["decided"]:
        return ""
    if not marks["judged"]:
        line = f"{marks['decided']} of {total} winners are in. None of them are categories you picked."
    else:
        line = f"You called {marks['correct']} of {marks['judged']}"
        line += "." if final else f" so far. {marks['decided']} of {total} winners are in."
    return f'<p class="aw-score" data-award-score><strong>{_e(line)}</strong></p>'


def _ballot_section(slug: str, show: dict, *, member: Optional[dict], states: Optional[dict], details: dict,
                    decided: dict, tallies: dict, admin: bool, state: str) -> str:
    signed_in = member is not None
    listed = awards.categories(show)
    total = len(listed)
    attrs = {
        "show": slug, "member": "1" if signed_in else "0", "state": state, "total": total,
        "signup": _signup_path(slug), "name": show["name"],
        "shared": "1" if member and member["shared"] else "0",
        "url": (member or {}).get("url") or "",
        "following": "1" if member and member["following"] else "0",
    }
    data = "".join(f' data-{name}="{_e(value)}"' for name, value in attrs.items())
    status = '<p class="aw-status" data-award-status role="status" aria-live="polite"></p>'

    if state == "coming":
        if signed_in and member["following"]:
            action = ('<p class="aw-following"><strong>You\'re on the list.</strong> A notification will tell you '
                      'when the ballot opens.</p>'
                      '<button type="button" class="aw-link aw-link--quiet" data-award-action="unfollow">Don\'t tell me</button>')
        elif signed_in:
            action = '<button type="button" class="button" data-award-action="follow">Tell me when the ballot opens</button>'
        else:
            action = (f'<a class="button" href="{_e(_signup_path(slug))}" rel="nofollow" data-award-signup>'
                      'Make a free account to get a reminder</a>')
        return (f'<section id="ballot" class="aw-ballot aw-ballot--coming" aria-labelledby="aw-ballot-heading"{data}>'
                '<p class="aw-ballot__kicker">YOUR BALLOT</p>'
                '<h2 id="aw-ballot-heading">The ballot opens when the nominees are announced</h2>'
                f'<p>{_e(show["nominees_note"])} The list is checked against the official one before it goes up here, '
                'so the ballot may open a few hours later.</p>'
                f'<div class="aw-actions">{action}</div>{status}</section>')

    locked = state != "open"
    picks = member["picks"] if member else {}
    blocks = "".join(
        _category_html(index, category, picks=picks, decided=decided, tallies=tallies, states=states,
                       details=details, member=signed_in, locked=locked, admin=admin)
        for index, category in enumerate(listed, 1)
    )
    jump = "".join(f'<li><a href="#cat-{_e(category["key"])}" data-award-jump="{_e(category["key"])}">'
                   f'{_e(category["name"])}</a></li>' for category in listed)
    picked = len(picks)
    if state == "open":
        heading = "Your ballot" if signed_in else "Pick the winners"
        intro = (f"One pick per category. Skip any you like. You can change your mind until "
                 f"{show['lock_label']}.")
    elif state == "locked":
        heading = "Your ballot" if signed_in else "The ballot"
        intro = "The show has started, so picks are locked. Winners are marked here as they are announced."
    else:
        heading = "Your ballot" if signed_in else "The winners"
        intro = "Every category has a winner. Here is how the ballot went."
    banner = ""
    if member and decided:
        banner = _score_banner(member["score"], total, state == "results")
    if signed_in and picked:
        share_label = "Copy your ballot link" if member["shared"] else "Share your ballot"
        actions = (f'<button type="button" class="button" data-award-action="share">{share_label}</button>'
                   + ('<button type="button" class="aw-link" data-award-action="unshare">Stop sharing</button>'
                      if member["shared"] else "")
                   + ('' if locked else
                      '<button type="button" class="aw-link aw-link--quiet" data-award-action="reset">Clear my ballot</button>'))
    elif signed_in:
        actions = '<button type="button" class="button" data-award-action="share" hidden>Share your ballot</button>'
    elif not locked:
        actions = ('<button type="button" class="button" data-award-action="signup">Save my ballot, free</button>'
                   '<span class="aw-note">Your picks stay in this browser until you make an account.</span>')
    else:
        actions = ""
    progress = (f'<div class="aw-progress" data-award-progress><div class="aw-progress__track">'
                f'<span class="aw-progress__fill" style="width: {int(100 * picked / total) if total else 0}%"></span></div>'
                f'<div class="aw-progress__line"><p class="aw-progress__text" data-award-count>{picked} of {total} picked</p>'
                f'{status}</div></div>')
    numbers = ""
    if tallies:
        numbers = ('<p class="aw-note">Percentages are the share of members\' ballots that picked each nominee. '
                   'They appear only after picks lock.</p>')
    return (
        f'<section id="ballot" class="aw-ballot" aria-labelledby="aw-ballot-heading"{data}>'
        '<p class="aw-ballot__kicker">YOUR BALLOT</p>'
        f'<h2 id="aw-ballot-heading">{_e(heading)}</h2><p>{_e(intro)}</p>{banner}'
        + (f'<div class="aw-actions">{actions}</div>' if actions else "")
        + f'<div class="aw-bar">{progress}</div>'
        f'<details class="aw-jump"><summary>Jump to a category</summary><ol>{jump}</ol></details>'
        f'<form class="aw-form" data-award-form novalidate>{blocks}</form>{numbers}'
        '<noscript><p class="aw-note">Saving a ballot needs JavaScript. The nominees are all listed above.</p></noscript>'
        '</section>'
    )


def _last_year(show: dict, states: Optional[dict], details: dict, member: bool) -> str:
    last = show.get("last_year")
    if not last:
        return ""
    rows = []
    for row in awards.last_year_winners(show):
        detail = f'<small>{_e(row["detail"])}</small>' if row["detail"] else ""
        chip = _library_chip(row["item"], states, details, member)
        rows.append(f'<li><span class="aw-past__cat">{_e(row["category"])}</span>'
                    f'<span class="aw-past__name"><strong>{_e(row["name"])}</strong>{detail}</span>'
                    f'<span class="aw-past__tools">{chip}</span></li>')
    listing = f'<ul class="aw-past">{"".join(rows)}</ul>' if rows else ""
    return (f'<section id="last-year" class="editorial aw-prose" aria-labelledby="aw-last-year">'
            f'<h2 id="aw-last-year">{_e(last["heading"])}</h2>{_paragraphs(last["intro"])}{listing}</section>')


def _sources(show_or_season: dict) -> str:
    links = " · ".join(f'<a href="{_e(url)}" rel="noopener" target="_blank">{_e(label)}</a>'
                       for label, url in show_or_season["sources"])
    return (f'<section class="editorial aw-sources"><p class="muted">Sources: {links}. '
            f'Dates and names were last checked on {_e(_long_date(show_or_season["reviewed"]))}. '
            '<a href="/contact">Send a correction</a> · <a href="/content-quality">Editorial standards</a></p></section>')


def _byline(entry: dict) -> str:
    return (f'<p class="guide-byline">By OmniTrackr · Checked <time datetime="{_e(entry["reviewed"])}">'
            f'{_e(_long_date(entry["reviewed"]))}</time></p>')


def _faq(pairs) -> str:
    items = "".join(f'<details class="aw-faq__item"><summary>{_e(question)}</summary><p>{_e(answer)}</p></details>'
                    for question, answer in pairs)
    return (f'<section id="faq" class="editorial aw-faq" aria-labelledby="aw-faq-heading">'
            f'<h2 id="aw-faq-heading">Questions</h2>{items}</section>')


def _article(entry: dict, canonical: str) -> dict:
    return {"@type": "Article", "headline": entry["title"], "description": entry["description"],
            "datePublished": entry["published"], "dateModified": entry["reviewed"],
            "mainEntityOfPage": canonical, "url": canonical,
            "author": {"@type": "Organization", "name": "OmniTrackr", "url": "https://omnitrackr.xyz/about"},
            "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": "https://omnitrackr.xyz/"},
            "inLanguage": "en-US"}


def _faq_data(pairs) -> dict:
    return {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": question, "acceptedAnswer": {"@type": "Answer", "text": answer}}
        for question, answer in pairs]}


def _head(signed_in: bool) -> str:
    head = (f'<link rel="stylesheet" href="/static/awards.css?v={CSS_VERSION}">'
            f'<script src="/static/awards.js?v={JS_VERSION}" defer></script>')
    if not signed_in:
        head += '<script src="/static/ad-loader.js" defer></script>'
    return head


# ---------------------------------------------------------------- the show page

def show_content(db: Session, slug: str, user=None, now: Optional[datetime] = None) -> str:
    show = awards.get(slug)
    now = now or awards._now()
    today = now.date()
    decided = awards.results(db, slug)
    state = awards.state(show, len(decided), now)
    member = awards.payload(db, user, slug, now) if user is not None else None
    states = awards.library_states(db, user.id, show) if user is not None else None
    details = awards.title_details(db, show)
    tallies = awards.tallies(db, slug, now)
    admin = user is not None and is_site_admin(user) and awards.has_nominees(show)

    dates = "".join(f'<div><dt>{_e(label)}</dt><dd>{_e(value)}</dd></div>' for label, value in show["dates"])
    sections = "".join(
        f'<section id="{_e(anchor)}" class="editorial aw-prose" aria-labelledby="aw-{_e(anchor)}">'
        f'<h2 id="aw-{_e(anchor)}">{_e(heading)}</h2>{_paragraphs(paragraphs)}</section>'
        for anchor, heading, paragraphs in show["sections"]
    )
    jump_links = [("#ballot", "Ballot"), ("#dates", "Key dates")]
    jump_links += [(f"#{anchor}", heading) for anchor, heading, _ in show["sections"]]
    if show.get("last_year"):
        jump_links.append(("#last-year", "Last year"))
    jump_links.append(("#faq", "Questions"))
    jump = ('<nav class="guide-jump" aria-label="On this page">'
            + "".join(f'<a href="{_e(href)}">{_e(label)}</a>' for href, label in jump_links) + '</nav>')
    filled = ""
    if tallies["ballots"] >= awards.MIN_PUBLIC_BALLOTS:
        filled = f'<span class="aw-hero__fact">{tallies["ballots"]} ballots filled in</span>'
    admin_note = ""
    if admin:
        admin_note = ('<p class="aw-admin-note">You are signed in as the site owner. Each nominee has a "Mark winner" '
                      'button; scores update as soon as you press it.</p>')
    return (
        f'<header class="hero hero--guide aw-hero"><a href="{awards.BASE_PATH}">← Awards season</a>'
        f'<p class="eyebrow">{_e(_status_line(show, state, today))}</p><h1>{_e(show["title"])}</h1>'
        f'<p>{_e(show["lead"])}</p>{_byline(show)}'
        f'<p class="aw-hero__facts"><span class="aw-hero__fact aw-hero__fact--when">{_e(_countdown(show, today))}</span>'
        f'<span class="aw-hero__fact">{_e(show["format"])}</span>{filled}</p>{jump}</header>'
        + admin_note
        + _ballot_section(slug, show, member=member, states=states, details=details, decided=decided,
                          tallies=tallies["categories"] if tallies["show"] else {}, admin=admin, state=state)
        + f'<section id="dates" class="editorial aw-prose" aria-labelledby="aw-dates-heading">'
          f'<h2 id="aw-dates-heading">Key dates</h2><dl class="aw-dates">{dates}</dl></section>'
        + sections
        + _last_year(show, states, details, user is not None)
        + _faq(show["faq"])
        + _sources(show)
    )


@router.get(awards.BASE_PATH + "/{slug}", include_in_schema=False)
def show_page(slug: str, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    from .discover import page
    show = _show_or_404(slug)
    canonical = awards.SITE_URL + awards.path(slug)
    structured = {"@context": "https://schema.org", "@graph": [_article(show, canonical), _faq_data(show["faq"])]}
    response = page(show["search_title"], show["description"], awards.path(slug), show_content(db, slug, user),
                    structured_data=structured, head=_head(user is not None), member=user is not None)
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


# ---------------------------------------------------------------- the calendar

def _show_card(db: Session, slug: str, show: dict, user, now: datetime) -> str:
    day = date.fromisoformat(show["ceremony_day"])
    decided = awards.results(db, slug)
    state = awards.state(show, len(decided), now)
    total = len(show.get("categories") or ())
    mine = ""
    if user is not None and state != "coming":
        chosen = awards.picks_of(awards.get_ballot(db, user.id, slug), show)
        if chosen and decided:
            marks = awards.score(chosen, decided)
            mine = f'<p class="aw-card__mine">You called {marks["correct"]} of {marks["judged"]}</p>'
        elif chosen:
            mine = f'<p class="aw-card__mine">Your ballot: {len(chosen)} of {total} picked</p>'
    if state == "coming":
        chip, action = f"Ballot opens {show['nominees_label']}", "Dates and details"
    elif state == "open":
        chip, action = "Ballot open", "Fill in your ballot"
    elif state == "locked":
        chip, action = "Picks locked", "See the ballot"
    else:
        chip, action = "Winners in", "See the winners"
    return (
        f'<article class="aw-card aw-card--{_e(state)}">'
        f'<div class="aw-card__date" aria-hidden="true"><span>{_e(day.strftime("%b").upper())}</span>'
        f'<strong>{day.day}</strong><span>{day.year}</span></div>'
        f'<div class="aw-card__body"><p class="aw-card__format">{_e(show["format"])}</p>'
        f'<h3><a href="{_e(awards.path(slug))}">{_e(show["name"])}</a></h3>'
        f'<dl class="aw-card__facts"><div><dt>Ceremony</dt><dd>{_e(day.strftime("%A, %B %d, %Y").replace(" 0", " "))}</dd></div>'
        f'<div><dt>Nominees</dt><dd>{_e(show["nominees_label"])}</dd></div>'
        f'<div><dt>Watch</dt><dd>{_e(show["watch"])}</dd></div></dl>{mine}'
        f'<p class="aw-card__foot"><span class="aw-chip aw-chip--state">{_e(chip)}</span>'
        f'<a class="button" href="{_e(awards.path(slug))}">{_e(action)} →</a></p></div></article>'
    )


def hub_content(db: Session, user=None, now: Optional[datetime] = None) -> str:
    season = awards_data.SEASON
    now = now or awards._now()
    cards = "".join(_show_card(db, slug, show, user, now) for slug, show in awards.ordered())
    also = "".join(
        f'<li><strong>{_e(entry["name"])}</strong> <span class="aw-also__when">{_e(entry["format"])} · {_e(entry["when"])}</span>'
        f'<p>{_e(entry["note"])}</p></li>' for entry in season["also"])
    jump = ('<nav class="guide-jump" aria-label="On this page"><a href="#calendar">Calendar</a>'
            '<a href="#ballots">How ballots work</a><a href="#voting">Who decides</a><a href="#faq">Questions</a></nav>')
    return (
        f'<header class="hero hero--guide aw-hero"><a href="/guides">← Guides</a>'
        f'<p class="eyebrow">AWARDS SEASON · 2026–27</p><h1>{_e(season["title"])}</h1>'
        f'<p>{_e(season["lead"])}</p>{_byline(season)}{jump}</header>'
        f'<section id="calendar" class="aw-calendar" aria-labelledby="aw-calendar-heading">'
        f'<h2 id="aw-calendar-heading">The calendar</h2><div class="aw-cards">{cards}</div>'
        + (f'<div class="aw-also"><h3>Also coming</h3><ul>{also}</ul></div>' if also else "") + '</section>'
        f'<section id="ballots" class="editorial aw-prose" aria-labelledby="aw-ballots-heading">'
        f'<h2 id="aw-ballots-heading">How the ballots work</h2>{_paragraphs(season["how"])}</section>'
        f'<section id="voting" class="editorial aw-prose" aria-labelledby="aw-voting-heading">'
        f'<h2 id="aw-voting-heading">Who decides the winners</h2>{_paragraphs(season["voting"])}</section>'
        + _faq(season["faq"])
        + '<section class="editorial aw-prose aw-related"><h2>While you wait for nominees</h2><ul>'
          '<li><a href="/best-of">Best of 2026</a>: the year\'s standouts in nine formats, several of them likely nominees.</li>'
          '<li><a href="/new-releases">Release guides</a>: what is still coming out before the eligibility cut-offs.</li>'
          '<li><a href="/binge-calculator">Binge calculator</a>: how long it takes to catch up on a series before the show.</li>'
          '</ul></section>'
        + _sources(season)
    )


@router.get(awards.BASE_PATH, include_in_schema=False)
def hub_page(user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    from .discover import page
    season = awards_data.SEASON
    canonical = awards.SITE_URL + awards.BASE_PATH
    structured = {"@context": "https://schema.org", "@graph": [_article(season, canonical), _faq_data(season["faq"])]}
    response = page(season["search_title"], season["description"], awards.BASE_PATH, hub_content(db, user),
                    structured_data=structured, head=_head(user is not None), member=user is not None)
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


# ---------------------------------------------------------------- shared ballot

def _shared_or_404(db: Session, token: str) -> tuple[models.AwardBallot, models.User, dict]:
    row = awards.find_shared(db, token)
    if row is None:
        raise HTTPException(status_code=404, detail="This ballot isn't shared anymore")
    return row, db.get(models.User, row.user_id), awards.get(row.show)


def _shared_lines(show: dict, picks: dict, decided: dict) -> list[dict]:
    lines = []
    for category in awards.categories(show):
        choice = picks.get(category["key"])
        if not choice:
            continue
        name = next(nominee["name"] for nominee in category["nominees"] if nominee["key"] == choice)
        winner = decided.get(category["key"])
        lines.append({"category": category["name"], "pick": name,
                      "result": None if winner is None else ("hit" if winner == choice else "miss")})
    return lines


@router.get("/ballot/{token}", include_in_schema=False)
def shared_ballot_page(token: str, request: Request, viewer=Depends(get_optional_current_user),
                       db: Session = Depends(get_db)):
    from .year_in_review import _page
    row, owner, show = _shared_or_404(db, token)
    slug = row.show
    canonical = awards.SITE_URL + awards.share_path(row)
    title = awards.headline(owner.username, show)
    picks = awards.picks_of(row, show)
    decided = awards.results(db, slug)
    now = awards._now()
    state = awards.state(show, len(decided), now)
    if viewer is None:
        funnel.record("ballot_link_opened", request)
    lines = _shared_lines(show, picks, decided)
    marks = awards.score(picks, decided)
    items = []
    for line in lines:
        mark = {"hit": '<span class="aw-shared__mark aw-shared__mark--hit">Called it ✓</span>',
                "miss": '<span class="aw-shared__mark aw-shared__mark--miss">Missed</span>'}.get(line["result"], "")
        items.append(f'<li class="aw-shared__row{" aw-shared__row--" + line["result"] if line["result"] else ""}">'
                     f'<span class="aw-shared__cat">{_e(line["category"])}</span>'
                     f'<strong>{_e(line["pick"])}</strong>{mark}</li>')
    total = len(show["categories"])
    if marks["judged"]:
        lead = f"Called {marks['correct']} of {marks['judged']}"
        lead += "." if state == "results" else f" so far, with {marks['decided']} of {total} winners in."
    elif state == "open":
        lead = f"{len(picks)} of {total} categories picked. Picks lock {show['lock_label']}."
    else:
        lead = f"{len(picks)} of {total} categories picked. Picks are locked."
    compare = ""
    if viewer is not None and viewer.id != owner.id:
        mine = awards.picks_of(awards.get_ballot(db, viewer.id, slug), show)
        match = awards.agreement(mine, picks)
        if match["both"]:
            compare = (f'<p class="aw-shared__compare">You and {_e(owner.username)} agree on '
                       f'<strong>{match["same"]} of {match["both"]}</strong> categories you both picked.</p>')
    body = (f'<link rel="stylesheet" href="/static/awards.css?v={CSS_VERSION}">'
            f'<section class="title-section aw-shared" aria-label="{_e(show["name"])} ballot">{compare}'
            f'<ol class="aw-shared__list">{"".join(items)}</ol></section>')
    if state == "open":
        cta_title, cta_text, cta_button = ("Fill in your own ballot",
                                           f"Pick a winner in each {show['short']} category, save it and see who calls more.",
                                           "Make my ballot")
    else:
        cta_title, cta_text, cta_button = ("See every winner",
                                           f"The full {show['name']} ballot, with the winners and how members voted.",
                                           "Open the ballot")
    cta = (f'<section class="profile-cta site-card"><div><h2>{_e(cta_title)}</h2><p>{_e(cta_text)}</p></div>'
           f'<a class="site-btn site-btn--primary" href="{_e(awards.path(slug))}#ballot">{_e(cta_button)}</a></section>')
    html = _page(
        title=f"{title} · OmniTrackr",
        description=f"{title}: who {owner.username} picked to win, on OmniTrackr, the free tracker for everything you watch, play, read and hear.",
        canonical=canonical,
        card_url=f"{canonical}/card.png",
        eyebrow=f"Awards season · {show['name']}",
        heading=title,
        lead=lead,
        actions=(f'<button type="button" class="site-btn site-btn--ghost site-btn--sm" data-share '
                 f'data-share-title="{_e(title)}">Share</button>'),
        body=body + cta,
    )
    response = strict_html_response(html)
    response.headers["Cache-Control"] = "private, no-store" if viewer is not None else "public, max-age=300"
    response.headers["Vary"] = "Cookie"
    response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


def render_ballot_card(username: str, show_name: str, lines: list[dict], marks: dict, total_picked: int) -> bytes:
    import io
    from PIL import Image, ImageDraw
    from .profiles import _fit, _font
    width, height = 1200, 630
    base = Image.new("RGB", (width, height), (12, 10, 22))
    glow = Image.new("RGB", (width, height), (12, 10, 22))
    glow_draw = ImageDraw.Draw(glow)
    for step in range(18, 0, -1):
        radius, mix = step * 36, (1 - step / 18) * 0.5
        shade = (int(12 + 190 * mix), int(10 + 140 * mix), int(22 + 30 * mix))
        glow_draw.ellipse((width // 2 - radius * 2, -220 - radius, width // 2 + radius * 2, -220 + radius), fill=shade)
    image = Image.blend(base, glow, 0.8)
    draw = ImageDraw.Draw(image)
    gold, cream, muted = (245, 200, 92), (250, 246, 234), (176, 168, 200)
    draw.rounded_rectangle((40, 40, width - 40, height - 40), radius=28, outline=(120, 96, 44), width=2)
    draw.text((84, 72), f"OmniTrackr · {show_name}".upper(), font=_font(26, bold=True), fill=gold)
    name_font = _font(56, bold=True)
    draw.text((84, 116), _fit(draw, f"{username}'s ballot", name_font, width - 168 - 260), font=name_font, fill=cream)
    if marks["judged"]:
        badge = f"{marks['correct']} of {marks['judged']}"
        badge_font, label_font = _font(54, bold=True), _font(22)
        badge_w = max(draw.textlength(badge, font=badge_font), draw.textlength("called right", font=label_font)) + 56
        left = width - 84 - badge_w
        draw.rounded_rectangle((left, 84, width - 84, 190), radius=22, fill=(40, 32, 16), outline=gold, width=2)
        draw.text((left + 28, 92), badge, font=badge_font, fill=gold)
        draw.text((left + 28, 154), "called right", font=label_font, fill=cream)
    shown = lines[:6]
    cat_font, pick_font = _font(22), _font(32, bold=True)
    column_w = (width - 168 - 40) // 2
    for index, line in enumerate(shown):
        row, column = divmod(index, 2)
        x = 84 + column * (column_w + 40)
        y = 226 + row * 104
        draw.rounded_rectangle((x, y, x + column_w, y + 88), radius=16, fill=(24, 20, 44), outline=(64, 54, 110), width=2)
        draw.text((x + 20, y + 12), _fit(draw, line["category"].upper(), cat_font, column_w - 40), font=cat_font, fill=muted)
        color = {"hit": (110, 231, 183), "miss": (176, 168, 200)}.get(line["result"], cream)
        draw.text((x + 20, y + 42), _fit(draw, line["pick"], pick_font, column_w - 40), font=pick_font, fill=color)
    host = awards.SITE_URL.replace("https://", "").replace("http://", "")
    footer_font = _font(24)
    draw.text((84, height - 96), f"{host}{awards.BASE_PATH} · fill in your own", font=footer_font, fill=muted)
    if total_picked > len(shown):
        more = f"+ {total_picked - len(shown)} more picks"
        draw.text((width - 84 - draw.textlength(more, font=footer_font), height - 96), more, font=footer_font, fill=gold)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


@router.get("/ballot/{token}/card.png", include_in_schema=False)
def shared_ballot_card(token: str, request: Request, db: Session = Depends(get_db)):
    row, owner, show = _shared_or_404(db, token)
    picks = awards.picks_of(row, show)
    decided = awards.results(db, row.show)
    lines = _shared_lines(show, picks, decided)
    marks = awards.score(picks, decided)
    signature = json.dumps([lines, marks], sort_keys=True)
    key = (owner.id, f"ballot:{row.show}:{owner.username}:{signature}")
    png = _CARDS.get(key)
    if png is None:
        try:
            png = render_ballot_card(owner.username, show["name"], lines, marks, len(picks))
        except Exception:
            raise HTTPException(status_code=404, detail="Card unavailable")
        _CARDS.put(key, png)
    return Response(content=png, media_type="image/png", headers={
        "Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff",
    })
