"""Monthly challenges: the member's opt-in challenge card, public guides and the shareable completion."""
from __future__ import annotations

import re
from datetime import datetime
from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from .. import challenges, models
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..discover_catalog import MONTHLY_EDITIONS
from .collections import CATEGORIES
from .profiles import _CardCache

router = APIRouter(tags=["challenges"])
_CARDS = _CardCache(size=64)
_MONTH_PATTERN = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
SIGNUP_PATH = "/?next=" + quote("/#challenge", safe="") + "#landing-auth"


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _completed_entry_or_404(db: Session, user: models.User, month: str | None = None) -> models.MonthlyChallengeEntry:
    """The member's completed entry for ``month`` (default: this month). Earlier months stay
    reachable so a completion near the month boundary can still be shared or un-shared."""
    current = challenges.month_key()
    if month is None:
        month = current
    elif not _MONTH_PATTERN.fullmatch(month) or month > current:
        raise HTTPException(status_code=404, detail="This month's challenge isn't complete yet.")
    entry = challenges.get_entry(db, user.id, month)
    if entry is None or entry.completed_at is None:
        raise HTTPException(status_code=404, detail="This month's challenge isn't complete yet.")
    return entry


# ---------------------------------------------------------------- member API

@router.get("/api/challenge")
def current_challenge(response: Response, user: models.User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    _no_store(response)
    return challenges.payload(db, user)


@router.post("/api/challenge/join")
def join_challenge(request: Request, response: Response, user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    _no_store(response)
    challenges.join(db, user.id, challenges.month_key())
    return challenges.payload(db, user)


@router.delete("/api/challenge/join")
def leave_challenge(request: Request, response: Response, user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    _no_store(response)
    if not challenges.leave(db, user.id, challenges.month_key()):
        raise HTTPException(status_code=404, detail="You haven't taken this month's challenge.")
    _CARDS.clear_user(user.id)
    return challenges.payload(db, user)


@router.post("/api/challenge/seen")
def challenge_seen(response: Response, user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db), month: str | None = Query(default=None, max_length=7)):
    """The member dismissed the dashboard celebration."""
    _no_store(response)
    entry = _completed_entry_or_404(db, user, month)
    challenges.mark_seen(db, entry)
    return challenges.completion_payload(entry)


@router.put("/api/challenge/share")
def share_challenge(request: Request, response: Response, user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db), month: str | None = Query(default=None, max_length=7)):
    """Make a public link for a completed challenge. It shows the steps, never titles."""
    _no_store(response)
    entry = _completed_entry_or_404(db, user, month)
    return challenges.completion_payload(challenges.share(db, entry))


@router.delete("/api/challenge/share")
def unshare_challenge(response: Response, user: models.User = Depends(get_current_user),
                      db: Session = Depends(get_db), month: str | None = Query(default=None, max_length=7)):
    _no_store(response)
    entry = _completed_entry_or_404(db, user, month)
    _CARDS.clear_user(user.id)
    return challenges.completion_payload(challenges.unshare(db, entry))


# ---------------------------------------------------------------- public guides

def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _paragraphs(values) -> str:
    return "".join(f"<p>{_e(value)}</p>" for value in values)


def _counts_line(counts: dict) -> str:
    if not counts["joined"]:
        return ""
    line = f"{counts['joined']} members have taken this challenge"
    if counts["completed"]:
        line += f", and {counts['completed']} have completed it"
    return f'<p class="challenge-count">{_e(line)}.</p>'


def _edition_section(step: dict) -> str:
    slug = step.get("edition")
    edition = MONTHLY_EDITIONS.get(slug)
    if not edition:
        return ""
    items = "".join(
        f'<li><strong>{_e(item["title"])}</strong> <span class="muted">{_e(CATEGORIES[item["category"]][1])}</span></li>'
        for item in edition["items"]
    )
    return (f'<section class="editorial challenge-edition"><h2>The six picks that count for step one</h2>'
            f'<p>{_e(edition["guide"])}</p><ul>{items}</ul>'
            f'<p><a href="/discover/monthly/{_e(slug)}">Read the full {_e(edition["name"])} edition →</a></p></section>')


def _cta(month: str, current: bool) -> str:
    if not current:
        return ('<section class="save-panel challenge-cta"><h2>This challenge has ended</h2>'
                '<p>Past challenges stay here as reading lists. This month\'s challenge is open on the '
                '<a href="/challenges">challenges page</a>.</p></section>')
    return ('<section id="take-challenge" class="save-panel challenge-cta"><h2>Take the challenge</h2>'
            f'<p>It is free, private and optional. Your progress fills in from the titles you mark finished in {_e(challenges.month_label(month))}, '
            'and nothing about your library is shared unless you choose to share the finished challenge.</p>'
            f'<p><a class="button" rel="nofollow" href="{_e(SIGNUP_PATH)}">Start tracking free</a> '
            '<a class="challenge-cta__member" href="/#challenge">Already a member? Open it on your dashboard</a></p></section>')


def _how_it_counts() -> str:
    return ('<section class="editorial"><h2>How progress counts</h2>'
            '<p>A title counts when you mark it finished in your library during the calendar month (UTC), whether you finish it on '
            'the first day or the last, and whether you joined before or after. Each title counts once, even if you log it twice. '
            'Ratings and takeaways come from the finish screen or your activity journal.</p>'
            '<p>There are no streaks, no leaderboards and nothing to lose if you skip a month. Leaving a challenge removes it from '
            'your dashboard without touching your library, and a new challenge starts on the first of each month.</p></section>')


def _method(published: str) -> str:
    stamp = datetime.strptime(published, "%Y-%m-%d").strftime("%B %d, %Y").replace(" 0", " ")
    return ('<section class="editorial"><p class="muted">Prepared by <a href="/about">OmniTrackr</a> and '
            f'reviewed against the linked Discover edition. Published {_e(stamp)}. '
            '<a href="/contact">Send a correction</a> · <a href="/content-quality">Editorial standards</a></p></section>')


def _archive(exclude: str) -> str:
    rows = "".join(
        f'<li><a href="/challenges/{_e(challenges.slug_for(month))}">{_e(challenges.month_label(month))}: '
        f'{_e(challenges.CHALLENGES[month]["name"])}</a><span>{_e(challenges.CHALLENGES[month]["tagline"])}</span></li>'
        for month in challenges.public_months() if month != exclude
    )
    return (f'<section class="editorial monthly-archive"><h2>Other monthly challenges</h2><ul>{rows}</ul></section>'
            if rows else "")


def _structured(name: str, description: str, path: str, published: str) -> dict:
    canonical = challenges.SITE_URL + path
    return {
        "@context": "https://schema.org", "@type": "Article",
        "headline": name, "description": description,
        "datePublished": published, "dateModified": published,
        "mainEntityOfPage": canonical, "url": canonical,
        "author": {"@type": "Organization", "name": "OmniTrackr", "url": "https://omnitrackr.xyz/about"},
        "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": "https://omnitrackr.xyz/"},
        "inLanguage": "en-US",
    }


@router.get("/challenges", include_in_schema=False)
def challenges_index(db: Session = Depends(get_db)):
    from .discover import page
    months = challenges.public_months()
    current = challenges.month_key()
    feature = ""
    if months and months[0] == current:
        challenge = challenges.CHALLENGES[current]
        steps = "".join(f"<li>{_e(step['label'])}</li>" for step in challenge["steps"])
        feature = (f'<section class="monthly-feature"><div><p class="eyebrow">THIS MONTH · {_e(challenges.month_label(current).upper())}</p>'
                   f'<h2>{_e(challenge["name"])}</h2><p>{_e(challenge["tagline"])}</p><ol class="challenge-steps-brief">{steps}</ol>'
                   f'{_counts_line(challenges.public_counts(db, current))}</div>'
                   f'<a class="button" href="/challenges/{_e(challenges.slug_for(current))}">Read this month\'s guide →</a></section>')
    content = (
        '<header class="hero"><p class="eyebrow">ONE SMALL CHALLENGE A MONTH</p><h1>Monthly challenges</h1>'
        '<p>Each month OmniTrackr sets three small steps across movies, TV, anime, games, music and books. They are written to '
        'nudge you toward something new, not to make you watch more. Join from your dashboard, and your progress fills in from '
        'what you already track.</p></header>'
        + feature
        + _archive(current if feature else "")
        + '<section class="editorial"><h2>Why challenges, and why monthly</h2>'
        '<p>A yearly goal is a good compass but a poor nudge: in March, "finish 24 books" is too far away to change what you do '
        'tonight. A month is short enough to plan around and long enough to fit a book or a season. Each challenge comes with a '
        'written guide that explains the idea behind it, suggests where to start and says plainly what counts.</p>'
        '<p>Challenges are private and opt-in. There are no streaks to protect and no ranking of members. When you complete one, '
        'you can share a card that shows the challenge and the steps, never the titles you finished.</p></section>'
        + _how_it_counts()
    )
    description = "A small, opt-in challenge every month across movies, TV, anime, games, music and books, with a written guide."
    structured = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": "Monthly challenges", "url": challenges.SITE_URL + "/challenges",
        "description": description, "inLanguage": "en-US",
        "isPartOf": {"@type": "WebSite", "name": "OmniTrackr", "url": challenges.SITE_URL + "/"},
        "mainEntity": {"@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "position": position, "name": f'{challenges.month_label(month)}: {challenges.CHALLENGES[month]["name"]}',
             "url": f"{challenges.SITE_URL}/challenges/{challenges.slug_for(month)}"}
            for position, month in enumerate(months, start=1)
        ]},
    }
    return page("Monthly media challenges", description, "/challenges", content, indexable=bool(months),
                structured_data=structured if months else None)


@router.get("/challenges/{slug}", include_in_schema=False)
def challenge_detail(slug: str, db: Session = Depends(get_db)):
    from .discover import page
    month = challenges.month_for_slug(slug)
    if month is None or month not in challenges.public_months() or slug != challenges.slug_for(month):
        raise HTTPException(status_code=404, detail="Challenge not found")
    challenge = challenges.CHALLENGES[month]
    current = month == challenges.month_key()
    label = challenges.month_label(month)
    step_cards = "".join(
        f'<article class="pick challenge-step"><p class="eyebrow">STEP {index}</p><h2>{_e(step["label"])}</h2>'
        f'<p>{_e(step["detail"])}</p></article>'
        for index, step in enumerate(challenge["steps"], 1)
    )
    edition = "".join(_edition_section(step) for step in challenge["steps"] if step["kind"] == "edition")
    reflection = (f'<section class="editorial"><h2>Something to think about</h2><p>{_e(challenge["reflection"])}</p></section>'
                  if challenge.get("reflection") else "")
    content = (
        f'<header class="hero"><a href="/challenges">← All challenges</a><p class="eyebrow">MONTHLY CHALLENGE · {_e(label.upper())}</p>'
        f'<h1>{_e(challenge["name"])}</h1><p>{_e(challenge["tagline"])}</p>'
        + (f'<a class="save-jump" href="#take-challenge">Take the challenge ↓</a>' if current else "")
        + f'{_counts_line(challenges.public_counts(db, month))}</header>'
        f'<section class="editorial challenge-intro">{_paragraphs(challenge["intro"])}</section>'
        f'<div class="picks challenge-steps">{step_cards}</div>'
        + edition + _how_it_counts() + reflection + _cta(month, current) + _archive(month) + _method(challenge["published"])
    )
    path = f"/challenges/{slug}"
    name = f"{label} challenge: {challenge['name']}"
    return page(name, challenge["tagline"], path, content,
                structured_data=_structured(name, challenge["tagline"], path, challenge["published"]))


# ---------------------------------------------------------------- shared completion

def _shared_or_404(db: Session, token: str) -> tuple[models.MonthlyChallengeEntry, models.User]:
    entry = challenges.find_shared(db, token)
    if entry is None:
        raise HTTPException(status_code=404, detail="This challenge isn't shared anymore")
    return entry, db.get(models.User, entry.user_id)


@router.get("/challenge/{token}", include_in_schema=False)
def shared_challenge_page(token: str, request: Request, db: Session = Depends(get_db)):
    from .year_in_review import _page
    entry, owner = _shared_or_404(db, token)
    canonical = challenges.SITE_URL + challenges.share_path(entry)
    challenge = challenges.challenge_for(entry.month)
    title = challenges.headline(owner.username, entry.month)
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    steps = "".join(
        f'<li class="recap-goal recap-goal--done"><strong>✓ {_e(step["label"])}</strong></li>'
        for step in challenge["steps"]
    )
    body = (f'<section class="title-section goal-reached" aria-label="Challenge complete">'
            f'<h2>{_e(challenge["name"])}</h2><p>{_e(challenge["tagline"])}</p>'
            f'<ol class="recap-goals">{steps}</ol>'
            f'<p class="title-sources">Completed {_e(entry.completed_at.strftime("%B %d, %Y").replace(" 0", " "))}</p></section>')
    guide = (f'<p><a href="/challenges/{_e(challenges.slug_for(entry.month))}">Read the challenge guide</a></p>'
             if challenges.is_curated(entry.month) and entry.month in challenges.public_months() else "")
    cta = ('<section class="profile-cta site-card"><div><h2>Take this month\'s challenge</h2>'
           '<p>Three small steps across movies, shows, anime, games, music and books, filled in from what you already track.</p>'
           f'{guide}</div>'
           + ('<a class="site-btn site-btn--primary" href="/#challenge">Open your challenge</a>' if signed_in
              else '<a class="site-btn site-btn--primary" href="/#signup">Start tracking free</a>')
           + '</section>')
    html = _page(
        title=f"{title} · OmniTrackr",
        description=f"{title} on OmniTrackr, the free tracker for movies, shows, anime, games, music and books.",
        canonical=canonical,
        card_url=f"{canonical}/card.png",
        eyebrow=f"Monthly challenge · {challenges.month_label(entry.month)}",
        heading=title,
        lead="Tracked on OmniTrackr, the free tracker for movies, shows, anime, games, music and books.",
        actions=(f'<button type="button" class="site-btn site-btn--ghost site-btn--sm" data-share '
                 f'data-share-title="{_e(title)}">Share</button>'),
        body=body + cta,
    )
    response = strict_html_response(html)
    response.headers["Cache-Control"] = "private, no-store" if signed_in else "public, max-age=300"
    response.headers["Vary"] = "Cookie"
    response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


def render_challenge_card(username: str, month: str) -> bytes:
    import io
    from PIL import Image, ImageDraw
    from .profiles import _fit, _font
    challenge = challenges.challenge_for(month)
    width, height = 1200, 630
    base = Image.new("RGB", (width, height), (11, 10, 24))
    glow = Image.new("RGB", (width, height), (11, 10, 24))
    glow_draw = ImageDraw.Draw(glow)
    for step in range(18, 0, -1):
        radius, mix = step * 34, (1 - step / 18) * 0.55
        shade = (int(11 + 150 * mix), int(10 + 60 * mix), int(24 + 140 * mix))
        glow_draw.ellipse((width - 160 - radius, -120 - radius, width - 160 + radius, -120 + radius), fill=shade)
    image = Image.blend(base, glow, 0.85)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, width - 40, height - 40), radius=28, outline=(60, 52, 110), width=2)
    draw.text((84, 78), f"OmniTrackr · {challenges.month_label(month)} challenge", font=_font(30, bold=True), fill=(94, 234, 212))
    name_font = _font(60, bold=True)
    draw.text((84, 136), _fit(draw, username, name_font, width - 168), font=name_font, fill=(245, 243, 255))
    big_font = _font(72, bold=True)
    draw.text((84, 222), _fit(draw, challenge["name"], big_font, width - 168), font=big_font, fill=(245, 243, 255))
    step_font = _font(30)
    for index, step in enumerate(challenge["steps"][:3]):
        draw.text((84, 330 + index * 52), _fit(draw, f"✓  {step['label']}", step_font, width - 168),
                  font=step_font, fill=(196, 181, 253))
    host = challenges.SITE_URL.replace("https://", "").replace("http://", "")
    draw.text((84, height - 100), f"{host} · take this month's challenge", font=_font(24), fill=(167, 160, 199))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


@router.get("/challenge/{token}/card.png", include_in_schema=False)
def shared_challenge_card(token: str, request: Request, db: Session = Depends(get_db)):
    entry, owner = _shared_or_404(db, token)
    key = (owner.id, f"challenge:{entry.month}:{owner.username}")
    png = _CARDS.get(key)
    if png is None:
        try:
            png = render_challenge_card(owner.username, entry.month)
        except Exception:
            raise HTTPException(status_code=404, detail="Card unavailable")
        _CARDS.put(key, png)
    return Response(content=png, media_type="image/png", headers={
        "Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff",
    })
