"""/continue: finish signing up in a real browser (Nov 26 2026).

Two pages at one address, picked by the browser asking:

- Inside Instagram, Facebook, TikTok and other apps' built-in browsers (app_browsers.py),
  where Google refuses to sign anyone in. /auth/google/start sends those visitors here.
  The page says why, opens the same page in Chrome on Android, and on iPhone shows the
  "Open in browser" menu steps. static/continue.js rewrites the address to a link that
  carries the visitor's saved titles, so the app's menu (or Copy link) takes them along.
  Email sign-up works inside the app, so it is offered right there too.
- In Safari, Chrome and every other browser: the titles that came with the link are
  added to this browser's guest list, and the page offers Continue with Google, email,
  or log in. The saved titles move into the new library as they do from any page.

The carried titles travel in the link itself (after the #, which browsers don't send to
the server, or in the query string for Chrome on Android, which the server ignores).
Nothing is stored about the visitor.
"""
from __future__ import annotations

import re
from html import escape
from typing import Optional
from urllib.parse import urlencode

from . import app_browsers, google_signin

PAGE_PATH = "/continue"
CSS_VERSION = "20261126-continue-1"
JS_VERSION = "20261126-continue-1"
GUEST_LIST_JS = "/static/guest-list.js?v=20261122-shelf-1"
# The page the visitor pressed the button on (from the Referer), so the new library can link back.
_FROM_PATH = re.compile(r"/[A-Za-z0-9/_.-]{0,200}")
_SKIP_FROM = ("/auth", "/continue", "/api", "/static")

GOOGLE_G = (
    '<svg class="continue-google__g" viewBox="0 0 18 18" width="18" height="18" aria-hidden="true" focusable="false">'
    '<path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z"/>'
    '<path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z"/>'
    '<path fill="#FBBC05" d="M3.97 10.72A5.4 5.4 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.95H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.05l3.01-2.33z"/>'
    '<path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z"/>'
    '</svg>'
)


def from_path(value: Optional[str]) -> Optional[str]:
    """A path on this site worth linking back to, or None."""
    if not isinstance(value, str) or not _FROM_PATH.fullmatch(value) or value.startswith("//"):
        return None
    if value == "/" or value.startswith(_SKIP_FROM):
        return None
    return value


def referer_path(referer: Optional[str], host: Optional[str]) -> Optional[str]:
    """The path of a same-site Referer header."""
    from urllib.parse import urlsplit
    if not referer or len(referer) > 600:
        return None
    try:
        parts = urlsplit(referer)
    except ValueError:
        return None
    hosts = {"omnitrackr.xyz", "www.omnitrackr.xyz"}
    if host:
        hosts.add(host.lower())
    if parts.scheme not in ("http", "https") or (parts.netloc or "").lower() not in hosts:
        return None
    return from_path(parts.path)


def url(invite: Optional[str] = None, came_from: Optional[str] = None) -> str:
    """Where /auth/google/start sends a visitor inside an app's browser."""
    query = {}
    if from_path(came_from):
        query["from"] = came_from
    if google_signin.valid_invite(invite):
        query["invite"] = invite
    return PAGE_PATH + (f"?{urlencode(query)}" if query else "")


def _google_href(invite: Optional[str]) -> str:
    return "/auth/google/start" + (f"?invite={invite}" if invite else "")


def _browser_for(platform: str) -> str:
    return {"ios": "Safari", "android": "Chrome"}.get(platform, "your browser")


def _app_label(name: str) -> str:
    return "this app's" if name == app_browsers.OTHER_APP else f"{name}'s"


def _text(value: str) -> str:
    """Escaped for page text: apostrophes stay apostrophes ("Instagram's")."""
    return escape(value, quote=False)


def _in_app_body(name: str, platform: str, invite: Optional[str]) -> str:
    browser = _browser_for(platform)
    app_label = _app_label(name)
    app_chip = "This app" if name == app_browsers.OTHER_APP else name
    if platform == "android":
        # continue.js swaps in a link that carries the saved titles; this one works without it.
        steps = (
            '<a class="site-btn site-btn--primary continue-main" href="intent://omnitrackr.xyz/continue?via=app'
            '#Intent;scheme=https;package=com.android.chrome;end" data-open-chrome>Open in Chrome</a>'
            '<p class="continue-hint">If nothing happens, tap <span class="continue-dots" aria-label="the menu">⋮</span> '
            'in the corner of the screen and choose <strong>Open in browser</strong> (some apps say Open in Chrome).</p>'
        )
    else:
        steps = (
            '<ol class="continue-steps">'
            '<li><span class="continue-steps__num" aria-hidden="true">1</span><span>Tap <span class="continue-dots" aria-label="the menu">•••</span> '
            'at the top or bottom of the screen.</span></li>'
            f'<li><span class="continue-steps__num" aria-hidden="true">2</span><span>Choose <strong>Open in browser</strong>. '
            f'Some apps call it Open in {_text(browser)} or Open in external browser.</span></li>'
            f'<li><span class="continue-steps__num" aria-hidden="true">3</span><span>Press <strong>Continue with Google</strong> '
            f'on the page that opens in {_text(browser)}.</span></li>'
            '</ol>'
        )
    anyway = _google_href(invite) + ("&" if invite else "?") + "here=1"
    return (
        '<div class="continue-hop" aria-hidden="true">'
        f'<span class="continue-hop__chip">{_text(app_chip)}</span><span class="continue-hop__line"></span>'
        f'<span class="continue-hop__chip continue-hop__chip--to">{_text(browser if browser != "your browser" else "Browser")}</span></div>'
        '<p class="site-eyebrow">One more step</p>'
        f'<h1 id="continueTitle">Finish in {_text(browser)}</h1>'
        f'<p class="continue-lead">Google doesn\'t allow sign-ins inside {_text(app_label)} built-in browser, so the Google '
        f'button can\'t work here. Open this page in {_text(browser)} and it\'s one tap from there.</p>'
        '<p class="continue-carry" data-carry-note hidden></p>'
        f'{steps}'
        '<div class="continue-copy">'
        '<button type="button" class="site-btn site-btn--ghost" data-copy-link>Copy link</button>'
        f'<p class="continue-copy__note">Then paste it into {_text(browser)}\'s address bar.</p>'
        '<input class="continue-copy__field" type="url" readonly aria-label="Link to this page" data-copy-field hidden>'
        '<p class="continue-status" data-copy-status role="status" aria-live="polite"></p></div>'
        '<div class="continue-or"><span>or stay here</span></div>'
        '<h2 class="continue-subhead">Sign up with your email</h2>'
        f'<p class="continue-text">Email works inside {_text(name if name != app_browsers.OTHER_APP else "this app")}. '
        'We send you a 6-digit code: check your mail, come back here and type it in.</p>'
        '<a class="site-btn site-btn--ghost continue-wide" href="/#signup" data-continue-email>Sign up with email</a>'
        '<p class="continue-small">Already have an account? <a href="/#login">Log in with your email and password</a>.<br>'
        f'Not inside an app? <a href="{escape(anyway, quote=True)}" rel="nofollow">Try Google here anyway</a></p>'
    )


def _browser_body(invite: Optional[str], via_app: bool, member: bool, google: bool) -> str:
    if member:
        return (
            '<p class="site-eyebrow">Signed in</p>'
            '<h1 id="continueTitle">You\'re already signed in</h1>'
            '<p class="continue-lead">Open your library and anything you saved before signing in moves into it.</p>'
            '<p class="continue-carry" data-carry-note hidden></p>'
            '<a class="site-btn site-btn--primary continue-wide" href="/">Open your library</a>'
        )
    heading = "Now finish with one tap" if via_app else "Make your free account"
    lead = ("You're out of the app. Make your free account here and you're in."
            if via_app else "Track every movie, show, game, book, album, anime, manga, podcast and audiobook in one library.")
    google_button = (
        f'<a class="continue-google continue-wide" href="{escape(_google_href(invite), quote=True)}" rel="nofollow" '
        f'data-continue-google>{GOOGLE_G}<span>Continue with Google</span></a>' if google else "")
    return (
        '<p class="site-eyebrow">Free account</p>'
        f'<h1 id="continueTitle">{escape(heading)}</h1>'
        f'<p class="continue-lead">{escape(lead)}</p>'
        '<div class="continue-list" data-continue-list hidden>'
        '<p class="continue-list__head" data-continue-list-head></p><ul data-continue-titles></ul>'
        '<p class="continue-list__more" data-continue-more hidden></p></div>'
        f'{google_button}'
        f'<a class="site-btn {"site-btn--ghost" if google else "site-btn--primary"} continue-wide" href="/#signup" data-continue-email>'
        'Sign up with email</a>'
        '<p class="continue-small">Free, private unless you share it, no card needed. Already a member? '
        '<a href="/#login" data-continue-login>Log in</a> and your list is added to your library.</p>'
        '<p class="continue-back" data-continue-back hidden></p>'
    )


def page_html(user_agent: str, *, invite: Optional[str] = None, came_from: Optional[str] = None,
              via_app: bool = False, member: bool = False) -> str:
    """The whole page for this browser."""
    from .site_chrome import apply_site_chrome
    invite = google_signin.valid_invite(invite)
    came_from = from_path(came_from)
    name = app_browsers.app_name(user_agent)
    google = google_signin.configured()
    in_app = bool(name) and google and not member
    if in_app:
        body = _in_app_body(name, app_browsers.platform(user_agent), invite)
        mode = "app"
        title = "Finish signing up in your browser"
    else:
        body = _browser_body(invite, via_app, member, google)
        mode = "member" if member else "browser"
        title = "Make your free account"
    # data-signup-sheet="off": the phone "Start tracking" sheet (site-nav.js) would get in the way of
    # this page's own Sign up with email link, which goes straight to the email form.
    data = f' data-continue="{mode}" data-platform="{escape(app_browsers.platform(user_agent))}" data-signup-sheet="off"'
    if invite:
        data += f' data-invite="{escape(invite, quote=True)}"'
    if came_from:
        data += f' data-from="{escape(came_from, quote=True)}"'
    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="robots" content="noindex, follow">
  <meta name="theme-color" content="#0b0a18">
  <title>{escape(title)} - OmniTrackr</title>
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261122-cwv-1">
  <link rel="stylesheet" href="/static/continue.css?v={CSS_VERSION}">
  <script src="{GUEST_LIST_JS}" defer></script>
  <script src="/static/continue.js?v={JS_VERSION}" defer></script>
</head>
<body class="site site-message-page continue-page"{data}>
  <!--SITE_NAV:-->
  <main class="site-wrap continue-wrap">
    <section class="continue-card" aria-labelledby="continueTitle">
      {body}
    </section>
  </main>
  <!--SITE_FOOTER-->
</body>
</html>'''
    return apply_site_chrome(page)
