"""Reading layout for the written guides (if-you-liked, in order, best of, release
guides, holiday and gift guides, Discover guides and monthly editions).

Every guide router builds its page the same way: an ``<article class="trail-guide">``
that opens with a ``hero--guide`` header holding the title, a byline and a row of
"On this page" links. ``add_reading_layout`` is an html_finish step that turns that
shared shape into a magazine page without each router having to know about it:

* the guide stylesheet, the serif used for reading and a small script go into <head>,
* the byline gets a reading time worked out from the article's own text,
* everything after the header goes into a body column, with a rail beside it that
  repeats the page's contents links and says when the guide was last checked.

The header's own links stay where they are: they are the contents on phones, and
the stylesheet hides them on wide screens where the rail shows the same list.
A page without that shape is returned unchanged.
"""
from __future__ import annotations

import math
import re
from html import escape, unescape

CSS_VERSION = "20261110-reader-1"
JS_VERSION = "20261110-reader-1"
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


def _rail(links: list[tuple[str, str]], minutes: int, checked) -> str:
    items = "".join(f'<li><a href="{escape(href, quote=True)}">{label}</a></li>' for href, label in links)
    toc = (f'<nav class="guide-toc" aria-label="Contents"><p class="guide-rail__label">On this page</p>'
           f'<ol>{items}</ol></nav>') if links else ""
    when = (f'<li>Checked <time datetime="{escape(checked[0], quote=True)}">{checked[1]}</time></li>'
            if checked else "")
    return (
        f'<aside class="guide-rail" aria-label="About this guide"><div class="guide-rail__inner">{toc}'
        '<div class="guide-rail__about"><p class="guide-rail__label">About this guide</p>'
        f'<ul><li>{minutes} min read</li>{when}<li>Reviewed by the site owner</li></ul>'
        '<p><a href="/content-quality">How we write guides</a></p>'
        '<p><a href="/contact">Send a correction</a></p></div></div></aside>'
    )


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

    layout = (f'{header}<div class="guide-columns" {MARKER}><div class="guide-body">{body}</div>'
              f'{_rail(_contents(header), minutes, checked)}</div>')
    html = html[:inner_start] + layout + html[close_start:]
    return html.replace("</head>", _head_tags(html) + "</head>", 1)
