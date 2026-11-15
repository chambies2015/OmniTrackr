"""Mark sign-in and sign-up links as nofollow on every page.

Guides, gift lists, the advent calendar and Release Radar all send guests to
the homepage's account card with the page to come back to, as
``/?next=<path>#signup``. Each of those is a different URL to a crawler, so the
November 15, 2026 crawl found Google being handed one homepage copy per guide
(about forty), all with the same title and a canonical pointing back at ``/``.
Several routers already wrote ``rel="nofollow"`` on theirs; this step catches
the rest in one place instead of in every router.
"""
from __future__ import annotations

import re

_ACCOUNT_LINK = re.compile(
    r'<a\b(?=[^>]*\shref="(?:https://omnitrackr\.xyz)?/\?(?:next|login)=)[^>]*>',
    re.I,
)
_REL = re.compile(r'\srel="([^"]*)"', re.I)


def _nofollow(match: re.Match) -> str:
    tag = match.group(0)
    rel = _REL.search(tag)
    if rel is None:
        return tag[:2] + ' rel="nofollow"' + tag[2:]
    values = rel.group(1).split()
    if "nofollow" in (value.lower() for value in values):
        return tag
    return tag[:rel.start(1)] + " ".join(values + ["nofollow"]) + tag[rel.end(1):]


def nofollow_account_links(html: str) -> str:
    if "?next=" not in html and "?login=" not in html:
        return html
    return _ACCOUNT_LINK.sub(_nofollow, html)
