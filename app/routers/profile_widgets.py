"""Embeddable profile widgets: /u/<username>/widget/<kind>.png|.svg, the /u/<username>/widgets embed page,
and the small Settings and counter endpoints behind them."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models, profile_widgets, public_profiles
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..integer_bounds import PositiveDatabaseId
from ..site_chrome import apply_site_chrome
from .profiles import TITLE_CSS_VERSION, _e, _viewer_id

router = APIRouter(tags=["profiles"])
CSS_VERSION = "20261120-badges-3"
FORMATS = (
    ("html", "HTML", "Blogs, personal sites and GitHub READMEs"),
    ("markdown", "Markdown", "GitHub, Obsidian and most wikis"),
    ("bbcode", "BBCode", "Forums, forum signatures and your MyAnimeList profile"),
    ("anilist", "AniList", "Your AniList bio"),
    ("image", "Image link", "Discord, chats, or anywhere that shows an image from a link"),
)
# The order cards appear on the page: the two that suit most places first.
PAGE_ORDER = ("signature", "now", "recent", "stats", "favorites", "badge")
MEDIA_TYPES = {"png": "image/png", "svg": "image/svg+xml"}
# An SVG opened on its own is a document: nothing in it may run or load.
SVG_POLICY = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"


def _headers(etag: str, fmt: str) -> dict:
    # Forums and chat apps fetch the image through their own proxies, so a short public cache keeps it fresh.
    headers = {"Cache-Control": "public, max-age=900", "ETag": f'"{etag}"', "X-Content-Type-Options": "nosniff",
               "X-Robots-Tag": "noindex", "Cross-Origin-Resource-Policy": "cross-origin"}
    if fmt == "svg":
        headers["Content-Security-Policy"] = SVG_POLICY
    return headers


def _matches(request: Request, etag: str) -> bool:
    wanted = request.headers.get("if-none-match") or ""
    return any(tag.strip().removeprefix("W/") in (f'"{etag}"', "*") for tag in wanted.split(",") if tag.strip())


def _widget_response(request: Request, db: Session, user: Optional[models.User], kind: str, theme: str, scale: str,
                     fmt: str):
    profile = public_profiles.visible_profile(db, user)
    if profile is None or kind not in profile_widgets.KINDS:
        raise HTTPException(status_code=404, detail="Widget not found")
    scale_value = 2 if scale == "2" else 1
    try:
        found = profile_widgets.image(db, user, profile, kind, theme, scale_value, fmt)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=404, detail="Widget unavailable")
    if found is None:
        raise HTTPException(status_code=404, detail="Widget not found")
    body, etag = found
    profile_widgets.record_load(db, user, kind, request)
    headers = _headers(etag, fmt)
    if _matches(request, etag):
        profile_widgets.count("not_modified")
        return Response(status_code=304, headers=headers)
    profile_widgets.count(f"served_{fmt}")
    return Response(content=body, media_type=MEDIA_TYPES[fmt], headers=headers)


@router.get("/u/id/{user_id:database_id}/widget/{kind}.png", include_in_schema=False)
def widget_by_id(user_id: PositiveDatabaseId, kind: str, request: Request, theme: str = "dark", scale: str = "1",
                 db: Session = Depends(get_db)):
    return _widget_response(request, db, public_profiles.find_user_by_id(db, user_id), kind, theme, scale, "png")


@router.get("/u/{handle}/widget/{kind}.png", include_in_schema=False)
def widget(handle: str, kind: str, request: Request, theme: str = "dark", scale: str = "1",
           db: Session = Depends(get_db)):
    return _widget_response(request, db, public_profiles.find_user(db, handle), kind, theme, scale, "png")


@router.get("/u/id/{user_id:database_id}/widget/{kind}.svg", include_in_schema=False)
def widget_svg_by_id(user_id: PositiveDatabaseId, kind: str, request: Request, theme: str = "dark",
                     db: Session = Depends(get_db)):
    return _widget_response(request, db, public_profiles.find_user_by_id(db, user_id), kind, theme, "1", "svg")


@router.get("/u/{handle}/widget/{kind}.svg", include_in_schema=False)
def widget_svg(handle: str, kind: str, request: Request, theme: str = "dark", db: Session = Depends(get_db)):
    return _widget_response(request, db, public_profiles.find_user(db, handle), kind, theme, "1", "svg")


# ---------------------------------------------------------------- small endpoints

class WidgetEvent(BaseModel):
    key: str = Field(..., max_length=40)


@router.post("/api/widgets/event", status_code=204, include_in_schema=False)
def widget_event(payload: WidgetEvent, request: Request):
    """A copy button or option press on the widget page or in Settings. Counted without saying who."""
    if payload.key in profile_widgets.CLIENT_COUNTERS:
        profile_widgets.count(payload.key)
    return Response(status_code=204)


@router.get("/api/profile/widgets")
def my_widgets(request: Request, response: Response, user: models.User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """What the Settings panel shows: a preview, the forum code and how often the widgets were loaded."""
    response.headers["Cache-Control"] = "private, no-store"
    profile = public_profiles.visible_profile(db, user)
    if profile is None:
        return {"enabled": False}
    profile_widgets.count("settings_shown")
    summary = profile_widgets.owner_summary(db, user.id)
    site = profile_widgets.SITE_URL
    codes = profile_widgets.snippets(user, "signature")
    return {
        "enabled": True,
        "page": public_profiles.profile_path(user) + "/widgets",
        "preview": profile_widgets.image_url(user, "signature", "dark", 2).removeprefix(site),
        "preview_light": profile_widgets.image_url(user, "signature", "light", 2).removeprefix(site),
        "width": profile_widgets.WIDTHS["signature"],
        "height": profile_widgets.HEIGHTS["signature"],
        "forum_code": codes["bbcode"],
        "loads": summary["loads"],
        "sites": summary["sites"],
        "summary": profile_widgets.summary_sentence(summary),
    }


# ---------------------------------------------------------------- embed page

def _format_html(kind: str, codes: dict) -> str:
    rows = ""
    for key, label, hint in FORMATS:
        field_id = f"widget-{kind}-{key}"
        rows += (f'<div class="widget-code"><label for="{field_id}"><strong>{_e(label)}</strong> '
                 f'<small>{_e(hint)}</small></label>'
                 f'<div class="widget-code__row"><textarea id="{field_id}" readonly rows="{3 if key == "html" else 2}" '
                 f'spellcheck="false" data-widget-field="{key}">{_e(codes[key])}</textarea>'
                 f'<button type="button" class="site-btn site-btn--ghost site-btn--sm" data-widget-copy="{field_id}" '
                 f'data-widget-count="copy_{key}">Copy</button>'
                 f'</div></div>')
    return rows


def _widget_card(user: models.User, kind: str, variants: dict, first: bool) -> str:
    title, blurb = profile_widgets.LABELS[kind]
    width = profile_widgets.WIDTHS.get(kind)
    height = profile_widgets.HEIGHTS[kind]
    size = f' width="{width}" height="{height}"' if width else f' height="{height}"'
    # One preview per colors and file pairing; the page script only shows and hides them. Lazy images
    # that stay hidden are never fetched. Relative addresses, so they load from whichever host serves the page.
    previews = ""
    for key, codes in variants.items():
        shown = key == "dark-png"
        lazy = "" if first and shown else ' loading="lazy"'
        previews += (f'<img src="{_e(codes["preview"])}" data-widget-variant="{_e(key)}" '
                     f'alt="{_e(title)} widget preview"{size}{lazy}{"" if shown else " hidden"}>')
    return (f'<section class="title-section widget-card widget-card--{kind}" data-widget-kind="{kind}" '
            f'aria-labelledby="widget-{kind}">'
            f'<h2 id="widget-{kind}">{_e(title)}</h2><p class="widget-card__blurb">{_e(blurb)}</p>'
            f'<div class="widget-preview widget-preview--{kind}">{previews}</div>'
            f'<details class="widget-codes"{" open" if first else ""}><summary>Get the code</summary>'
            f'{_format_html(kind, variants["dark-png"])}</details>'
            f'</section>')


def _missing_note(kinds: list[str]) -> str:
    missing = [kind for kind in profile_widgets.KINDS if kind not in kinds]
    if not missing:
        return ""
    reasons = {
        "stats": "Library stats appear when your profile shows library counts and your statistics aren't private.",
        "recent": "Recently finished appears when you switch on the diary.",
        "favorites": "Favorites appears when your profile shows favorites or you pin titles to your showcase.",
        "now": "Right now appears when you switch on Right now. It shows what you started from Up next, never how far along you are.",
    }
    items = "".join(f"<li>{_e(reasons[kind])}</li>" for kind in missing if kind in reasons)
    return (f'<div class="profile-owner-note widget-missing"><p>Only you see this. More widgets unlock from '
            f'<a href="/#public-profile">Account → Public profile</a>:</p><ul>{items}</ul></div>')


def _controls() -> str:
    def button(group: str, value: str, label: str, active: bool) -> str:
        return (f'<button type="button" class="widget-theme__btn{" is-active" if active else ""}" '
                f'data-widget-{group}="{value}" aria-pressed="{"true" if active else "false"}">{_e(label)}</button>')
    colors = "".join(button("theme", value, label, value == "dark")
                     for value, label in (("dark", "Dark"), ("light", "Light"), ("auto", "Auto")))
    files = "".join(button("format", value, label, value == "png") for value, label in (("png", "PNG"), ("svg", "SVG")))
    return ('<div class="widget-controls" id="widgetControls">'
            f'<div class="widget-controls__group"><span class="widget-controls__label" id="widgetColorsLabel">Colors</span>'
            f'<div class="widget-theme" role="group" aria-labelledby="widgetColorsLabel">{colors}</div></div>'
            f'<div class="widget-controls__group"><span class="widget-controls__label" id="widgetFileLabel">File</span>'
            f'<div class="widget-theme" role="group" aria-labelledby="widgetFileLabel">{files}</div></div>'
            '<p class="widget-controls__hint" id="widgetHint" aria-live="polite">PNG works on every forum and chat app. '
            'SVG stays sharp at any size and suits GitHub and websites.</p></div>')


def render_page(db: Session, user: models.User, profile: models.PublicProfile, *, signed_in: bool, is_owner: bool) -> str:
    name = user.username
    path = public_profiles.profile_path(user)
    kinds = profile_widgets.available(db, user, profile)
    ordered = [kind for kind in PAGE_ORDER if kind in kinds]
    codes = {kind: profile_widgets.variants(user, kind) for kind in ordered}
    cards = "".join(_widget_card(user, kind, codes[kind], index == 0) for index, kind in enumerate(ordered))
    intro = (f"Put your OmniTrackr profile in your forum signature, blog, GitHub README or AniList bio. "
             f"Widgets update by themselves as you track, and only show what your public profile already shows."
             if is_owner else
             f"Images of {name}'s public profile that update as they track. Each one links back to their profile.")
    discord = ('<section class="title-section widget-card"><h2>Discord, X, Bluesky and group chats</h2>'
               '<p class="widget-card__blurb">Paste your profile link. It unfolds into a big preview card by itself.</p>'
               f'<div class="widget-code__row"><input type="text" readonly id="widget-profile-link" '
               f'value="{_e(profile_widgets.link_url(user))}" aria-label="Profile link">'
               '<button type="button" class="site-btn site-btn--ghost site-btn--sm" data-widget-copy="widget-profile-link" '
               'data-widget-count="copy_link">Copy</button>'
               '</div></section>')
    cta = ("" if signed_in else
           '<section class="profile-cta site-card"><div><h2>Make widgets of your own</h2>'
           '<p>OmniTrackr is free. Track movies, shows, anime, games, music and books, then show them off anywhere.</p></div>'
           '<a class="site-btn site-btn--primary" href="/#signup">Start tracking free</a></section>')
    owner = ""
    if is_owner:
        summary = profile_widgets.owner_summary(db, user.id)
        owner = (f'<p class="widget-loads" id="widgetLoads">{_e(profile_widgets.summary_sentence(summary))}</p>'
                 + _missing_note(kinds))
    # Every theme and file pairing's embed code, for the Colors and File buttons. Text only: the page
    # script copies it into the code boxes. The previews are already on the page as images.
    codes = {kind: {key: {field: value for field, value in found.items() if field != "preview"}
                    for key, found in pairs.items()} for kind, pairs in codes.items()}
    data = json.dumps(codes, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
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
  <link rel="stylesheet" href="/static/fonts.css?v=20261122-cwv-1">
  <link rel="stylesheet" href="/static/title-page.css?v={TITLE_CSS_VERSION}">
  <link rel="stylesheet" href="/static/profile-page.css?v=20261030-audiobooks-1">
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
        {owner}
      </div>
    </section>
    <div class="site-wrap title-body">
      {_controls()}
      {cards}
      {discord}
      {cta}
      <p class="title-sources">Widgets follow the member's profile settings. Switching the profile off takes every widget down.
        OmniTrackr counts how often each member's widgets load and on which sites (the site's name only, never the page or the reader).</p>
    </div>
  </main>
  <script type="application/json" id="widgetCodes">{data}</script>
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
    profile_widgets.count("page_owner" if is_owner else "page_guest")
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
