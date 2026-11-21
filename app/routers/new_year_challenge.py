"""The New Year challenge: the guide page with its pledge form, the member API and the shared pledge card."""
from __future__ import annotations

import json
from datetime import date, datetime
from html import escape
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import funnel, goals, models, new_year_challenge as nyc, year_in_review
from ..admin_access import is_site_admin
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..new_year_challenge_guide import GUIDES
from ..time_spent import CATEGORIES as FORMAT_LABELS
from .profiles import _CardCache

router = APIRouter(tags=["new-year-challenge"])
_CARDS = _CardCache(size=64)
CSS_VERSION = "20261110-pledge-3"
JS_VERSION = "20261110-pledge-2"


class PledgeBody(BaseModel):
    goals: dict[str, Optional[int]] = Field(..., min_length=1, max_length=len(goals.NOUNS))


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _preview(user) -> bool:
    return user is not None and is_site_admin(user)


def _year_or_404(year: int, user=None) -> int:
    if year not in nyc.EDITIONS or year not in GUIDES:
        raise HTTPException(status_code=404, detail="No challenge for that year.")
    if not nyc.is_public(year) and not _preview(user):
        raise HTTPException(status_code=404, detail="No challenge for that year.")
    return year


def _label(key: str) -> str:
    if key == goals.ALL:
        return "Everything"
    return FORMAT_LABELS[key][1]


# ---------------------------------------------------------------- member API

@router.get("/api/new-year-challenge")
def challenge_card(request: Request, response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The dashboard card. ``show`` is false outside the December-January window."""
    _no_store(response)
    return nyc.card_payload(db, user)


@router.get("/api/new-year-challenge/{year}")
def challenge_state(year: int, request: Request, response: Response, user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    _no_store(response)
    _year_or_404(year, user)
    return nyc.payload(db, user, year, preview=_preview(user))


@router.put("/api/new-year-challenge/{year}/pledge")
def make_pledge(year: int, body: PledgeBody, request: Request, response: Response,
                user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Save the pledged goals and sign the member up. Categories sent as null drop that goal."""
    _no_store(response)
    _year_or_404(year, user)
    try:
        _, created = nyc.pledge(db, user, year, body.goals, preview=_preview(user))
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error))
    if created:
        funnel.record("pledge_made", request)
    _CARDS.clear_user(user.id)
    return nyc.payload(db, user, year, preview=_preview(user))


@router.delete("/api/new-year-challenge/{year}/pledge")
def leave_pledge(year: int, request: Request, response: Response, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    _no_store(response)
    _year_or_404(year, user)
    if not nyc.leave(db, user.id, year):
        raise HTTPException(status_code=404, detail="You haven't pledged for that year.")
    _CARDS.clear_user(user.id)
    return nyc.payload(db, user, year, preview=_preview(user))


def _pledge_or_404(db: Session, user: models.User, year: int) -> models.YearPledge:
    _year_or_404(year, user)
    row = nyc.get(db, user.id, year)
    if row is None:
        raise HTTPException(status_code=404, detail="Make your pledge first.")
    return row


@router.put("/api/new-year-challenge/{year}/share")
def share_pledge(year: int, request: Request, response: Response,
                 user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Make the public pledge card. It shows numbers for public shelves only, never titles."""
    _no_store(response)
    row = _pledge_or_404(db, user, year)
    # The signed-in member is loaded with a handful of columns. Fetch the shelf privacy
    # switches together, or each one is its own query when public_goals reads it.
    db.refresh(user, attribute_names=[details[4] for details in year_in_review.CATEGORIES.values()])
    if not nyc.public_goals(db, user, year):
        raise HTTPException(status_code=422, detail="Your goals are all on private shelves, so there's nothing to share.")
    first = not row.share_token
    nyc.share(db, row)
    if first:
        funnel.record("pledge_link_created", request)
    return nyc.payload(db, user, year, preview=_preview(user))


@router.delete("/api/new-year-challenge/{year}/share")
def unshare_pledge(year: int, request: Request, response: Response, user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    _no_store(response)
    row = _pledge_or_404(db, user, year)
    nyc.unshare(db, row)
    _CARDS.clear_user(user.id)
    return nyc.payload(db, user, year, preview=_preview(user))


# ---------------------------------------------------------------- the guide

def _signup_path(year: int) -> str:
    return "/?next=" + quote(f"{nyc.path(year)}#pledge", safe="") + "#landing-auth"


def _counts_section(counts: dict, year: int) -> str:
    if not counts["show"]:
        return ""
    members = counts["pledged"]
    line = f"{members} members have pledged for {year}"
    if counts["titles"]:
        line += f", adding up to {counts['titles']:,} titles"
    items = "".join(
        f'<li><strong>{_e(item["median"])} {_e(item["noun"])}</strong>'
        f'<span>{_e(_label(item["key"]))}: the middle goal of {_e(item["members"])} pledges</span></li>'
        for item in counts["categories"][:6]
    )
    typical = (f'<h3>Typical goals so far</h3><ul class="nyc-typical">{items}</ul>' if items else "")
    return (f'<section class="editorial nyc-counts" aria-labelledby="nyc-counts-heading">'
            f'<h2 id="nyc-counts-heading">Who has pledged</h2><p>{_e(line)}.</p>{typical}'
            '<p class="muted">Counts include only members who made a pledge here. Formats with fewer than three '
            'goals are left out.</p></section>')


def _row_hint(key: str, member: Optional[dict]) -> str:
    """The small line under each format: last year's count for members, the typical length for guests."""
    if member is None:
        return f"Counted as {nyc.HOURS_BASIS[key]}" if key in nyc.HOURS_BASIS else "One overall number: every format counts toward it"
    goal = member["goals"].get(key)
    if goal and member["started"]:
        return f"{goal['done']} of {goal['target']} so far"
    suggestion = member["suggestions"]["categories"].get(key)
    last = member["suggestions"]["year"]
    if suggestion:
        if member["suggestions"]["projected"] and suggestion["projected"] > suggestion["done"]:
            return f"{suggestion['done']} in {last} so far, about {suggestion['projected']} at that pace"
        return f"{suggestion['done']} in {last}"
    if key == goals.ALL:
        return "One overall number: every format counts toward it"
    return f"None finished in {last} yet"


def _form(year: int, member: Optional[dict]) -> str:
    rows = []
    # The overall number goes last: most people think in formats first.
    for key in [key for key in goals.ORDER if key != goals.ALL] + [goals.ALL]:
        hours = nyc.HOURS.get(key, 0)
        current = member["goals"].get(key) if member else None
        suggestion = (member["suggestions"]["categories"].get(key) if member else None) or {}
        data = "".join(f' data-{name}="{_e(suggestion[name])}"' for name in ("keep", "more", "stretch") if name in suggestion)
        value = f' value="{_e(current["target"])}"' if current else ""
        singular, plural = goals.NOUNS[key]
        rows.append(
            f'<div class="nyc-row{" nyc-row--all" if key == goals.ALL else ""}" data-category="{_e(key)}" data-hours="{hours:.3f}"'
            f' data-singular="{_e(singular)}" data-plural="{_e(plural)}"{data}>'
            f'<label for="pledge-{_e(key)}"><span class="nyc-row__name">{_e(_label(key))}</span>'
            f'<span class="nyc-row__hint">{_e(_row_hint(key, member))}</span></label>'
            f'<input id="pledge-{_e(key)}" name="{_e(key)}" type="number" min="1" max="{goals.MAX_TARGET}" step="1" '
            f'inputmode="numeric" placeholder="–" autocomplete="off"{value}></div>'
        )
    has_suggestions = bool(member and member["suggestions"]["categories"])
    last = year - 1
    presets = ""
    if has_suggestions:
        presets = ('<div class="nyc-presets" role="group" aria-label="Starting points">'
                   f'<span>Start from {_e(last)}:</span>'
                   '<button type="button" data-preset="keep">The same again</button>'
                   '<button type="button" data-preset="more">A bit more</button>'
                   '<button type="button" data-preset="stretch">A stretch</button>'
                   '<button type="button" data-preset="clear">Clear</button></div>')
    elif member is None:
        presets = ('<div class="nyc-presets" role="group" aria-label="Starting points">'
                   '<span>Try:</span>'
                   '<button type="button" data-sample="light">A light year</button>'
                   '<button type="button" data-sample="busy">A busy year</button>'
                   '<button type="button" data-preset="clear">Clear</button></div>')
    if member is None:
        submit = '<button type="submit" class="button" data-pledge-submit>Save my pledge, free</button>'
        note = ("Your numbers stay in this browser until you make an account. After signing up you come back here "
                "to save them.")
    elif member["pledged"]:
        submit = '<button type="submit" class="button" data-pledge-submit>Update my pledge</button>'
        note = "Changes save to your yearly goals right away. Empty boxes remove that goal."
    else:
        submit = '<button type="submit" class="button" data-pledge-submit>Make my pledge</button>'
        note = "Each number becomes a yearly goal on your dashboard. You can change them any time."
    weekly = nyc.weekly_hours({key: goal["target"] for key, goal in (member or {}).get("goals", {}).items()}) if member else 0
    attrs = {
        "year": year, "member": "1" if member else "0",
        "pledged": "1" if member and member["pledged"] else "0",
        "shared": "1" if member and member["shared"] else "0",
        "url": (member or {}).get("url") or "",
        "signup": _signup_path(year),
        "max": goals.MAX_TARGET,
    }
    data_attrs = "".join(f' data-{name}="{_e(value)}"' for name, value in attrs.items())
    return (f'<form id="pledgeForm" class="nyc-form"{data_attrs} novalidate>'
            f'{presets}<div class="nyc-rows">{"".join(rows)}</div>'
            f'<p class="nyc-total" data-pledge-total aria-live="polite">{_e(_total_text(weekly))}</p>'
            f'<div class="nyc-actions">{submit}<span class="nyc-note">{_e(note)}</span></div>'
            '<p class="nyc-status" data-pledge-status role="status" aria-live="polite"></p>'
            '<noscript><p class="nyc-note">The pledge form needs JavaScript. You can set the same numbers from the '
            'goals card on your dashboard.</p></noscript></form>')


def _total_text(weekly: float) -> str:
    label = nyc.hours_label(weekly)
    if not label:
        return "Fill in a number or two to see roughly how much time it adds up to."
    return f"At typical lengths that comes to {label}, not counting the any-kind goal."


def _member_banner(year: int, member: dict) -> str:
    if not member["pledged"]:
        return ""
    goal_count = len(member["goals"])
    if member["started"]:
        reached = sum(1 for goal in member["goals"].values() if goal["pace"]["status"] == "done")
        line = f"You're in. {reached} of {goal_count} goal{'' if goal_count == 1 else 's'} reached so far."
    else:
        days = member["days_until_start"]
        line = (f"You're in with {goal_count} goal{'' if goal_count == 1 else 's'}. "
                f"The challenge starts in {days} day{'' if days == 1 else 's'}.")
    share = ('<button type="button" class="nyc-link" data-pledge-action="share">'
             + ("Copy your pledge link" if member["shared"] else "Share your pledge card") + '</button>')
    stop = ('<button type="button" class="nyc-link" data-pledge-action="unshare">Stop sharing</button>'
            if member["shared"] else "")
    leave = '<button type="button" class="nyc-link nyc-link--quiet" data-pledge-action="leave">Leave the challenge</button>'
    return (f'<div class="nyc-banner" data-pledge-banner><p><strong>{_e(line)}</strong></p>'
            f'<div class="nyc-banner__actions">{share}{stop}{leave}</div></div>')


def _cost_table() -> str:
    rows = []
    for key in goals.ORDER:
        if key not in nyc.HOURS:
            continue
        twelve = nyc.hours_label(nyc.weekly_hours({key: 12})).replace("about ", "")
        fifty_two = nyc.hours_label(nyc.weekly_hours({key: 52})).replace("about ", "")
        rows.append(f'<tr><th scope="row">{_e(_label(key))}</th><td>{_e(nyc.HOURS_BASIS[key])}</td>'
                    f'<td>{_e(twelve)}</td><td>{_e(fifty_two)}</td></tr>')
    # Scrolls sideways on phones, so it takes keyboard focus and has a name for screen readers.
    return ('<div class="nyc-table-wrap" role="region" aria-label="Time each format takes" tabindex="0">'
            '<table class="nyc-table"><caption>Roughly how much time a goal takes each week</caption>'
            '<thead><tr><th scope="col">Format</th><th scope="col">One title, typically</th>'
            '<th scope="col">12 a year</th><th scope="col">52 a year</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def _paragraphs(values) -> str:
    return "".join(f"<p>{_e(value)}</p>" for value in values)


def _member_state(db: Session, user, year: int) -> Optional[dict]:
    if user is None:
        return None
    data = nyc.payload(db, user, year, preview=_preview(user))
    data["goals"] = {goal["category"]: goal for goal in data["goals"]}
    return data


def _published(year: int) -> str:
    stamp = datetime.strptime(nyc.EDITIONS[year]["published"], "%Y-%m-%d")
    return stamp.strftime("%B %d, %Y").replace(" 0", " ")


def guide_content(db: Session, year: int, member: Optional[dict], today: Optional[date] = None) -> str:
    guide = GUIDES[year]
    today = today or nyc._today()
    started = nyc.has_started(year, today)
    ended = today > date(year, 12, 31)
    if ended:
        eyebrow = f"NEW YEAR CHALLENGE · {year} · ENDED"
    elif started:
        eyebrow = f"NEW YEAR CHALLENGE · {year} · UNDERWAY"
    else:
        days = nyc.days_until_start(year, today)
        eyebrow = f"NEW YEAR CHALLENGE · STARTS IN {days} DAY{'' if days == 1 else 'S'}"
    faq = "".join(f'<details class="nyc-faq__item"><summary>{_e(question)}</summary><p>{_e(answer)}</p></details>'
                  for question, answer in guide["faq"])
    if ended:
        pledge = ('<section id="pledge" class="save-panel nyc-pledge"><h2>This challenge has ended</h2>'
                  f'<p>The {year} challenge closed on December 31. The guide stays up as a reference, and your goals '
                  f'for {year} are still in your Year in Review.</p></section>')
    else:
        heading = "Your pledge" if member and member["pledged"] else "Make your pledge"
        intro = ("Fill in only the formats you care about. Leave the rest empty." if member
                 else "Try some numbers. Nothing is saved until you make a free account.")
        pledge = (f'<section id="pledge" class="save-panel nyc-pledge" aria-labelledby="nyc-pledge-heading">'
                  f'<h2 id="nyc-pledge-heading">{_e(heading)}</h2><p>{_e(intro)}</p>'
                  + (_member_banner(year, member) if member else "")
                  + _form(year, member)
                  + ('' if member else '<p class="nyc-member">Already a member? <a href="/?next='
                     + _e(quote(f"{nyc.path(year)}#pledge", safe="")) + '#landing-auth" rel="nofollow">Sign in</a> '
                     'and your 2026 numbers show up here.</p>')
                  + '</section>')
    jump = ('<nav class="guide-jump" aria-label="On this page"><a href="#pledge">Pledge</a><a href="#how">How it works</a>'
            '<a href="#picking">Picking a number</a><a href="#cost">What it costs</a><a href="#faq">Questions</a></nav>')
    related = ('<section class="editorial nyc-related"><h2>Finding things to pledge</h2><ul>'
               '<li><a href="/best-of">Best of 2026</a>: the year\'s standouts in all nine formats, for catching up.</li>'
               '<li><a href="/new-releases">Release guides</a>: what is coming out month by month.</li>'
               '<li><a href="/challenges">Monthly challenges</a>: three small steps each month that count the same finishes.</li>'
               '<li><a href="/discover">Discover trails</a>: picks across formats that share one idea.</li>'
               '</ul></section>')
    return (
        f'<header class="hero hero--guide nyc-hero"><a href="/challenges">← Challenges</a>'
        f'<p class="eyebrow">{_e(eyebrow)}</p><h1>{_e(guide["title"])}</h1><p>{_e(guide["lead"])}</p>{jump}</header>'
        + _counts_section(nyc.public_counts(db, year), year)
        + pledge
        + f'<section id="how" class="editorial nyc-prose" aria-labelledby="nyc-how"><h2 id="nyc-how">How it works</h2>{_paragraphs(guide["how"])}</section>'
        + f'<section id="picking" class="editorial nyc-prose" aria-labelledby="nyc-picking"><h2 id="nyc-picking">Picking a number you will keep</h2>{_paragraphs(guide["picking"])}</section>'
        + f'<section id="cost" class="editorial nyc-prose" aria-labelledby="nyc-cost"><h2 id="nyc-cost">What a year of each format costs</h2>'
          f'{_cost_table()}<p>{_e(guide["hours_note"])}</p></section>'
        + f'<section class="editorial nyc-prose" aria-labelledby="nyc-stick"><h2 id="nyc-stick">Making it stick</h2>{_paragraphs(guide["stick"])}'
          f'<h3>When you reach a goal</h3><p>{_e(guide["end"])}</p></section>'
        + f'<section id="faq" class="editorial nyc-faq" aria-labelledby="nyc-faq-heading"><h2 id="nyc-faq-heading">Questions</h2>{faq}</section>'
        + related
        + f'<section class="editorial"><p class="muted">{_e(guide["method"])} Published {_e(_published(year))}. '
          'Time estimates use the typical lengths in the table above. '
          '<a href="/contact">Send a correction</a> · <a href="/content-quality">Editorial standards</a></p></section>'
    )


def _structured(year: int) -> dict:
    guide = GUIDES[year]
    canonical = nyc.SITE_URL + nyc.path(year)
    published = nyc.EDITIONS[year]["published"]
    return {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Article", "headline": guide["title"], "description": guide["description"],
             "datePublished": published, "dateModified": published, "mainEntityOfPage": canonical, "url": canonical,
             "author": {"@type": "Organization", "name": "OmniTrackr", "url": "https://omnitrackr.xyz/about"},
             "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": "https://omnitrackr.xyz/"},
             "inLanguage": "en-US"},
            {"@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": question, "acceptedAnswer": {"@type": "Answer", "text": answer}}
                for question, answer in guide["faq"]
            ]},
        ],
    }


@router.get(nyc.BASE_PATH, include_in_schema=False)
def challenge_home(user=Depends(get_optional_current_user)):
    year = nyc.current_year()
    if year is None and _preview(user):
        year = min(nyc.EDITIONS)
    if year is None:
        raise HTTPException(status_code=404, detail="No challenge is open yet.")
    # A fixed target from the code's own editions, never from the request.
    return RedirectResponse(nyc.path(year), status_code=302)


@router.get(nyc.BASE_PATH + "/{year}", include_in_schema=False)
def challenge_guide(year: int, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    from .discover import page
    _year_or_404(year, user)
    signed_in = user is not None
    member = _member_state(db, user, year)
    guide = GUIDES[year]
    head = (f'<link rel="stylesheet" href="/static/new-year-challenge.css?v={CSS_VERSION}">'
            f'<script src="/static/new-year-challenge.js?v={JS_VERSION}" defer></script>')
    if not signed_in:
        head += '<script src="/static/ad-loader.js" defer></script>'
    response = page(guide["search_title"], guide["description"], nyc.path(year),
                    guide_content(db, year, member), structured_data=_structured(year), head=head,
                    member=signed_in, indexable=nyc.is_public(year))
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


# ---------------------------------------------------------------- shared pledge

def _shared_or_404(db: Session, token: str) -> tuple[models.YearPledge, models.User, list[dict]]:
    row = nyc.find_shared(db, token)
    if row is None:
        raise HTTPException(status_code=404, detail="This pledge isn't shared anymore")
    owner = db.get(models.User, row.user_id)
    shown = nyc.public_goals(db, owner, row.year)
    if not shown:
        raise HTTPException(status_code=404, detail="This pledge isn't shared anymore")
    return row, owner, shown


def _goal_line(goal: dict, year: int) -> str:
    verb = goals.VERBS.get(goal["category"], "finish")
    verb = {"watched": "watch", "played": "play", "listened to": "listen to", "read": "read", "finished": "finish"}.get(verb, verb)
    return f"{verb.capitalize()} {goal['target']} {goal['noun']}"


@router.get("/pledge/{token}", include_in_schema=False)
def shared_pledge_page(token: str, request: Request, db: Session = Depends(get_db)):
    from .year_in_review import _page
    row, owner, shown = _shared_or_404(db, token)
    canonical = nyc.SITE_URL + nyc.share_path(row)
    year = row.year
    title = nyc.headline(owner.username, year)
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    if not signed_in:
        funnel.record("pledge_link_opened", request)
    started = nyc.has_started(year)
    items = []
    for goal in shown:
        if started:
            status = goal["summary"]
            width = goal["percent"]
        else:
            status = "Starts January 1"
            width = 0
        done = " recap-goal--done" if goal["pace"]["status"] == "done" else ""
        items.append(f'<li class="recap-goal{done}"><strong>{_e(_goal_line(goal, year))}</strong>'
                     f'<span class="recap-goal__track"><span class="recap-goal__fill" style="width: {int(width)}%"></span></span>'
                     f'<small>{_e(status)}</small></li>')
    weekly = nyc.hours_label(nyc.weekly_hours({goal["category"]: goal["target"] for goal in shown}))
    when = f"Pledged {row.created_at.strftime('%B %d, %Y').replace(' 0', ' ')}" if row.created_at else ""
    note = " · ".join(part for part in (when, f"{weekly[0].upper()}{weekly[1:]} at typical lengths" if weekly else "") if part)
    body = (f'<section class="title-section goal-reached" aria-label="{_e(year)} pledge">'
            f'<ol class="recap-goals">{"".join(items)}</ol>'
            + (f'<p class="title-sources">{_e(note)}</p>' if note else "") + '</section>')
    cta_href = nyc.path(year) + "#pledge"
    cta = ('<section class="profile-cta site-card"><div><h2>Make your own pledge</h2>'
           f'<p>Pick how many books, films, shows, anime, games, albums, manga, podcasts or audiobooks you want to finish in {year}. '
           'Progress fills in from what you track.</p></div>'
           f'<a class="site-btn site-btn--primary" href="{_e(cta_href)}">See the {_e(year)} challenge</a></section>')
    html = _page(
        title=f"{title} · OmniTrackr",
        description=f"{title}: the goals {owner.username} pledged on OmniTrackr, the free tracker for everything you watch, play, read and hear.",
        canonical=canonical,
        card_url=f"{canonical}/card.png",
        eyebrow=f"New Year challenge · {year}",
        heading=title,
        lead=("Tracked on OmniTrackr. Progress updates as titles are marked finished." if started
              else f"Tracked on OmniTrackr. Progress starts filling in on January 1, {year}."),
        actions=(f'<button type="button" class="site-btn site-btn--ghost site-btn--sm" data-share '
                 f'data-share-title="{_e(title)}">Share</button>'),
        body=body + cta,
    )
    response = strict_html_response(html)
    response.headers["Cache-Control"] = "private, no-store" if signed_in else "public, max-age=300"
    response.headers["Vary"] = "Cookie"
    response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


def render_pledge_card(username: str, year: int, shown: list[dict], started: bool) -> bytes:
    import io
    from PIL import Image, ImageDraw
    from .profiles import _fit, _font
    width, height = 1200, 630
    base = Image.new("RGB", (width, height), (11, 10, 24))
    glow = Image.new("RGB", (width, height), (11, 10, 24))
    glow_draw = ImageDraw.Draw(glow)
    for step in range(18, 0, -1):
        radius, mix = step * 34, (1 - step / 18) * 0.55
        shade = (int(11 + 170 * mix), int(10 + 120 * mix), int(24 + 40 * mix))
        glow_draw.ellipse((width - 140 - radius, -140 - radius, width - 140 + radius, -140 + radius), fill=shade)
    image = Image.blend(base, glow, 0.85)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, width - 40, height - 40), radius=28, outline=(60, 52, 110), width=2)
    draw.text((84, 74), f"OmniTrackr · the {year} challenge", font=_font(30, bold=True), fill=(251, 191, 36))
    name_font = _font(58, bold=True)
    draw.text((84, 124), _fit(draw, f"{username} pledged to", name_font, width - 168), font=name_font, fill=(245, 243, 255))
    tiles = shown[:6]
    columns = 3 if len(tiles) > 4 else max(1, min(len(tiles), 2 if len(tiles) == 4 else len(tiles)))
    gap = 20
    tile_w = (width - 168 - gap * (columns - 1)) // columns
    tile_h = 128
    big_font, small_font = _font(54, bold=True), _font(26)
    for index, goal in enumerate(tiles):
        row, column = divmod(index, columns)
        x = 84 + column * (tile_w + gap)
        y = 222 + row * (tile_h + gap)
        draw.rounded_rectangle((x, y, x + tile_w, y + tile_h), radius=18, fill=(26, 22, 52), outline=(70, 60, 130), width=2)
        draw.text((x + 22, y + 14), _fit(draw, str(goal["target"]), big_font, tile_w - 44), font=big_font, fill=(245, 243, 255))
        draw.text((x + 22, y + 80), _fit(draw, goal["noun"], small_font, tile_w - 44), font=small_font, fill=(196, 181, 253))
        if started:
            bar_w = tile_w - 44
            draw.rounded_rectangle((x + 22, y + tile_h - 14, x + 22 + bar_w, y + tile_h - 8), radius=3, fill=(50, 44, 90))
            filled = int(bar_w * min(100, goal["percent"]) / 100)
            if filled > 0:
                draw.rounded_rectangle((x + 22, y + tile_h - 14, x + 22 + filled, y + tile_h - 8), radius=3, fill=(94, 234, 212))
    host = nyc.SITE_URL.replace("https://", "").replace("http://", "")
    footer_font = _font(24)
    draw.text((84, height - 96), f"{host}{nyc.BASE_PATH} · make your own pledge", font=footer_font, fill=(167, 160, 199))
    if len(shown) > len(tiles):
        more = f"+ {len(shown) - len(tiles)} more"
        draw.text((width - 84 - draw.textlength(more, font=footer_font), height - 96), more, font=footer_font, fill=(196, 181, 253))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


@router.get("/pledge/{token}/card.png", include_in_schema=False)
def shared_pledge_card(token: str, request: Request, db: Session = Depends(get_db)):
    row, owner, shown = _shared_or_404(db, token)
    started = nyc.has_started(row.year)
    signature = json.dumps([[goal["category"], goal["target"], goal["percent"] if started else 0] for goal in shown])
    key = (owner.id, f"pledge:{row.year}:{owner.username}:{started}:{signature}")
    png = _CARDS.get(key)
    if png is None:
        try:
            png = render_pledge_card(owner.username, row.year, shown, started)
        except Exception:
            raise HTTPException(status_code=404, detail="Card unavailable")
        _CARDS.put(key, png)
    return Response(content=png, media_type="image/png", headers={
        "Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff",
    })
