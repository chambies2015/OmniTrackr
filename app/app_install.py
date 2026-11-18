"""The installed app: how members find, install and keep opening OmniTrackr from a home screen (Nov 2026).

OmniTrackr has been installable since October 2026 (manifest, service worker, offline page, the
Android share target and the home-screen install card), but every step only went to Google
Analytics, so Site stats couldn't say whether anyone keeps the app on their phone. This module adds:

* Anonymous daily counters in ``site_traffic_daily`` under kind "app": an install offer shown and
  where, Install pressed and where, the browser's own install dialog accepted or closed, the Add to
  Home Screen steps opened (by browser), "Not now", the app installed, and shares received from
  other apps. They name no member.
* One row per member in ``installed_app_opens`` the first time they open OmniTrackr from its icon,
  touched at most once a day after that, so Site stats can count the members who actually use it.

Nothing here changes a member's library or settings.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models

KIND = "app"

# Where an install offer can be shown or pressed.
PLACES = {
    "card": "Home screen card",
    "sheet": "Phone note on a return visit",
    "menu": "Install app in the menu",
    "bell": "Notifications on iPhone (needs the app)",
    "page": "The Get the app page",
}
# Which Add to Home Screen steps were opened, by browser.
STEPS = {
    "ios_safari": "iPhone or iPad, Safari",
    "ios_other": "iPhone or iPad, Chrome, Edge or Firefox",
    "in_app": "Inside another app's browser",
    "android_other": "Android browser without an install button",
    "desktop_other": "Computer browser without an install button",
}
PLATFORMS = ("ios", "android", "desktop")
OUTCOMES = {
    "prompt_accepted": "Browser install dialog: Install chosen",
    "prompt_dismissed": "Browser install dialog: closed",
    "installed": "Installed (Android and computers report this)",
    "opened": "Days the installed app was opened (one per device per day)",
    "shared_in": "Links shared in from other apps (Android)",
    "offline_seen": "Offline page shown, then back online",
}

CLIENT_EVENTS = frozenset(
    {f"offer_{key}" for key in PLACES}
    | {f"install_{key}" for key in PLACES}
    | {f"later_{key}" for key in PLACES}
    | {f"steps_{key}" for key in STEPS}
    | {"prompt_accepted", "prompt_dismissed", "installed", "opened", "offline_seen"}
)
_BOT = re.compile(r"bot|crawl|spider|slurp|headless|lighthouse|preview|facebookexternalhit|python|curl|wget", re.I)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def count(key: str, request=None) -> bool:
    """Add 1 to an "app" counter for today. Never raises."""
    try:
        from .site_traffic import RECORDER
        if not RECORDER.enabled or not re.fullmatch(r"[a-z_]{1,40}", key or ""):
            return False
        if request is not None and _BOT.search(request.headers.get("user-agent", "") or "x"):
            return False
        day = datetime.now(timezone.utc).date()
        with RECORDER._lock:
            RECORDER._pending[(day, KIND, key)] += 1
            RECORDER._events += 1
        return True
    except Exception:
        return False


def platform_for(value: Optional[str]) -> Optional[str]:
    value = (value or "").strip().lower()
    return value if value in PLATFORMS else None


def record_open(db: Session, user: models.User, platform: Optional[str], today: Optional[date] = None) -> bool:
    """Note that a member opened the installed app today. Returns True the first time on a given day."""
    today = today or datetime.now(timezone.utc).date()
    row = db.query(models.InstalledAppOpen).filter(models.InstalledAppOpen.user_id == user.id).first()
    if row is not None and row.last_opened_on == today:
        return False
    if row is None:
        row = models.InstalledAppOpen(user_id=user.id, first_opened_at=_now(), open_days=0)
        db.add(row)
    row.last_opened_on = today
    row.open_days = (row.open_days or 0) + 1
    known = [part for part in (row.platforms or "").split(",") if part in PLATFORMS]
    platform = platform_for(platform)
    if platform and platform not in known:
        row.platforms = ",".join(sorted(known + [platform]))
    db.commit()
    return True


def platforms_for(db: Session, user: models.User) -> list[str]:
    """The kinds of device a member opened the installed app on."""
    row = db.query(models.InstalledAppOpen.platforms).filter(models.InstalledAppOpen.user_id == user.id).first()
    return [part for part in ((row[0] if row else "") or "").split(",") if part in PLATFORMS]


# ---------------------------------------------------------------- Site stats

def stats(db: Session, days: int, now: datetime) -> dict:
    table = models.SiteTrafficDaily
    since = (now - timedelta(days=days - 1)).date()
    counts = dict(db.query(table.key, func.sum(table.count)).filter(
        table.kind == KIND, table.day >= since,
    ).group_by(table.key).all())
    get = lambda key: int(counts.get(key) or 0)  # noqa: E731
    opens = models.InstalledAppOpen
    members = lambda *conditions: int(db.query(func.count(opens.id)).filter(*conditions).scalar() or 0)  # noqa: E731
    start = now - timedelta(days=days)
    return {
        "members": members(),
        "members_7d": members(opens.last_opened_on >= (now - timedelta(days=6)).date()),
        "members_range": members(opens.last_opened_on >= since),
        "new_members": members(opens.first_opened_at >= start),
        "by_platform": [{"platform": label, "count": members(opens.platforms.like(f"%{key}%"))}
                        for key, label in (("ios", "iPhone and iPad"), ("android", "Android"), ("desktop", "computers"))],
        "offers": [{"place": label, "shown": get(f"offer_{key}"), "pressed": get(f"install_{key}"),
                    "later": get(f"later_{key}")} for key, label in PLACES.items()],
        "steps": [{"browser": label, "count": get(f"steps_{key}")} for key, label in STEPS.items()],
        "outcomes": [{"label": label, "count": get(key)} for key, label in OUTCOMES.items()],
    }


# ---------------------------------------------------------------- Add to Home Screen steps

# Small outline icons that look like the buttons a member is told to press.
_SVG = ('<svg class="install-glyph" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>')
GLYPHS = {
    "share": _SVG.format('<path d="M12 3v12"/><path d="m8 7 4-4 4 4"/>'
                         '<path d="M7 10H6a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2h-1"/>'),
    "add": _SVG.format('<rect x="4" y="4" width="16" height="16" rx="4"/><path d="M12 8v8M8 12h8"/>'),
    "more": _SVG.format('<circle cx="5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/>'),
    "menu": _SVG.format('<circle cx="12" cy="5" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="12" cy="19" r="1.4"/>'),
    "install": _SVG.format('<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M12 7v6M9 10.5l3 3 3-3"/><path d="M8 21h8"/>'),
}

# (route, heading, steps). Each step is HTML with {glyph} names filled from GLYPHS; text is written here,
# never taken from a request.
STEP_GUIDES = (
    ("ios_safari", "Add OmniTrackr to your Home Screen", (
        "Tap <strong>Share</strong> {share} in Safari's toolbar. On iOS 26, tap <strong>More</strong> {more} first.",
        "Scroll down and tap <strong>Add to Home Screen</strong> {add}.",
        "Leave <strong>Open as Web App</strong> on and tap <strong>Add</strong>. OmniTrackr now opens full screen from its own icon.",
    )),
    ("ios_other", "Add OmniTrackr to your Home Screen", (
        "Tap <strong>Share</strong> {share}. In Chrome it's at the right of the address bar; in Edge and Firefox it's in the menu {more}.",
        "Tap <strong>Add to Home Screen</strong> {add}. If you don't see it, tap <strong>More</strong> first.",
        "Tap <strong>Add</strong>. OmniTrackr now opens from its own icon, without the browser around it.",
    )),
    ("in_app", "Open this page in your browser first", (
        "This page is open inside another app, and that app can't add it to your home screen.",
        "Tap the menu {more} or the compass button and choose <strong>Open in Safari</strong> or <strong>Open in browser</strong>.",
        "There, press <strong>Install app</strong> in the menu, or follow the Add to Home Screen steps.",
    )),
    ("android_other", "Add OmniTrackr to your home screen", (
        "Open your browser's menu {menu}.",
        "Choose <strong>Install</strong>, <strong>Add app to Home screen</strong> or <strong>Add to Home screen</strong> (the words differ by browser).",
        "Tap <strong>Add</strong>. OmniTrackr now opens from its own icon.",
    )),
    ("desktop_other", "Add OmniTrackr to your Dock", (
        "In Safari's menu bar, choose <strong>File</strong>, then <strong>Add to Dock</strong>.",
        "Click <strong>Add</strong>. OmniTrackr then opens in its own window from the Dock.",
    )),
)
STEPS_MARKER = "<!--INSTALL_STEPS-->"


def steps_markup(shown: str = "ios_safari") -> str:
    """Every browser's steps as hidden blocks; static/pwa.js reveals the one that fits the visitor."""
    blocks = []
    for route, heading, steps in STEP_GUIDES:
        items = "".join(f"<li><span>{step.format(**GLYPHS)}</span></li>" for step in steps)
        hidden = "" if route == shown else " hidden"
        copy = ('<button type="button" class="install-steps__copy" data-install-copy-link>Copy this page\'s link</button>'
                if route == "in_app" else "")
        blocks.append(f'<div class="install-steps" data-install-steps="{route}" data-install-title="{heading}"{hidden}>'
                      f'<ol>{items}</ol>{copy}</div>')
    return "".join(blocks)


def _guide(route: str) -> str:
    for key, _heading, steps in STEP_GUIDES:
        if key == route:
            return '<div class="install-steps"><ol>' + "".join(f"<li><span>{step.format(**GLYPHS)}</span></li>" for step in steps) + "</ol></div>"
    return ""


# ---------------------------------------------------------------- the /app page

PAGE_PATH = "/app"
PAGE_CSS_VERSION = "20261118-app-1"
PWA_JS_VERSION = "20261118-app-1"
_PERKS = (
    ("Opens from its own icon", "Full screen, without the address bar and tabs around it, and it picks up where you left off."),
    ("Share a link straight in", "On Android, OmniTrackr shows up when you tap Share in IMDb, Spotify, Goodreads, YouTube and "
                                 "about forty other apps, and the title is found for you."),
    ("Release-day alerts", "Turn them on from the bell and you'll hear when a new episode or a sequel is out. On iPhone, "
                           "notifications only work once OmniTrackr is on your Home Screen."),
    ("Shortcuts on the icon", "Press and hold the icon for Add a title, Release Radar, Pick for me and the daily game."),
    ("Starts faster", "The app keeps its own copy of OmniTrackr's styles and scripts, so it opens quicker than a fresh tab."),
    ("Nothing to download", "No app store and no updates to install. It takes a few megabytes and always runs the latest version."),
)
_FAQ = (
    ("Is it free?", "Yes. It's the same OmniTrackr, with the same free account. Nothing is sold through the app."),
    ("Is my library the same?", "Yes. Log in once inside the app and you'll see the same library, lists and friends as on the website."),
    ("Does it work offline?", "It opens without a connection and shows a short offline page, then loads your library as soon as "
                              "you're back online. Nothing you saved is lost."),
    ("How do I remove it?", "Press and hold the icon and choose Remove App (iPhone) or Uninstall (Android). On a computer, open "
                            "the app's menu and choose Uninstall. Your account and library stay as they are."),
)


def app_page_html() -> str:
    """The public "Get the app" page: what installing gives you, and the steps for each device."""
    from html import escape
    from .site_chrome import apply_site_chrome
    perks = "".join(f'<li><h3>{escape(title)}</h3><p>{escape(text)}</p></li>' for title, text in _PERKS)
    faq = "".join(f'<details><summary>{escape(q)}</summary><p>{escape(a)}</p></details>' for q, a in _FAQ)
    title = "Get the OmniTrackr app for iPhone, Android and computers"
    description = ("Add OmniTrackr to your home screen: it opens full screen from its own icon, takes shares from other apps "
                   "on Android, and shows release-day alerts. Steps for iPhone, Android and computers.")
    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="robots" content="index, follow, max-image-preview:large">
  <meta name="theme-color" content="#0b0a18">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(description, quote=True)}">
  <link rel="canonical" href="https://omnitrackr.xyz{PAGE_PATH}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://omnitrackr.xyz{PAGE_PATH}">
  <meta property="og:title" content="{escape(title, quote=True)}">
  <meta property="og:description" content="{escape(description, quote=True)}">
  <meta property="og:image" content="https://omnitrackr.xyz/omnitrackr_vortex.png">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="manifest" href="/manifest.webmanifest">
  <link rel="apple-touch-icon" href="/static/icons/apple-touch-icon.png?v=20261003-pwa-1">
  <meta name="apple-mobile-web-app-title" content="OmniTrackr">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">
  <link rel="stylesheet" href="/static/install-app.css?v={PAGE_CSS_VERSION}">
  <link rel="stylesheet" href="/static/app-page.css?v={PAGE_CSS_VERSION}">
  <script src="/static/pwa.js?v={PWA_JS_VERSION}" defer></script>
</head>
<body class="site app-page">
  <!--SITE_NAV:-->
  <main class="site-wrap app-page__main">
    <section class="app-page__hero" aria-labelledby="appPageTitle">
      <img class="app-page__icon" src="/static/icons/icon-192.png?v=20261003-pwa-1" alt="" width="88" height="88">
      <p class="site-eyebrow">Get the app</p>
      <h1 id="appPageTitle">OmniTrackr on your home screen</h1>
      <p class="app-page__lead">There's nothing to download from an app store. Add OmniTrackr from your browser and it opens
        like any other app: full screen, from its own icon, with your library one tap away.</p>
      <div class="app-page__actions">
        <button type="button" class="site-btn site-btn--primary" data-install-app="page" hidden>Install OmniTrackr</button>
        <a class="site-btn site-btn--ghost" href="#steps">Steps for your device</a>
      </div>
      <p class="app-page__installed" data-app-installed hidden>You're already using the app. Press and hold its icon for shortcuts.</p>
    </section>

    <section aria-labelledby="appPerks">
      <h2 id="appPerks">What you get</h2>
      <ul class="app-page__perks">{perks}</ul>
    </section>

    <section id="steps" class="app-page__steps" aria-labelledby="appSteps">
      <h2 id="appSteps">How to add it</h2>
      <div class="app-page__devices">
        <article aria-labelledby="appStepsIphone">
          <h3 id="appStepsIphone">iPhone and iPad (Safari)</h3>
          {_guide("ios_safari")}
          <p class="app-page__note">Using Chrome, Edge or Firefox on iPhone? They can add it too (iOS 16.4 and later):</p>
          {_guide("ios_other")}
        </article>
        <article aria-labelledby="appStepsAndroid">
          <h3 id="appStepsAndroid">Android</h3>
          <p class="app-page__note">In Chrome, Samsung Internet or Edge, press <strong>Install OmniTrackr</strong> above, or
            <strong>Install app</strong> in the menu of your OmniTrackr library. In other browsers:</p>
          {_guide("android_other")}
        </article>
        <article aria-labelledby="appStepsComputer">
          <h3 id="appStepsComputer">Computers</h3>
          <p class="app-page__note">In Chrome or Edge, click the install icon {GLYPHS["install"]} at the right of the address bar,
            or press <strong>Install OmniTrackr</strong> above. On a Mac with Safari 17 or later:</p>
          {_guide("desktop_other")}
        </article>
      </div>
      <p class="app-page__note">Opened this page from Instagram, Facebook or TikTok? Their built-in browsers can't add apps.
        Open the page in Safari or Chrome first.</p>
    </section>

    <section aria-labelledby="appFaq" class="app-page__faq">
      <h2 id="appFaq">Questions</h2>
      {faq}
    </section>

    <p class="app-page__cta"><a class="site-btn site-btn--primary" href="/#signup">Start your free library</a>
      <a class="site-btn site-btn--ghost" href="/">Open OmniTrackr</a></p>
  </main>

  <dialog id="installAppDialog" class="install-app-dialog" aria-labelledby="installAppDialogTitle">
    <div class="install-app-dialog__head">
      <img src="/static/icons/icon-192.png?v=20261003-pwa-1" alt="" width="44" height="44" loading="lazy" decoding="async">
      <h2 id="installAppDialogTitle">Add OmniTrackr to your Home Screen</h2>
    </div>
    {steps_markup()}
    <div class="install-app-dialog__actions">
      <button id="installAppDialogClose" class="site-btn site-btn--primary" type="button" autofocus>Got it</button>
    </div>
  </dialog>
  <!--SITE_FOOTER-->
</body>
</html>'''
    return apply_site_chrome(page)
