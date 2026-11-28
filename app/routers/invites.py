"""Friend invite links: create/share a link, the public /join page, and accepting from it."""
from __future__ import annotations

import os
from html import escape
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import friend_invites, funnel, taste_compare
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..site_chrome import apply_site_chrome, message_page
from .taste_compare import ASSET_VERSION as COMPARE_VERSION, CompareAnswers, _json_block, _pairs, _play_html

router = APIRouter(tags=["friends"])
SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
JOIN_JS_VERSION = "20261010-invite-2"


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


class InviteLinkOptions(BaseModel):
    reset: bool = False
    # True: the link opens on a taste test (the visitor rates a few of the member's titles).
    # False: a plain invite again. Left out: unchanged.
    taste_test: Optional[bool] = None


PLAIN_TEXT = ("Join me on OmniTrackr, a free tracker for movies, shows, anime, games, music and books. "
              "We'll be friends as soon as you sign up. Then we can see how well our taste matches.")
TEST_TEXT = ("How close is our taste? Rate a few things I've watched, played and read on OmniTrackr and see your score. "
             "It takes about a minute, no account needed. If you sign up from it we'll be friends.")


@router.post("/api/friends/invite-link")
def invite_link(request: Request, response: Response, options: InviteLinkOptions | None = None,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    """The member's reusable invite link (``reset`` swaps in a new one and retires the old)."""
    _private(response)
    options = options or InviteLinkOptions()
    invite = friend_invites.link_for(db, user, reset=options.reset)
    rated = len(taste_compare.deck(db, user))
    ready = rated >= taste_compare.MIN_DECK
    if options.taste_test is not None:
        friend_invites.set_taste_test(db, invite, options.taste_test and ready)
        if options.taste_test and ready:
            funnel.record("invite_test_sent", request)
    test_on = bool(invite.taste_test) and ready
    return {
        "url": f"{SITE_URL}/join/{invite.token}",
        "text": TEST_TEXT if test_on else PLAIN_TEXT,
        "taste_test": test_on,
        "taste_test_ready": ready,
        "rated_needed": max(0, taste_compare.MIN_DECK - rated),
    }


@router.post("/api/friends/invite/{token}/guess")
def invite_guess(token: str, payload: CompareAnswers, request: Request, response: Response, db: Session = Depends(get_db)):
    """Score a visitor's taste test answers against the inviter's ratings. Nothing is stored."""
    response.headers["Cache-Control"] = "no-store"
    inviter = friend_invites.taste_test_inviter(db, token)
    if inviter is None:
        raise HTTPException(404, "This taste test was switched off.")
    result = taste_compare.guess(db, inviter, _pairs(payload))
    if result["rated_count"]:
        funnel.record("invite_test_finished", request)
    return result


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def taste_test_page(inviter, token: str, cards: list[dict]) -> str:
    """/join/<token> when the member sent a taste test: rate their titles first, then join."""
    name = inviter.username
    join = f"/?invite={token}#signup"
    login = f"/?next={quote(f'/join/{token}', safe='')}#login"
    title = f"How close is your taste to {name}'s?"
    description = (f"{name} sent you a taste test. Rate a few of their movies, shows, games and books and see your score. "
                   "About a minute on OmniTrackr, no account needed.")
    initial = _e((name or "?")[:1].upper())
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_e(title)} · OmniTrackr</title>
  <meta name="description" content="{_e(description)}">
  <meta name="robots" content="noindex, nofollow">
  <meta property="og:site_name" content="OmniTrackr">
  <meta property="og:title" content="{_e(f'{name} sent you a taste test')}">
  <meta property="og:description" content="{_e(description)}">
  <meta property="og:type" content="website">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261122-cwv-1">
  <link rel="stylesheet" href="/static/title-page.css?v=20261009-take-1">
  <link rel="stylesheet" href="/static/profile-page.css?v=20261030-compare-1">
  <link rel="stylesheet" href="/static/taste-compare.css?v={COMPARE_VERSION}">
  <script src="/static/taste-compare.js?v={COMPARE_VERSION}" defer></script>
</head>
<body class="site title-page profile-page compare-page invite-test-page profile-page--guest">
  <!--SITE_NAV:-->
  <main>
    <section class="profile-hero compare-hero">
      <div class="site-wrap profile-hero__inner">
        <div class="profile-hero__avatar profile-hero__avatar--empty" aria-hidden="true">{initial}</div>
        <div class="profile-hero__copy">
          <p class="site-eyebrow">{_e(name)} sent you a taste test</p>
          <h1>{_e(title)}</h1>
          <p class="profile-hero__bio">Rate a few things {_e(name)} has watched, played or read. Skip what you haven't seen.
          Three answers get you a score, plus where you agree and what {_e(name)} thinks you should try next.</p>
        </div>
      </div>
    </section>
    <div class="site-wrap title-body compare-body">
      <section class="compare" id="tasteCompare" data-owner-id="{inviter.id}" data-owner-name="{_e(name)}"
        data-signed-in="false" data-link="/join/{_e(token)}" data-profile="/" data-min-answers="{taste_compare.MIN_ANSWERS}"
        data-guess-url="/api/friends/invite/{_e(token)}/guess" data-join-url="{_e(join)}" data-share="off"
        data-invite="true" data-signup-event="invite_test_signup_clicked">
        <div class="compare-screen compare-intro" data-compare-screen="intro">
          <p class="compare-intro__lead" data-compare-intro-lead>{len(cards)} titles to rate. Skip anything you haven't seen; three answers are enough for a score.</p>
          <button type="button" class="site-btn site-btn--primary compare-start" data-compare-action="start">Start the taste test</button>
        </div>
        {_play_html(name)}
        <div class="compare-screen compare-result" data-compare-screen="result" hidden tabindex="-1"></div>
        {_json_block(cards)}
        <noscript><p>The taste test needs JavaScript. You can still <a href="{_e(join)}">join {_e(name)} on OmniTrackr</a>.</p></noscript>
      </section>
      <section class="profile-cta invite-test-join site-card">
        <div>
          <p class="site-eyebrow">Free on OmniTrackr</p>
          <h2>Join {_e(name)} on OmniTrackr</h2>
          <p>Track the movies, shows, anime, games, music and books you love in one free library. Sign up through this link
          and you and {_e(name)} become friends, so you see what each other finishes and get a Taste Match across both libraries.</p>
        </div>
        <div class="profile-cta__actions">
          <a class="site-btn site-btn--primary" href="{_e(join)}">Join for free</a>
          <a class="site-btn site-btn--ghost" href="{_e(login)}">I already have an account</a>
        </div>
      </section>
      <p class="title-sources">{_e(name)} chose to send this taste test. Private categories are never part of it, and reviews and notes are never shown.</p>
    </div>
  </main>
  <!--SITE_FOOTER-->
</body>
</html>"""
    page = apply_site_chrome(page)
    # Every sign-up button on the page (header and footer too) carries the invite.
    return page.replace('href="/#signup"', f'href="{_e(join)}"')


@router.post("/api/friends/invite/{token}/accept")
def accept_invite(token: str, request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    inviter = friend_invites.inviter_for(db, token)
    if inviter is None:
        raise HTTPException(404, "This invite link has expired or was replaced.")
    try:
        added = friend_invites.befriend(db, inviter, user, joined=False)
    except ValueError as error:
        raise HTTPException(400, str(error))
    return {"friend": inviter.username, "added": added}


@router.get("/join/{token}", include_in_schema=False)
def join_page(token: str, request: Request, db: Session = Depends(get_db)):
    inviter = friend_invites.inviter_for(db, token)
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    cards = []
    if inviter is not None and not signed_in and friend_invites.taste_test_inviter(db, token) is not None:
        cards = taste_compare.deck(db, inviter)
    if len(cards) >= taste_compare.MIN_DECK:
        funnel.record("invite_test_opened", request)
        response = strict_html_response(taste_test_page(inviter, token, cards))
    elif inviter is None:
        page = message_page("Invite link expired", "This invite link has expired",
                            "Ask your friend for a fresh link, or start your own free library now.",
                            actions=(("Start tracking for free", "/#signup"), ("See what OmniTrackr does", "/about")))
        response = strict_html_response(page, status_code=404)
    else:
        name = inviter.username
        page = message_page(
            f"{name} invited you", f"{name} invited you to OmniTrackr",
            f"Track the movies, shows, anime, games, music and books you love in one free library. "
            f"Join through this link and you and {name} become friends, so you can see what each other is into "
            f"and get a Taste Match: your shared favorites, your biggest disagreements and what to try next.",
            eyebrow="You're invited",
            actions=(("Join for free", f"/?invite={token}#signup"),
                     ("I already have an account", f"/?next={quote(f'/join/{token}', safe='')}#login")),
        )
        # Every sign-up button on the page (header and footer too) carries the invite.
        page = page.replace('href="/#signup"', f'href="/?invite={token}#signup"')
        if signed_in:
            start = page.index('<div class="site-message__actions">')
            end = page.index("</div>", start) + len("</div>")
            page = (page[:start]
                    + '<div class="site-message__actions">'
                    f'<button type="button" class="site-btn site-btn--primary" data-join-accept data-token="{escape(token, quote=True)}">'
                    f'Add {escape(name)} as a friend</button>'
                    '<a class="site-btn site-btn--ghost" href="/">Go to my library</a></div>'
                    '<p class="site-message__status" data-join-status role="status" aria-live="polite"></p>'
                    + page[end:])
            page = page.replace("</body>", f'<script src="/static/join.js?v={JOIN_JS_VERSION}" defer></script>\n</body>', 1)
        response = strict_html_response(page)
    _private(response)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Vary"] = "Cookie"
    return response
