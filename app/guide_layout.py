"""Reading layout for the written guides (if-you-liked, in order, best of, release
guides, holiday and gift guides, Discover guides and monthly editions).

Every guide router builds its page the same way: an ``<article class="trail-guide">``
that opens with a ``hero--guide`` header holding the title, a byline and a row of
"On this page" links. ``add_reading_layout`` is an html_finish step that turns that
shared shape into a magazine page without each router having to know about it:

* the guide stylesheet, the serif used for reading and a small script go into <head>,
* the byline gets a reading time worked out from the article's own text,
* everything after the header goes into a body column, with a rail beside it that
  repeats the page's contents links and says when the guide was last checked,
* the body ends with a short note on who writes the guides and how to chip in on Ko-fi
  (Nov 23 2026), the only support ask a reader who never signs up will see,
* the first three covers from the guide's own picks are fanned out beside the title
  on wide screens, and visitors get a small "keep a list" note in the rail when the
  page has save buttons (Nov 25 2026).

The header's own links stay where they are: they are the contents on phones, and
the stylesheet hides them on wide screens where the rail shows the same list.
A page without that shape is returned unchanged.
"""
from __future__ import annotations

import math
import re
from html import escape, unescape
from urllib.parse import urlsplit

CSS_VERSION = "20261125-look-1"
JS_VERSION = "20261125-look-1"
SERIF_FONT = "/static/fonts/source-serif-4-latin-var-normal.woff2"
MARKER = "data-guide-layout"
WORDS_PER_MINUTE = 230

_ARTICLE_OPEN = re.compile(r'<article class="trail-guide[^"]*"[^>]*>')
_ARTICLE_TAG = re.compile(r"<(/?)article\b[^>]*>", re.I)
_HEADER_TAG = re.compile(r"<(/?)header\b[^>]*>", re.I)
_JUMP = re.compile(r'<nav class="guide-jump"[^>]*>(.*?)</nav>', re.S)
_LINK = re.compile(r'<a href="(#[^"]+)"[^>]*>(.*?)</a>', re.S)
_BYLINE = re.compile(r'(<p class="guide-byline">)(.*?)(</p>)', re.S)
_TIME = re.compile(r'<time datetime="([^"]+)">(.*?)</time>', re.S)
_SKIP = re.compile(r"<(script|style|template|noscript)\b.*?</\1>", re.S | re.I)
_TAGS = re.compile(r"<[^>]+>")
_NONCE = re.compile(r'<script\b[^>]*\snonce="([A-Za-z0-9+/=_-]+)"')
_WORD = re.compile(r"[A-Za-z0-9À-ɏ'’]+")
_CANONICAL = re.compile(r'<link rel="canonical" href="(https://omnitrackr\.xyz[^"]*)"')
_BACK_LINK = re.compile(r'\s*<a href="[^"]*">\s*←[^<]*</a>')
# Covers on the picks themselves: the poster on an If you liked, Best of, release, seasonal or
# In order pick (never the art on cards that point at other guides), and the drawn covers
# Discover and the Essential 100 use (explore_art.cover).
_PICK_ART = re.compile(r'<img class="(?:yl-pick|sn-pick|io-entry)__art"[^>]*>|<span class="x-art[ "][^>]*>')
_SRC = re.compile(r'\ssrc="([^"]+)"')
_SPAN_TAG = re.compile(r"<(/?)span\b[^>]*>", re.I)
FAN_COVERS = 3


def _matching_close(html: str, start: int, pattern: re.Pattern) -> int:
    """Index just past the tag that closes the element opened at ``start`` (-1 if unbalanced)."""
    depth = 0
    for match in pattern.finditer(html, start):
        depth += -1 if match.group(1) else 1
        if depth == 0:
            return match.end()
    return -1


def reading_minutes(fragment: str) -> int:
    text = unescape(_TAGS.sub(" ", _SKIP.sub(" ", fragment)))
    return max(1, math.ceil(len(_WORD.findall(text)) / WORDS_PER_MINUTE))


def _contents(header: str) -> list[tuple[str, str]]:
    jump = _JUMP.search(header)
    if not jump:
        return []
    return [(href, _TAGS.sub("", label).strip()) for href, label in _LINK.findall(jump.group(1)) if _TAGS.sub("", label).strip()]


_DRAWN_LABELS = {"movie": "Movie", "tv": "TV", "anime": "Anime", "game": "Game", "album": "Album", "book": "Book",
                 "manga": "Manga", "podcast": "Podcast", "audiobook": "Audiobook"}


def drawn_cover(prefix: str, title: str, kind: str) -> str:
    """A stand-in poster for a pick whose art hasn't been found yet: the title set on the format's colour
    (guide-reader.css .guide-drawn), so a list of picks keeps one column of covers."""
    label = _DRAWN_LABELS.get(kind, "")
    # Long words get smaller type so "Soundtracks" fits on one line instead of breaking.
    longest = max((len(word) for word in (title or "").split()), default=0)
    size = " guide-drawn--xlong" if longest > 12 else " guide-drawn--long" if longest > 8 else ""
    return (f'<span class="{prefix}__art guide-drawn{size}" data-kind="{escape(kind or "", quote=True)}" aria-hidden="true">'
            f'<small>{escape(label)}</small><b>{escape(title or "")}</b></span>')


def _fan(body: str) -> str:
    """The first three covers in the guide, fanned out beside the title. Wide screens only (guide-reader.css);
    the copies load lazily, so a phone, where the fan is hidden, never fetches them."""
    covers, seen = [], set()
    for match in _PICK_ART.finditer(body):
        if len(covers) == FAN_COVERS:
            break
        tag = match.group(0)
        if tag.startswith("<img"):
            src = _SRC.search(tag)
            if not src or src.group(1) in seen:
                continue
            seen.add(src.group(1))
            covers.append(f'<img src="{src.group(1)}" alt="" width="136" height="204" loading="lazy" decoding="async" '
                          'referrerpolicy="no-referrer">')
        else:
            end = _matching_close(body, match.start(), _SPAN_TAG)
            if end < 0:
                continue
            art = body[match.start():end]
            name = re.search(r"<b>(.*?)</b>", art)
            key = name.group(1) if name else art
            if key in seen:
                continue
            seen.add(key)
            covers.append(art)
    if len(covers) < FAN_COVERS:
        return ""
    cards = "".join(f'<span class="guide-fan__card guide-fan__card--{n}">{cover}</span>' for n, cover in enumerate(covers, 1))
    return f'<div class="guide-fan" aria-hidden="true">{cards}</div>'


def _with_fan(header: str, fan: str) -> str:
    # Seasonal guides keep their own corner art (the moon, the wreath of lights) in that spot.
    if not fan or "sn-hero" in header:
        return header
    close = header.rfind("</header>")
    return header if close < 0 else header[:close] + fan + header[close:]


def _keep(body: str) -> str:
    """A short note for visitors in the rail: the save buttons work without an account. Only on pages
    that have guest save buttons; data-guest-only hides it from members (site-nav.js)."""
    if "data-guest-kind=" not in body:
        return ""
    return ('<div class="guide-rail__keep" data-guest-only><p class="guide-rail__label">Keep a list</p>'
            '<p>Save anything on this page as you read. No account needed, and a free one keeps the list '
            'on every device.</p>'
            '<a class="guide-rail__join" href="/#signup" data-guide-signup>Start a free library</a></div>')


def _rail(links: list[tuple[str, str]], minutes: int, checked, library: str = "", keep: str = "") -> str:
    # The links are copied from finished HTML, so an href is already escaped once.
    items = "".join(f'<li><a href="{escape(unescape(href), quote=True)}">{label}</a></li>' for href, label in links)
    toc = (f'<nav class="guide-toc" aria-label="Contents"><p class="guide-rail__label">On this page</p>'
           f'<ol>{items}</ol></nav>') if links else ""
    when = (f'<li>Checked <time datetime="{escape(checked[0], quote=True)}">{checked[1]}</time></li>'
            if checked else "")
    return (
        f'<aside class="guide-rail" aria-label="About this guide"><div class="guide-rail__inner">{toc}'
        '<div class="guide-rail__about"><p class="guide-rail__label">About this guide</p>'
        f'<ul><li>{minutes} min read</li>{when}<li>Reviewed by the site owner</li></ul>'
        '<p><a href="/content-quality">How we write guides</a></p>'
        '<p><a href="/corrections#send">Send a correction</a></p>'
        f'<p><a href="/corrections">Corrections log</a></p></div>{keep}{library}</div></aside>'
    )


def _support_note() -> str:
    """The end-of-guide note. Plain HTML, the same for everyone, so it can be cached with the page."""
    from . import supporters  # avoids loading the supporter code for every page that skips this layout
    kofi = escape(supporters.KOFI_URL, quote=True)
    founding = ('<p class="guide-support__founding"><span aria-hidden="true">★</span> Anyone who supports before 2027 '
                'stays a founding supporter for good.</p>') if supporters.founding_open() else ""
    return (
        '<aside class="guide-support" aria-labelledby="guide-support-title">'
        '<p class="guide-rail__label">Free to read</p>'
        '<h2 id="guide-support-title">Liked this guide?</h2>'
        '<p>OmniTrackr is run by one person, who checks every guide before it goes up, and nobody pays to be in one. '
        'If this one saved you some digging, a $3 coffee on Ko-fi helps pay for the servers that keep the guides and '
        'the tracker free.</p>'
        f'{founding}'
        f'<p class="guide-support__actions"><a class="site-btn site-btn--primary site-btn--sm" href="{kofi}" '
        'data-guide-kofi target="_blank" rel="noopener noreferrer">Buy a coffee on Ko-fi ↗</a>'
        '<a href="/supporters?from=guide">What supporters get</a></p>'
        '</aside>'
    )


def _canonical_path(html: str):
    match = _CANONICAL.search(html)
    return urlsplit(unescape(match.group(1))).path.rstrip("/") or "/" if match else None


def _crumbs(html: str) -> str:
    """A visible trail above the title (Home / Guides / Franchises in order), from the same
    steps as the page's BreadcrumbList data. The page itself is left off: its title is right below."""
    match = _CANONICAL.search(html)
    if not match:
        return ""
    from .page_breadcrumbs import trail
    steps = trail(unescape(match.group(1)), "")[:-1]
    if len(steps) < 2:
        return ""
    items = "".join(f'<li><a href="{escape(urlsplit(url).path or "/", quote=True)}">{escape(name)}</a></li>'
                    for name, url in steps)
    return f'<nav class="guide-crumbs" aria-label="Breadcrumb"><ol>{items}</ol></nav>'


def _library(html: str) -> str:
    path = _canonical_path(html)
    if not path:
        return ""
    from .guide_library import rail_html
    return rail_html(path)


def _with_crumbs(header: str, crumbs: str) -> str:
    """Put the trail first in the header. It replaces the old "← Back to the hub" link,
    which named the same hub."""
    if not crumbs:
        return header
    opened = _HEADER_TAG.match(header.lstrip())
    lead = len(header) - len(header.lstrip())
    start = lead + opened.end()
    back = _BACK_LINK.match(header, start)
    if back:
        return header[:start] + crumbs + header[back.end():]
    return header[:start] + crumbs + header[start:]


def _head_tags(html: str) -> str:
    # Pages are sent with a nonce-based CSP, added to their script tags before this
    # step runs, so the reader script borrows the nonce the page already carries.
    nonce = _NONCE.search(html)
    nonce_attr = f' nonce="{nonce.group(1)}"' if nonce else ""
    return (f'<link rel="preload" href="{SERIF_FONT}" as="font" type="font/woff2" crossorigin>'
            f'<link rel="stylesheet" href="/static/guide-reader.css?v={CSS_VERSION}">'
            f'<script src="/static/guide-reader.js?v={JS_VERSION}"{nonce_attr} defer></script>')


def add_reading_layout(html: str) -> str:
    if 'class="trail-guide' not in html or MARKER in html or "</head>" not in html:
        return html
    opened = _ARTICLE_OPEN.search(html)
    if not opened:
        return html
    article_end = _matching_close(html, opened.start(), _ARTICLE_TAG)
    if article_end < 0:
        return html
    inner_start = opened.end()
    close_start = html.rindex("</article>", inner_start, article_end)
    inner = html[inner_start:close_start]
    header_open = _HEADER_TAG.match(inner.lstrip())
    if not header_open or header_open.group(1):
        return html
    lead = len(inner) - len(inner.lstrip())
    header_end = _matching_close(inner, lead, _HEADER_TAG)
    if header_end < 0:
        return html
    header, body = inner[:header_end], inner[header_end:]
    if not body.strip():
        return html

    minutes = reading_minutes(inner)
    checked = None
    byline = _BYLINE.search(header)
    if byline:
        stamp = _TIME.search(byline.group(2))
        checked = (unescape(stamp.group(1)), stamp.group(2)) if stamp else None
        header = (header[:byline.end(2)] + f' <span class="guide-readtime">· {minutes} min read</span>'
                  + header[byline.end(2):])

    try:
        header = _with_crumbs(header, _crumbs(html))
    except Exception:
        pass  # the page keeps its own back link
    try:
        library = _library(html)
    except Exception:
        library = ""
    try:
        support = _support_note()
    except Exception:
        support = ""
    links = _contents(header)
    header = _with_fan(header, _fan(body))
    layout = (f'{header}<div class="guide-columns" {MARKER}><div class="guide-body">{body}{support}</div>'
              f'{_rail(links, minutes, checked, library, _keep(body))}</div>')
    html = html[:inner_start] + layout + html[close_start:]
    return html.replace("</head>", _head_tags(html) + "</head>", 1)
