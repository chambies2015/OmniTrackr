"""Visitors who arrive from a search engine, followed by the kind of page they landed on.

Google sends people to guides and title pages, not to the homepage, so the homepage
funnel says nothing about them. This keeps four anonymous counters per landing
section in ``site_traffic_daily`` (kind "search_journey", key "<section>|<step>"):

- landed: a likely person opened a page with a search engine as the referrer
  (counted from static/visit.js, guests only);
- saved: that visitor then saved a title to their guest list;
- signup: they opened the sign-up form or pressed a Google sign-up button;
- account: an account was made in that browser.

The link between steps is a one-day first-party cookie that static/visit.js sets
on the landing page. It holds only the first part of the landing page's address
(for example "in-order"), never an identifier, and nothing about the visitor is
stored with a count.
"""
from __future__ import annotations

import re
from typing import Optional

COOKIE = "omnitrackr_from_search"
KIND = "search_journey"

# Hosts (without "www.") whose referrals are web searches. Mirrored in static/visit.js.
SEARCH_HOST = re.compile(
    r"(?:^|\.)(?:google\.[a-z.]{2,8}|bing\.com|duckduckgo\.com|yahoo\.[a-z.]{2,8}|ecosia\.org|search\.brave\.com"
    r"|yandex\.[a-z.]{2,8}|baidu\.com|startpage\.com|qwant\.com|kagi\.com)$"
)

# The landing sections Site stats lists, in this order: (cookie value, label).
SECTIONS = (
    ("in-order", "In order guides"),
    ("binge-calculator", "Binge calculator guides"),
    ("if-you-liked", "If you liked guides"),
    ("best-of", "Best of lists"),
    ("discover", "Discover trails and monthly editions"),
    ("titles", "Title pages"),
    ("trackers", "Tracker guides (movie, anime, book...)"),
    ("switch", "Switching guides"),
    ("new-releases", "New release guides"),
    ("holidays", "Holiday and seasonal guides"),
    ("browse", "Browse shelves"),
    ("awards", "Awards ballots"),
    ("reviews", "Reviews"),
    ("collections", "Public lists"),
    ("home", "Homepage"),
    ("other", "Anything else"),
)
SECTION_KEYS = {key for key, _ in SECTIONS}
# First address parts that share a section with another one.
ALIASES = {
    "halloween": "holidays", "new-this-week": "new-releases", "release-radar": "new-releases",
    "u": "other", "lists": "collections", "use-cases": "trackers", "media-tracking": "trackers",
}

STEPS = (
    ("landed", "Landed from a search"),
    ("saved", "Saved a title"),
    ("signup", "Started signing up"),
    ("account", "Made an account"),
)
# Funnel events (app/funnel.py) that move a search visitor along.
EVENT_STEPS = {"guest_pick_added": "saved", "signup_form_opened": "signup", "signup_created": "account"}

_SEGMENT = re.compile(r"^[a-z0-9-]{1,40}$")


def section_for(value: str) -> str:
    """The section for a page address ("/in-order/star-wars") or a cookie value ("in-order")."""
    value = (value or "").strip().lower()
    segment = value.lstrip("/").split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if value in ("/", "home") or (value.startswith("/") and not segment):
        return "home"
    if not _SEGMENT.fullmatch(segment):
        return "other"
    if segment.endswith("-tracker"):
        return "trackers"
    segment = ALIASES.get(segment, segment)
    return segment if segment in SECTION_KEYS else "other"


def is_search(source: Optional[str]) -> bool:
    """True when site_traffic.source_for() named a search engine."""
    return bool(source) and bool(SEARCH_HOST.search(source))


def cookie_section(request) -> Optional[str]:
    """The landing section carried by this browser's cookie, or None without one."""
    try:
        value = request.cookies.get(COOKIE)
    except Exception:
        return None
    if not value or len(value) > 40:
        return None
    return section_for(value)


def key(section: str, step: str) -> str:
    return f"{section}|{step}"


def step_key(event: str, request) -> Optional[str]:
    """The counter a funnel event adds to for a search visitor, or None."""
    step = EVENT_STEPS.get(event)
    if step is None or request is None:
        return None
    section = cookie_section(request)
    if section is None:
        return None
    if step != "account":
        from .site_traffic import AUTH_COOKIE_NAME
        if AUTH_COOKIE_NAME in request.cookies:
            return None  # Members saving and browsing are not search visitors signing up.
    return key(section, step)


def summary(counts: dict[str, int]) -> dict:
    """Shape {"<section>|<step>": count} for Site stats: totals plus one row per section seen."""
    totals = {step: 0 for step, _ in STEPS}
    rows = []
    for section, label in SECTIONS:
        values = {step: int(counts.get(key(section, step), 0)) for step, _ in STEPS}
        for step, value in values.items():
            totals[step] += value
        if any(values.values()):
            rows.append({"section": section, "label": label, **values})
    rows.sort(key=lambda row: (-row["landed"], -row["account"], -row["saved"]))
    return {
        "steps": [{"event": step, "label": label, "count": totals[step]} for step, label in STEPS],
        "sections": rows,
    }
