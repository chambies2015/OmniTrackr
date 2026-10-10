"""Friend invite links: create/share a link, the public /join page, and accepting from it."""
from __future__ import annotations

import os
from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import friend_invites
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..site_chrome import message_page

router = APIRouter(tags=["friends"])
SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
JOIN_JS_VERSION = "20261010-invite-2"


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


class InviteLinkOptions(BaseModel):
    reset: bool = False


@router.post("/api/friends/invite-link")
def invite_link(request: Request, response: Response, options: InviteLinkOptions | None = None,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    """The member's reusable invite link (``reset`` swaps in a new one and retires the old)."""
    _private(response)
    invite = friend_invites.link_for(db, user, reset=bool(options and options.reset))
    return {
        "url": f"{SITE_URL}/join/{invite.token}",
        "text": f"Join me on OmniTrackr, a free tracker for movies, shows, anime, games, music and books. "
                "We'll be friends as soon as you sign up.",
    }


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
    if inviter is None:
        page = message_page("Invite link expired", "This invite link has expired",
                            "Ask your friend for a fresh link, or start your own free library now.",
                            actions=(("Start tracking for free", "/#signup"), ("See what OmniTrackr does", "/about")))
        response = strict_html_response(page, status_code=404)
    else:
        name = inviter.username
        signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
        page = message_page(
            f"{name} invited you", f"{name} invited you to OmniTrackr",
            f"Track the movies, shows, anime, games, music and books you love in one free library. "
            f"Join through this link and you and {name} become friends, so you can see what each other is into.",
            eyebrow="You're invited",
            actions=(("Join for free", f"/?invite={token}#signup"),
                     ("I already have an account", f"/?next={quote(f'/join/{token}', safe='')}#landing-auth")),
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
