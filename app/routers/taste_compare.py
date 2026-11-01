"""Compare tastes with a member: /u/<name>/match, its share card, and the deck endpoints."""
from __future__ import annotations

import hashlib
import io
import json
import os
from html import escape
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import funnel, models, public_profiles, taste_compare, taste_match
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..integer_bounds import PositiveDatabaseId
from ..progress import lock_progress_owner
from ..site_chrome import apply_site_chrome
from .profiles import _CardCache, _avatar_html, _card_avatar, _fit, _font, _viewer_id

router = APIRouter(tags=["taste-match"])
SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
ASSET_VERSION = "20261030-compare-1"
_CARD_CACHE = _CardCache(size=96)


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _json_block(data) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return f'<script type="application/json" id="compareDeck">{payload}</script>'


# ---------------------------------------------------------------- page

def _owner_panel(user: models.User, cards: list[dict]) -> str:
    link = SITE_URL + taste_compare.link_path(user)
    if len(cards) < taste_compare.MIN_DECK:
        ready = (f'<p class="compare-owner__warn">Your link needs at least {taste_compare.MIN_DECK} rated titles in categories '
                 f'you share. You have {len(cards)} right now, so visitors will see a "not ready yet" note. '
                 '<a href="/">Rate a few more in your library</a>.</p>')
    else:
        titles = "".join(f'<li>{_e(card["title"])} <span>{_e(card["label"])}</span></li>' for card in cards)
        ready = (f'<h2 class="compare-owner__heading">What people will rate</h2>'
                 f'<p class="compare-owner__hint">Picked from your rated titles: the ones most members know, mostly favorites '
                 f'plus a few you rated lower. Your ratings only show up after someone answers.</p>'
                 f'<ol class="compare-owner__deck">{titles}</ol>')
    return (
        '<section class="compare-owner site-card" aria-labelledby="compare-owner-title">'
        '<h2 id="compare-owner-title">Share it anywhere</h2>'
        '<p>Post it in a group chat or on your socials. Anyone can rate a handful of your titles, '
        'see how close their taste is to yours, and start a library of their own.</p>'
        '<div class="compare-owner__row">'
        f'<input type="text" readonly id="compareLink" value="{_e(link)}" aria-label="Your compare link">'
        '<button type="button" class="site-btn site-btn--primary site-btn--sm" data-compare-copy>Copy link</button>'
        '<button type="button" class="site-btn site-btn--ghost site-btn--sm" data-compare-share-link>Share</button>'
        '</div>'
        f'<img class="compare-owner__card" src="{_e(taste_compare.link_path(user))}/card.png" width="1200" height="630" '
        'alt="The preview people see when you post your link" loading="lazy">'
        f'{ready}'
        '<p class="compare-owner__off">Want to stop? Switch off "Let people compare tastes with me" in '
        '<a href="/#public-profile">your public profile settings</a>.</p>'
        '</section>'
    )


def _not_ready(name: str, path: str) -> str:
    return (f'<section class="compare-empty site-card"><h2>Not ready yet</h2>'
            f'<p>{_e(name)} hasn\'t rated enough titles to compare with. Check back soon, or look around '
            f'<a href="{_e(path)}">their profile</a> in the meantime.</p></section>')


def _play_html(name: str) -> str:
    return (
        '<div class="compare-screen compare-play" data-compare-screen="play" hidden>'
        '<div class="compare-progress"><div class="compare-progress__bar"><span data-compare-bar></span></div>'
        '<p class="compare-progress__text" data-compare-count aria-live="polite"></p></div>'
        '<article class="compare-card" data-compare-card aria-live="polite"></article>'
        '<div class="compare-answers" role="group" aria-label="Your answer">'
        '<div class="compare-answers__seen">'
        '<button type="button" class="compare-answer compare-answer--loved" data-compare-answer="loved">Loved it</button>'
        '<button type="button" class="compare-answer compare-answer--liked" data-compare-answer="liked">Liked it</button>'
        '<button type="button" class="compare-answer compare-answer--meh" data-compare-answer="meh">Not for me</button>'
        '</div><div class="compare-answers__other">'
        '<button type="button" class="compare-answer compare-answer--want" data-compare-answer="want">Want to try</button>'
        '<button type="button" class="compare-answer compare-answer--skip" data-compare-answer="skip">Haven\'t seen it</button>'
        '</div></div>'
        '<div class="compare-controls"><button type="button" class="compare-link" data-compare-action="back" disabled>Back</button>'
        f'<button type="button" class="compare-link compare-finish" data-compare-action="finish" hidden>See how I match with {_e(name)}</button></div>'
        '</div>'
    )


def render_page(user: models.User, cards: list[dict], *, signed_in: bool, is_owner: bool) -> str:
    name = user.username
    profile_path = public_profiles.profile_path(user)
    path = taste_compare.link_path(user)
    canonical = SITE_URL + path
    title = f"How does your taste compare with {name}'s?"
    description = (f"Rate a few of {name}'s movies, shows, games, books and music, and see how close your taste is. "
                   "Takes about a minute on OmniTrackr, no account needed.")
    ready = len(cards) >= taste_compare.MIN_DECK
    if is_owner:
        heading, lead = "Your compare link", "Share it and see who has the same taste as you."
    elif signed_in:
        heading = title
        lead = (f"Your library is lined up with {name}'s first. Rate any of their titles you haven't tracked "
                "to sharpen the score; your answers go into your library.")
    else:
        heading = title
        lead = (f"Rate up to {len(cards) or taste_compare.DECK_SIZE} of {name}'s titles, then see your score, "
                "where you agree and what to try next. About a minute, no account needed.")
    if is_owner:
        body = _owner_panel(user, cards)
    elif not ready and not signed_in:
        body = _not_ready(name, profile_path)
    else:
        intro_button = ('<button type="button" class="site-btn site-btn--primary compare-start" data-compare-action="start">'
                        f'Start rating</button>') if cards else ""
        body = (
            f'<section class="compare" id="tasteCompare" data-owner-id="{user.id}" data-owner-name="{_e(name)}" '
            f'data-signed-in="{"true" if signed_in else "false"}" data-link="{_e(path)}" '
            f'data-profile="{_e(profile_path)}" data-min-answers="{taste_compare.MIN_ANSWERS}">'
            '<div class="compare-screen compare-intro" data-compare-screen="intro">'
            '<div class="compare-library" data-compare-library hidden></div>'
            f'<p class="compare-intro__lead" data-compare-intro-lead>{_e(len(cards))} titles to rate. '
            'Skip anything you haven\'t seen; three answers are enough for a score.</p>'
            f'{intro_button}'
            '</div>'
            f'{_play_html(name)}'
            '<div class="compare-screen compare-result" data-compare-screen="result" hidden tabindex="-1"></div>'
            f'{_json_block(cards)}'
            '<noscript><p>Comparing tastes needs JavaScript.</p></noscript>'
            '</section>'
        )
    cta = ("" if signed_in else
           '<section class="profile-cta site-card"><div><p class="site-eyebrow">Free on OmniTrackr</p>'
           '<h2>Get a compare link of your own</h2>'
           '<p>Track what you watch, play, read and hear, rate what you finish, and see who shares your taste.</p></div>'
           '<div class="profile-cta__actions"><a class="site-btn site-btn--primary" href="/#signup" data-compare-join>Start tracking free</a>'
           '<a class="site-btn site-btn--ghost" href="/taste-quiz">Take the taste quiz</a></div></section>')
    member_cta = ("" if not signed_in or is_owner else
                  '<p class="compare-own"><strong>Want people to compare with you?</strong> Turn on '
                  '"Let people compare tastes with me" in <a href="/#public-profile">your public profile settings</a> '
                  'and share your own link.</p>')
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_e(title)} · OmniTrackr</title>
  <meta name="description" content="{_e(description)}">
  <meta name="robots" content="noindex, follow">
  <link rel="canonical" href="{_e(canonical)}">
  <meta property="og:site_name" content="OmniTrackr">
  <meta property="og:title" content="{_e(title)}">
  <meta property="og:description" content="{_e(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{_e(canonical)}">
  <meta property="og:image" content="{_e(canonical + '/card.png')}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="{_e(f'Compare tastes with {name} on OmniTrackr')}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{_e(title)}">
  <meta name="twitter:description" content="{_e(description)}">
  <meta name="twitter:image" content="{_e(canonical + '/card.png')}">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">
  <link rel="stylesheet" href="/static/title-page.css?v=20261009-take-1">
  <link rel="stylesheet" href="/static/profile-page.css?v=20261030-compare-1">
  <link rel="stylesheet" href="/static/taste-compare.css?v={ASSET_VERSION}">
  <script src="/static/taste-compare.js?v={ASSET_VERSION}" defer></script>
</head>
<body class="site title-page profile-page compare-page{'' if signed_in else ' profile-page--guest'}">
  <!--SITE_NAV:-->
  <main>
    <section class="profile-hero compare-hero">
      <div class="site-wrap profile-hero__inner">
        {_avatar_html(user)}
        <div class="profile-hero__copy">
          <p class="site-eyebrow"><a href="{_e(profile_path)}">{_e(name)}</a> · Compare tastes</p>
          <h1>{_e(heading)}</h1>
          <p class="profile-hero__bio">{_e(lead)}</p>
        </div>
      </div>
    </section>
    <div class="site-wrap title-body compare-body">
      {body}
      {member_cta}
      {cta}
      <p class="title-sources">{_e(name)} chose to share this link. Private categories are never part of it, and reviews and notes are never shown.</p>
    </div>
  </main>
  <!--SITE_FOOTER-->
</body>
</html>"""
    return apply_site_chrome(page)


def _owner_or_404(db: Session, user: Optional[models.User]) -> models.User:
    if taste_compare.link_profile(db, user) is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return user


def _page_response(request: Request, db: Session, user: Optional[models.User]):
    user = _owner_or_404(db, user)
    canonical = taste_compare.link_path(user)
    if request.url.path.rstrip("/") != canonical:
        return RedirectResponse(canonical, status_code=301)
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    viewer_id = _viewer_id(request, db) if signed_in else None
    is_owner = signed_in and viewer_id == user.id
    viewer = db.get(models.User, viewer_id) if viewer_id and not is_owner else None
    if signed_in and viewer is not None:
        cards = taste_compare.deck_for_member(db, user, viewer)
    else:
        cards = taste_compare.deck(db, user)
    if not signed_in:
        funnel.record("compare_link_opened", request)
    response = strict_html_response(render_page(user, cards, signed_in=signed_in, is_owner=is_owner))
    response.headers["Cache-Control"] = "private, no-store" if signed_in else "public, max-age=300"
    response.headers["Vary"] = "Cookie"
    response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


@router.get("/u/id/{user_id:database_id}/match", include_in_schema=False)
def compare_page_by_id(user_id: PositiveDatabaseId, request: Request, db: Session = Depends(get_db)):
    return _page_response(request, db, public_profiles.find_user_by_id(db, user_id))


@router.get("/u/{handle}/match", include_in_schema=False)
def compare_page(handle: str, request: Request, db: Session = Depends(get_db)):
    return _page_response(request, db, public_profiles.find_user(db, handle))


# ---------------------------------------------------------------- share card

def _wrap(draw, text: str, font, width: int, lines: int) -> list[str]:
    words, rows, current = text.split(), [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= width or not current:
            current = trial
        else:
            rows.append(current)
            current = word
    if current:
        rows.append(current)
    if len(rows) > lines:
        rows = rows[:lines - 1] + [_fit(draw, " ".join(rows[lines - 1:]), font, width)]
    return rows


def render_card(user: models.User, cards: list[dict]) -> bytes:
    from PIL import Image, ImageDraw
    width, height = 1200, 630
    violet, teal = (139, 92, 246), (45, 212, 191)
    image = Image.new("RGB", (width, height), (11, 10, 24))
    glow = Image.new("RGB", (width, height), (11, 10, 24))
    glow_draw = ImageDraw.Draw(glow)
    # Two soft glows, one per "taste", overlapping in the middle.
    for center, rgb in (((300, 560), violet), ((900, 80), teal)):
        for step in range(16, 0, -1):
            radius = step * 30
            mix = (1 - step / 16) * 0.45
            shade = tuple(int(base + (c - base) * mix) for c, base in zip(rgb, (11, 10, 24)))
            glow_draw.ellipse((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), fill=shade)
    image = Image.blend(image, glow, 0.85)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, width - 40, height - 40), radius=28, outline=(60, 52, 110), width=2)
    draw.text((84, 78), "OmniTrackr", font=_font(30, bold=True), fill=(196, 181, 253))
    draw.text((width - 84 - draw.textlength("COMPARE TASTES", font=_font(24, bold=True)), 84), "COMPARE TASTES",
              font=_font(24, bold=True), fill=(94, 234, 212))

    avatar, _, mask = _card_avatar(user, violet)
    image.paste(avatar, (84, 150), mask)
    draw = ImageDraw.Draw(image)
    # The visitor's side: an empty ring with a question mark, overlapping the member's avatar.
    ring_left = 84 + 104
    draw.ellipse((ring_left, 150, ring_left + 140, 290), fill=(24, 20, 48), outline=teal, width=4)
    mark_font = _font(64, bold=True)
    box = draw.textbbox((0, 0), "?", font=mark_font)
    draw.text((ring_left + 70 - (box[2] - box[0]) / 2 - box[0], 220 - (box[3] - box[1]) / 2 - box[1]), "?",
              font=mark_font, fill=(153, 246, 228))

    headline_font = _font(56, bold=True)
    left = 380
    rows = _wrap(draw, f"How does your taste compare with {user.username}'s?", headline_font, width - left - 84, 3)
    y = 150
    for row in rows:
        draw.text((left, y), row, font=headline_font, fill=(245, 243, 255))
        y += 68
    titles = [card["title"] for card in cards[:4]]
    if titles:
        sub = _font(28)
        draw.text((84, 380), "Rate a few of their picks:", font=sub, fill=(167, 160, 199))
        draw.text((84, 422), _fit(draw, " · ".join(titles), _font(30, bold=True), width - 168),
                  font=_font(30, bold=True), fill=(214, 209, 240))
    invite_font = _font(26, bold=True)
    invite = "Find out in a minute"
    invite_width = draw.textlength(invite, font=invite_font) + 52
    draw.rounded_rectangle((width - 84 - invite_width, height - 118, width - 84, height - 68), radius=25, fill=(124, 58, 237))
    draw.text((width - 84 - invite_width + 26, height - 107), invite, font=invite_font, fill=(255, 255, 255))
    path_text = SITE_URL.replace("https://", "").replace("http://", "") + taste_compare.link_path(user)
    draw.text((84, height - 104), _fit(draw, path_text, _font(24), width - 168 - invite_width - 24),
              font=_font(24), fill=(167, 160, 199))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _card_response(db: Session, user: Optional[models.User]):
    user = _owner_or_404(db, user)
    cards = taste_compare.deck(db, user)
    fingerprint = hashlib.sha256(repr((
        user.username, hashlib.sha256(user.profile_picture_data or b"").hexdigest(), [c["title"] for c in cards[:4]],
    )).encode("utf-8")).hexdigest()[:16]
    key = (user.id, fingerprint)
    png = _CARD_CACHE.get(key)
    if png is None:
        try:
            png = render_card(user, cards)
        except Exception:
            raise HTTPException(status_code=404, detail="Card unavailable")
        _CARD_CACHE.put(key, png)
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600", "ETag": f'"{fingerprint}"',
                             "X-Content-Type-Options": "nosniff"})


@router.get("/u/id/{user_id:database_id}/match/card.png", include_in_schema=False)
def compare_card_by_id(user_id: PositiveDatabaseId, request: Request, db: Session = Depends(get_db)):
    return _card_response(db, public_profiles.find_user_by_id(db, user_id))


@router.get("/u/{handle}/match/card.png", include_in_schema=False)
def compare_card(handle: str, request: Request, db: Session = Depends(get_db)):
    return _card_response(db, public_profiles.find_user(db, handle))


# ---------------------------------------------------------------- API

Answer = Literal["loved", "liked", "meh", "want", "skip"]


class CompareAnswer(BaseModel):
    id: str = Field(..., min_length=3, max_length=40)
    answer: Answer


class CompareAnswers(BaseModel):
    answers: list[CompareAnswer] = Field(default_factory=list, max_length=taste_compare.DECK_SIZE * 2)
    # "deck" when a member just rated the deck; "guest" when answers saved before sign-up are moved in.
    source: Literal["deck", "guest"] = "deck"


def _pairs(payload: CompareAnswers) -> list[tuple[str, str]]:
    seen, pairs = set(), []
    for item in payload.answers:
        if item.id not in seen:
            seen.add(item.id)
            pairs.append((item.id, item.answer))
    return pairs


def _linked_owner(db: Session, owner_id: int) -> models.User:
    return _owner_or_404(db, public_profiles.find_user_by_id(db, owner_id))


def _member_match(db: Session, viewer: models.User, owner: models.User) -> dict:
    result = taste_match.match(db, viewer, owner)
    result.pop("friend", None)
    result["owner"] = {"id": owner.id, "username": owner.username}
    return result


@router.post("/api/taste-match/u/{owner_id}/guess")
def compare_guess(owner_id: PositiveDatabaseId, payload: CompareAnswers, request: Request, response: Response,
                  db: Session = Depends(get_db)):
    """Score a visitor's answers against the member's ratings. Nothing is stored."""
    response.headers["Cache-Control"] = "no-store"
    owner = _linked_owner(db, owner_id)
    result = taste_compare.guess(db, owner, _pairs(payload))
    if result["rated_count"]:
        funnel.record("compare_finished", request)
    return result


@router.get("/api/taste-match/u/{owner_id}")
def compare_library(owner_id: PositiveDatabaseId, request: Request, response: Response, user=Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """A signed-in member's full library lined up with the member who shared the link."""
    response.headers["Cache-Control"] = "private, no-store"
    owner = _linked_owner(db, owner_id)
    if owner.id == user.id:
        raise HTTPException(400, "That's your own link.")
    return _member_match(db, user, owner)


@router.post("/api/taste-match/u/{owner_id}/answers")
def compare_save(owner_id: PositiveDatabaseId, payload: CompareAnswers, request: Request, response: Response,
                 user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Put a member's deck answers into their library, then return the full match."""
    response.headers["Cache-Control"] = "private, no-store"
    owner = _linked_owner(db, owner_id)
    if owner.id == user.id:
        raise HTTPException(400, "That's your own link.")
    lock_progress_owner(db, user.id)
    saved = taste_compare.save_answers(db, user, owner, _pairs(payload))
    db.commit()
    if saved["added"]:
        funnel.record("compare_imported" if payload.source == "guest" else "compare_finished", request)
    return {**saved, "match": _member_match(db, user, owner)}
