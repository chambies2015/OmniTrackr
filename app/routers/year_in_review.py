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

from .. import auth, models, year_in_review
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..site_chrome import apply_site_chrome
from .profiles import _CardCache, _fit, _font

router = APIRouter(tags=["year-in-review"])
SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
ASSET_VERSION = "20261008-recap-1"
TITLE_CSS_VERSION = "20261002-profiles-1"
FIRST_TRACKED_NOTE = {
    2026: "OmniTrackr started keeping a dated journal in September 2026 and add dates in October, "
          "so this year's recap covers the autumn. Next year's will cover all twelve months.",
}
_CARDS = _CardCache(size=96)


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
    return f'<div class="recap-highlights">{"".join(bits)}</div>' if bits else ""


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
        _highlights(recap),
        _title_list(recap.get("top_rated", []), "Highest rated finishes", "recap-top"),
        _title_list(recap.get("favorites", []), "Marked as favorites", "recap-favorites"),
        _categories(recap),
        _months(recap),
    ]
    note = FIRST_TRACKED_NOTE.get(recap.get("year"))
    if note:
        parts.append(f'<p class="title-sources">{_e(note)}</p>')
    return "".join(parts)


def _page(*, title: str, description: str, canonical: str, card_url: str, eyebrow: str, heading: str,
          lead: str, actions: str, body: str, extra: str = "", script: bool = False) -> str:
    scripts = (f'<script src="/static/year-in-review.js?v={ASSET_VERSION}" defer></script>' if script
               else '<script src="/static/share.js?v=20261004-share-1" defer></script>')
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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/title-page.css?v={TITLE_CSS_VERSION}">
  <link rel="stylesheet" href="/static/profile-page.css?v=20261004-share-1">
  <link rel="stylesheet" href="/static/year-in-review.css?v={ASSET_VERSION}">
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
  <!--SITE_FOOTER-->
</body>
</html>"""
    return apply_site_chrome(page)


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
          <button type="button" class="site-btn site-btn--ghost" data-recap-unshare{'' if state['shared'] else ' hidden'}>Stop sharing</button>
        </div>
        <img class="recap-share__card" src="/api/year-in-review/{year}/card.png" alt="Your {year} in review card" width="600" height="315" loading="lazy">
      </section>"""
    html = _page(
        title=f"Your {year} in review · OmniTrackr",
        description="Your private Year in Review on OmniTrackr.",
        canonical=f"{SITE_URL}/year-in-review/{year}",
        card_url=f"{SITE_URL}/omnitrackr_vortex.png",
        eyebrow="Year in Review · private to you",
        heading=f"Your {year} in media{so_far}",
        lead=_summary(recap) + ".",
        actions=f'<span class="recap-years">{years}</span>',
        body=_body(recap, private=True) + share_box,
        script=True,
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
    cta = ("" if signed_in else
           f'<section class="profile-cta site-card"><div><h2>Make your own {share.year} in review</h2>'
           '<p>OmniTrackr is a free tracker for movies, shows, anime, games, music and books. '
           'Log what you finish and get a recap like this one every December.</p></div>'
           '<a class="site-btn site-btn--primary" href="/#signup">Start tracking free</a></section>')
    html = _page(
        title=f"{name}'s {share.year} in review · OmniTrackr",
        description=f"{name}'s {share.year} in media on OmniTrackr: {_summary(recap)}.",
        canonical=canonical,
        card_url=f"{canonical}/card.png",
        eyebrow=f"Year in Review · {share.year}",
        heading=f"{name}'s {share.year} in media",
        lead=_summary(recap) + ".",
        actions=(f'<button type="button" class="site-btn site-btn--ghost site-btn--sm" data-share '
                 f'data-share-title="{_e(name)}\'s {share.year} in review">Share</button>'),
        body=_body(recap, private=False) + cta,
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


def _png_response(user_id: int, username: str, recap: dict, *, private: bool = False):
    fingerprint = hashlib.sha256(json.dumps([username, recap], sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    key = (user_id, fingerprint)
    png = _CARDS.get(key)
    if png is None:
        try:
            png = render_card(username, recap)
        except Exception:
            raise HTTPException(status_code=404, detail="Card unavailable")
        _CARDS.put(key, png)
    return Response(content=png, media_type="image/png", headers={
        "Cache-Control": "private, no-store" if private else "public, max-age=3600",
        "ETag": f'"{fingerprint}"', "X-Content-Type-Options": "nosniff",
    })
