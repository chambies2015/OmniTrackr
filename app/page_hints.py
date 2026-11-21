"""Early connections to the image hosts a page shows first.

Posters on title pages, profiles and the best-of lists come from other sites
(Amazon, Wikimedia, Apple, AniList). The browser only opens a connection to such
a host once it reaches the <img> tag, and on a phone the DNS lookup, TCP and TLS
handshakes cost a few hundred milliseconds before the first poster can start
downloading. A preconnect hint in <head> starts that work while the stylesheets
load.

Only images that load straight away count (lazy ones are below the fold), and
at most two hosts get a hint: each open connection costs the phone something,
and an unused one is wasted.
"""
from __future__ import annotations

import re

MAX_HOSTS = 2
EAGER_IMAGES_CHECKED = 8

_IMG = re.compile(r"<img\b[^>]*>", re.I)
_SRC = re.compile(r'\ssrc="(https://([a-z0-9.-]+\.[a-z]{2,}))/[^"]*"', re.I)
_OWN_HOSTS = ("omnitrackr.xyz", "www.omnitrackr.xyz")


def eager_image_origins(html: str) -> list[str]:
    body_start = html.find("<body")
    origins: list[str] = []
    checked = 0
    for tag in _IMG.finditer(html, body_start if body_start != -1 else 0):
        checked += 1
        if checked > EAGER_IMAGES_CHECKED:
            break
        text = tag.group(0)
        if 'loading="lazy"' in text:
            continue
        src = _SRC.search(text)
        if not src:
            continue
        origin, host = src.group(1).lower(), src.group(2).lower()
        if host in _OWN_HOSTS or origin in origins:
            continue
        origins.append(origin)
        if len(origins) >= MAX_HOSTS:
            break
    return origins


def add_preconnects(html: str) -> str:
    """Add <link rel="preconnect"> for the hosts of the first eager images."""
    head_end = html.find("</head>")
    if head_end == -1 or "<img" not in html:
        return html
    head = html[:head_end]
    origins = [o for o in eager_image_origins(html)
               if f'rel="preconnect" href="{o}"' not in head and f'rel="dns-prefetch" href="{o}"' not in head]
    if not origins:
        return html
    hints = "".join(f'<link rel="preconnect" href="{origin}">' for origin in origins)
    # Before the first stylesheet, so the handshake runs while CSS downloads.
    stylesheet = re.search(r'<link\b[^>]*rel="stylesheet"', head)
    at = stylesheet.start() if stylesheet else head_end
    return html[:at] + hints + "\n  " + html[at:]


_PLAIN_INDEX = re.compile(r'<meta name="robots" content="index, follow"\s*/?>', re.I)


def allow_large_image_previews(html: str) -> str:
    """Let Google show a large image preview for indexed pages that don't say so yet.

    Most public pages send "index, follow, max-image-preview:large". A few (public
    lists, title indexes, profiles, the policy pages) send plain "index, follow",
    which limits Search and Discover to a small thumbnail. Noindex pages are untouched.
    """
    head_end = html.find("</head>")
    if head_end == -1:
        return html
    head = html[:head_end]
    match = _PLAIN_INDEX.search(head)
    if not match:
        return html
    return html[:match.start()] + '<meta name="robots" content="index, follow, max-image-preview:large">' + html[match.end():]


THEME_COLOR = "#0b0a18"  # --site-bg in site.css
_SITE_BODY = re.compile(r'<body\b[^>]*\bclass="(?:[^"]*\s)?site(?:\s[^"]*)?"', re.I)
_VIEWPORT = re.compile(r'<meta name="viewport"[^>]*>', re.I)


def add_theme_color(html: str) -> str:
    """Tint the phone browser's address bar to match the dark site.

    Only the homepage sent theme-color, so Chrome on Android drew a white bar
    over every guide. Pages that already send one, and pages without the dark
    site chrome (body class "site"), are left alone.
    """
    head_end = html.find("</head>")
    if head_end == -1 or 'name="theme-color"' in html[:head_end] or not _SITE_BODY.search(html, head_end):
        return html
    tag = f'<meta name="theme-color" content="{THEME_COLOR}">'
    viewport = _VIEWPORT.search(html, 0, head_end)
    at = viewport.end() if viewport else head_end
    return html[:at] + tag + html[at:]
