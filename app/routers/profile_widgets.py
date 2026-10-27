"""Embeddable profile widgets: /u/<username>/widget/<kind>.png and the /u/<username>/widgets embed page."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import models, profile_widgets, public_profiles
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_db
from ..integer_bounds import PositiveDatabaseId
from ..site_chrome import apply_site_chrome
from .profiles import TITLE_CSS_VERSION, _e, _viewer_id

router = APIRouter(tags=["profiles"])
CSS_VERSION = "20261027-widgets-1"
FORMATS = (
    ("html", "HTML", "Blogs, personal sites, Notion and GitHub READMEs"),
    ("markdown", "Markdown", "Reddit, GitHub, Obsidian and most wikis"),
    ("bbcode", "BBCode", "Forums and forum signatures"),
    ("image", "Image link", "Discord, chats, or anywhere that shows an image from a link"),
)


def _widget_response(db: Session, user: Optional[models.User], kind: str, theme: str, scale: str):
    profile = public_profiles.visible_profile(db, user)
    if profile is None or kind not in profile_widgets.KINDS:
        raise HTTPException(status_code=404, detail="Widget not found")
    theme = theme if theme in profile_widgets.THEMES else "dark"
    scale_value = 2 if scale == "2" else 1
    try:
        found = profile_widgets.image(db, user, profile, kind, theme, scale_value)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=404, detail="Widget unavailable")
    if found is None:
        raise HTTPException(status_code=404, detail="Widget not found")
    png, etag = found
    # Forums and chat apps fetch the image through their own proxies, so a short public cache keeps it fresh.
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=900", "ETag": f'"{etag}"',
                             "X-Content-Type-Options": "nosniff", "X-Robots-Tag": "noindex",
                             "Cross-Origin-Resource-Policy": "cross-origin"})


@router.get("/u/id/{user_id:database_id}/widget/{kind}.png", include_in_schema=False)
def widget_by_id(user_id: PositiveDatabaseId, kind: str, request: Request, theme: str = "dark", scale: str = "1",
                 db: Session = Depends(get_db)):
    return _widget_response(db, public_profiles.find_user_by_id(db, user_id), kind, theme, scale)


@router.get("/u/{handle}/widget/{kind}.png", include_in_schema=False)
def widget(handle: str, kind: str, request: Request, theme: str = "dark", scale: str = "1",
           db: Session = Depends(get_db)):
    return _widget_response(db, public_profiles.find_user(db, handle), kind, theme, scale)


# ---------------------------------------------------------------- embed page

def _format_html(user: models.User, kind: str) -> str:
    themed = {theme: profile_widgets.snippets(user, kind, theme) for theme in profile_widgets.THEMES}
    rows = ""
    for key, label, hint in FORMATS:
        field_id = f"widget-{kind}-{key}"
        rows += (f'<div class="widget-code"><label for="{field_id}"><strong>{_e(label)}</strong> '
                 f'<small>{_e(hint)}</small></label>'
                 f'<div class="widget-code__row"><textarea id="{field_id}" readonly rows="{3 if key == "html" else 2}" '
                 f'spellcheck="false" data-dark="{_e(themed["dark"][key])}" data-light="{_e(themed["light"][key])}">'
                 f'{_e(themed["dark"][key])}</textarea>'
                 f'<button type="button" class="site-btn site-btn--ghost site-btn--sm" data-widget-copy="{field_id}">Copy</button>'
                 f'</div></div>')
    return rows


def _widget_card(user: models.User, kind: str) -> str:
    title, blurb = profile_widgets.LABELS[kind]
    # Relative addresses for the previews, so they load from whichever host serves the page.
    site = profile_widgets.SITE_URL
    dark = profile_widgets.image_url(user, kind, "dark", 2).removeprefix(site)
    light = profile_widgets.image_url(user, kind, "light", 2).removeprefix(site)
    height = profile_widgets.HEIGHTS[kind]
    return (f'<section class="title-section widget-card" aria-labelledby="widget-{kind}">'
            f'<h2 id="widget-{kind}">{_e(title)}</h2><p class="widget-card__blurb">{_e(blurb)}</p>'
            f'<div class="widget-preview"><img src="{_e(dark)}" data-dark="{_e(dark)}" data-light="{_e(light)}" '
            f'alt="{_e(title)} widget preview" width="{profile_widgets.WIDTH}" height="{height}" loading="lazy"></div>'
            f'<details class="widget-codes"><summary>Get the embed code</summary>{_format_html(user, kind)}</details>'
            f'</section>')


def _missing_note(kinds: list[str]) -> str:
    missing = [kind for kind in profile_widgets.KINDS if kind not in kinds]
    if not missing:
        return ""
    reasons = {
        "stats": "Library stats appear when your profile shows library counts and your statistics aren't private.",
        "recent": "Recently finished appears when you switch on the diary.",
        "favorites": "Favorites appears when your profile shows favorites or you pin titles to your showcase.",
    }
    items = "".join(f"<li>{_e(reasons[kind])}</li>" for kind in missing)
    return (f'<div class="profile-owner-note widget-missing"><p>Only you see this. More widgets unlock from '
            f'<a href="/#public-profile">Account → Public profile</a>:</p><ul>{items}</ul></div>')


def render_page(db: Session, user: models.User, profile: models.PublicProfile, *, signed_in: bool, is_owner: bool) -> str:
    name = user.username
    path = public_profiles.profile_path(user)
    kinds = profile_widgets.available(db, user, profile)
    cards = "".join(_widget_card(user, kind) for kind in kinds)
    if not cards:
        cards = f'<p class="title-empty">{_e(name)} hasn\'t shared anything that fits in a widget yet.</p>'
    intro = (f"Put your OmniTrackr profile on your blog, forum signature, GitHub README or Discord. "
             f"Widgets update by themselves as you track, and only show what your public profile already shows."
             if is_owner else
             f"Images of {name}'s public profile that update as they track. Each one links back to their profile.")
    discord = ('<section class="title-section widget-card"><h2>Discord, X, Bluesky and group chats</h2>'
               '<p class="widget-card__blurb">Paste your profile link. It unfolds into a big preview card by itself.</p>'
               f'<div class="widget-code__row"><input type="text" readonly id="widget-profile-link" '
               f'value="{_e(profile_widgets.link_url(user))}" aria-label="Profile link">'
               '<button type="button" class="site-btn site-btn--ghost site-btn--sm" data-widget-copy="widget-profile-link">Copy</button>'
               '</div></section>')
    cta = ("" if signed_in else
           '<section class="profile-cta site-card"><div><h2>Make widgets of your own</h2>'
           '<p>OmniTrackr is free. Track movies, shows, anime, games, music and books, then show them off anywhere.</p></div>'
           '<a class="site-btn site-btn--primary" href="/#signup">Start tracking free</a></section>')
    owner = _missing_note(kinds) if is_owner else ""
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_e(name)}'s profile widgets · OmniTrackr</title>
  <meta name="description" content="{_e(f"Embeddable OmniTrackr widgets for {name}'s public profile.")}">
  <meta name="robots" content="noindex, follow">
  <link rel="canonical" href="{_e(profile_widgets.SITE_URL + path + '/widgets')}">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">
  <link rel="stylesheet" href="/static/title-page.css?v={TITLE_CSS_VERSION}">
  <link rel="stylesheet" href="/static/profile-page.css?v=20261022-diary-1">
  <link rel="stylesheet" href="/static/profile-widgets.css?v={CSS_VERSION}">
  <script src="/static/profile-widgets.js?v={CSS_VERSION}" defer></script>
</head>
<body class="site title-page profile-page widgets-page">
  <!--SITE_NAV:-->
  <main>
    <section class="profile-hero widgets-hero">
      <div class="site-wrap widgets-hero__inner">
        <p class="site-eyebrow"><a href="{_e(path)}">{_e(name)}</a> · Widgets</p>
        <h1>{"Your profile, anywhere" if is_owner else f"{_e(name)}'s profile widgets"}</h1>
        <p class="profile-hero__bio">{_e(intro)}</p>
        <div class="widget-theme" role="group" aria-label="Widget colors">
          <button type="button" class="widget-theme__btn is-active" data-widget-theme="dark" aria-pressed="true">Dark</button>
          <button type="button" class="widget-theme__btn" data-widget-theme="light" aria-pressed="false">Light</button>
        </div>
        {owner}
      </div>
    </section>
    <div class="site-wrap title-body">
      {cards}
      {discord}
      {cta}
      <p class="title-sources">Widgets follow the member's profile settings. Switching the profile off takes every widget down.</p>
    </div>
  </main>
  <!--SITE_FOOTER-->
</body>
</html>"""
    return apply_site_chrome(page)


def _page_response(request: Request, db: Session, user: Optional[models.User]):
    profile = public_profiles.visible_profile(db, user)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    canonical = public_profiles.profile_path(user) + "/widgets"
    if request.url.path.rstrip("/") != canonical:
        return RedirectResponse(canonical, status_code=301)
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    is_owner = signed_in and _viewer_id(request, db) == user.id
    response = strict_html_response(render_page(db, user, profile, signed_in=signed_in, is_owner=is_owner))
    response.headers["Cache-Control"] = "private, no-store" if signed_in else "public, max-age=300"
    response.headers["Vary"] = "Cookie"
    response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


@router.get("/u/id/{user_id:database_id}/widgets", include_in_schema=False)
def widgets_page_by_id(user_id: PositiveDatabaseId, request: Request, db: Session = Depends(get_db)):
    return _page_response(request, db, public_profiles.find_user_by_id(db, user_id))


@router.get("/u/{handle}/widgets", include_in_schema=False)
def widgets_page(handle: str, request: Request, db: Session = Depends(get_db)):
    return _page_response(request, db, public_profiles.find_user(db, handle))
