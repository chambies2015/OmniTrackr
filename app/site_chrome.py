"""Shared header and footer for every public (signed-out) page.

Templates opt in with two markers:

    <!--SITE_NAV:guides-->   the key of the nav item to mark as current (or empty)
    <!--SITE_FOOTER-->

Keeping the markup in one place means a new public page, a renamed section,
or a new footer link is a one-line change instead of an edit to every template.
Styles live in /static/site.css.
"""
from __future__ import annotations

import re
from html import escape

SITE_CSS_VERSION = "20260928-site-1"
SITE_JS_VERSION = "20260928-site-1"

# (key, label, href) in display order. The first NAV_PRIMARY entries stay
# visible on tablets; everything is always available in the compact menu.
NAV_ITEMS = (
    ("release-radar", "Release Radar", "/release-radar"),
    ("discover", "Discover", "/discover"),
    ("reviews", "Public reviews", "/reviews"),
    ("collections", "Collections", "/collections/explore"),
    ("guides", "Guides", "/guides"),
    ("faq", "FAQ", "/faq"),
)
NAV_PRIMARY = 2

FOOTER_GROUPS = (
    ("Explore", (
        ("Release Radar", "/release-radar"),
        ("Discover", "/discover"),
        ("Public reviews", "/reviews"),
        ("Collections", "/collections/explore"),
        ("Interactive demo", "/demo"),
        ("Sample library", "/sample-library"),
    )),
    ("Learn", (
        ("Guides", "/guides"),
        ("Tracking hub", "/media-tracking"),
        ("Import & backups", "/export-import-guide"),
        ("Review guide", "/review-guidelines"),
        ("Compare trackers", "/compare"),
        ("Ways to use OmniTrackr", "/use-cases"),
        ("FAQ", "/faq"),
    )),
    ("OmniTrackr", (
        ("About", "/about"),
        ("What's new", "/changelog"),
        ("Contact", "/contact"),
        ("Content quality", "/content-quality"),
        ("Ads & affiliates", "/advertising"),
        ("Privacy", "/privacy"),
        ("Terms", "/terms"),
        ("Site map", "/site-map"),
    )),
)

NAV_MARKER = re.compile(r"<!--SITE_NAV:([a-z-]*)-->")
FOOTER_MARKER = "<!--SITE_FOOTER-->"


def _brand() -> str:
    return '<a class="site-brand" href="/"><img src="/vortex-still.webp" alt="" width="28" height="28">OmniTrackr</a>'


def site_nav(active: str = "", *, login_action: bool = False) -> str:
    """The sticky site header. `login_action` wires "Log in" to the homepage form script."""
    links = []
    for index, (key, label, href) in enumerate(NAV_ITEMS):
        current = ' aria-current="page"' if key == active else ""
        tier = "site-nav__link--primary" if index < NAV_PRIMARY else "site-nav__link--secondary"
        links.append(f'<a class="site-nav__link {tier}" href="{href}"{current}>{escape(label)}</a>')
    current_attr = ' aria-current="page"'
    menu_links = "".join(
        f'<a href="{href}"{current_attr if key == active else ""}>{escape(label)}</a>'
        for key, label, href in NAV_ITEMS
    )
    login_attr = ' data-action="show-login-form"' if login_action else ""
    return (
        '<header class="site-header">'
        '<nav class="public-site-nav site-nav" aria-label="Public site navigation">'
        f'{_brand()}'
        '<div class="public-site-nav__links site-nav__links">'
        f'{"".join(links)}'
        f'<a class="site-nav__login" href="/#landing-auth"{login_attr}>Log in</a>'
        '<a class="public-site-nav__cta site-btn site-btn--primary site-btn--sm" href="/#landing-auth">Start tracking</a>'
        '<details class="site-menu"><summary aria-label="More pages"><span></span><span></span><span></span></summary>'
        f'<div class="site-menu__panel">{menu_links}'
        f'<a class="site-menu__login" href="/#landing-auth"{login_attr}>Log in</a></div></details>'
        '</div></nav></header>'
    )


def site_footer() -> str:
    columns = "".join(
        f'<nav class="site-footer__col" aria-label="{escape(title)}"><h2>{escape(title)}</h2>'
        + "".join(f'<a href="{href}">{escape(label)}</a>' for label, href in links)
        + "</nav>"
        for title, links in FOOTER_GROUPS
    )
    return (
        '<footer class="site-footer"><div class="site-wrap site-footer__grid">'
        f'<div class="site-footer__brand">{_brand()}'
        '<p>A free, independent media tracker for everything you watch, play, read, and hear.</p>'
        '<a class="site-footer__cta" href="/#landing-auth">Start your library <span aria-hidden="true">→</span></a>'
        '<a class="site-footer__kofi" href="https://ko-fi.com/omnitrackr" target="_blank" rel="noopener noreferrer">Support on Ko-fi ↗</a>'
        f'</div>{columns}</div></footer>'
    )


def site_assets() -> str:
    return (f'<link rel="stylesheet" href="/static/site.css?v={SITE_CSS_VERSION}">'
            f'<script src="/static/site.js?v={SITE_JS_VERSION}" defer></script>')


def apply_site_chrome(html: str, *, login_action: bool = False) -> str:
    """Replace the nav/footer markers; leaves pages without markers untouched."""
    if "<!--SITE_" not in html:
        return html
    html = NAV_MARKER.sub(lambda m: site_nav(m.group(1), login_action=login_action), html, count=1)
    html = html.replace(FOOTER_MARKER, site_footer(), 1)
    if "/static/site.css" not in html and "</head>" in html:
        html = html.replace("</head>", site_assets() + "\n</head>", 1)
    return html


def message_page(title: str, heading: str, message: str, *, eyebrow: str = "",
                 actions: tuple[tuple[str, str], ...] = (("Go to the homepage", "/"),)) -> str:
    """A small, fully styled page (not found, unavailable...) with the shared header and footer.

    Every argument is escaped; `actions` are (label, href) pairs rendered as buttons.
    """
    buttons = "".join(
        f'<a class="site-btn {"site-btn--primary" if index == 0 else "site-btn--ghost"}" href="{escape(href, quote=True)}">{escape(label)}</a>'
        for index, (label, href) in enumerate(actions)
    )
    kicker = f'<p class="site-eyebrow">{escape(eyebrow)}</p>' if eyebrow else ""
    page = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '  <meta charset="UTF-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '  <meta name="robots" content="noindex, follow">\n'
        f'  <title>{escape(title)} - OmniTrackr</title>\n'
        '  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">\n'
        '  <link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">\n'
        '</head>\n<body class="site site-message-page">\n  <!--SITE_NAV:-->\n'
        '  <main class="site-message site-wrap">\n'
        '    <div class="site-message__orb" aria-hidden="true"><img src="/vortex-still.webp" alt="" width="160" height="160"></div>\n'
        f'    {kicker}<h1>{escape(heading)}</h1>\n    <p>{escape(message)}</p>\n'
        f'    <div class="site-message__actions">{buttons}</div>\n'
        '  </main>\n  <!--SITE_FOOTER-->\n</body>\n</html>'
    )
    return apply_site_chrome(page)
