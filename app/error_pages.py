"""Error pages for people browsing the site.

Browsers asking for HTML get a styled page with the shared header and footer
(not found, too many requests, server error). API clients and the dashboard's
fetch() calls keep JSON bodies, so nothing that parses `detail` changes.

Every page here carries `noindex`: error responses should never be listed in
search results or counted as thin content.
"""
from __future__ import annotations

import re
from html import escape

from fastapi import Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from .csp import strict_html_response
from .site_chrome import message_page


HTML_ERROR_EXCLUDED_PREFIXES = ("/api/", "/auth/", "/static/", "/docs", "/redoc", "/openapi.json")

SERVER_ERROR_DETAIL = "Something went wrong on our side. Please try again in a moment."

# (label, href, one-line description) shown under the buttons on a not-found page.
PLACES = (
    ("Popular titles", "/titles", "What members are tracking right now"),
    ("Release Radar", "/release-radar", "Out this week and coming soon"),
    ("Member reviews", "/reviews", "Reviews written by people who finished it"),
    ("Guides", "/guides", "How to track, import and get started"),
)

# Path prefix -> (heading, message, actions) for things that go missing for a known reason.
NOT_FOUND_COPY = (
    ("/u/", "This profile isn't available",
     "The member may have changed their username, made their profile private, or closed their account.",
     (("Browse member reviews", "/reviews"), ("Go to the homepage", "/"))),
    ("/titles/", "We don't have a page for that title yet",
     "Title pages appear once members start tracking something. Try a search, or add it to your own library.",
     (("Browse popular titles", "/titles"), ("Start your library", "/#signup"))),
    ("/people/", "We couldn't find that person",
     "People pages are built from the titles members track. This one may have been renamed or merged.",
     (("Browse people", "/people"), ("Browse popular titles", "/titles"))),
    ("/collections/", "This collection isn't available",
     "Its owner may have made it private or deleted it.",
     (("Explore collections", "/collections/explore"), ("Go to the homepage", "/"))),
)
DEFAULT_NOT_FOUND = (
    "This page drifted into the void",
    "The link may be old or mistyped. Search for what you were after, or pick one of the places below.",
    (("Go to the homepage", "/"), ("See what's coming out", "/release-radar"), ("Browse reviews", "/reviews")),
)

_HINT_WORDS = re.compile(r"[a-z0-9]+")
_TRAILING_ID = re.compile(r"(?:^|-)\d+$")


def wants_html_page(request: Request) -> bool:
    return (request.method in ("GET", "HEAD")
            and "text/html" in request.headers.get("accept", "")
            and not request.url.path.startswith(HTML_ERROR_EXCLUDED_PREFIXES))


def search_hint(path: str) -> str:
    """Turn the last part of a missing URL into a search, e.g. /titles/movie/the-matrixx -> "the matrixx"."""
    last = path.rstrip("/").rsplit("/", 1)[-1].lower()
    last = _TRAILING_ID.sub("", last)
    words = _HINT_WORDS.findall(last.replace("%20", " "))
    hint = " ".join(word for word in words if not word.isdigit())
    return hint[:60].strip() if len(hint) >= 2 else ""


def _search_and_places(hint: str) -> str:
    label = f'Search for &ldquo;{escape(hint)}&rdquo;' if hint else "Search movies, shows, anime, games, books…"
    search = (
        f'    <a class="site-message__search" href="/titles" data-site-search-open data-search-hint="{escape(hint, quote=True)}">'
        '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>'
        f'<span>{label}</span></a>\n'
    )
    cards = "".join(
        f'<li><a href="{escape(href, quote=True)}"><strong>{escape(name)}</strong><span>{escape(blurb)}</span></a></li>'
        for name, href, blurb in PLACES
    )
    return (
        f'{search}'
        '    <nav class="site-message__places" aria-label="Popular places">'
        f'<h2>Popular places</h2><ul>{cards}</ul></nav>\n'
        '    <p class="site-message__note">Followed a broken link on OmniTrackr? '
        '<a href="/contact">Tell us where</a> and we\'ll fix it.</p>\n'
    )


def not_found_page(path: str) -> str:
    heading, message, actions = DEFAULT_NOT_FOUND
    for prefix, *copy in NOT_FOUND_COPY:
        if path.startswith(prefix):
            heading, message, actions = copy
            break
    # The finder searches titles, so a missing username is not worth searching for.
    hint = "" if path.startswith("/u/") else search_hint(path)
    return message_page("Page not found", heading, message, eyebrow="404", actions=actions,
                        extra_html=_search_and_places(hint))


def server_error_page() -> str:
    return message_page(
        "Something went wrong", "Something broke on our end",
        "That one's on us. Your library is safe. Try the page again in a moment, and if it keeps "
        "happening, let us know what you were doing.",
        eyebrow="500",
        actions=(("Go to the homepage", "/"), ("Report the problem", "/contact")),
    )


def rate_limited_page() -> str:
    return message_page(
        "Too many requests", "Give it a minute",
        "That was a lot of requests in a short time, so we paused things for a moment. "
        "Wait about a minute, then reload the page.",
        eyebrow="429",
    )


def _noindex(response):
    response.headers["X-Robots-Tag"] = "noindex"
    return response


async def http_error(request: Request, exc: StarletteHTTPException):
    """Browsers get a styled 404 page for public URLs; API clients keep JSON errors."""
    if exc.status_code == 404 and wants_html_page(request):
        return _noindex(strict_html_response(not_found_page(request.url.path), status_code=404))
    return await http_exception_handler(request, exc)


def rate_limited(request: Request, exc: RateLimitExceeded):
    response = _rate_limit_exceeded_handler(request, exc)
    if not wants_html_page(request):
        return response
    page = _noindex(strict_html_response(rate_limited_page(), status_code=429))
    for header in ("Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"):
        if header in response.headers:
            page.headers[header] = response.headers[header]
    return page


async def server_error(request: Request, exc: Exception):
    """Unhandled errors. Starlette still logs the traceback after this returns.

    This runs outside the app's middleware, so the headers it would add are set here.
    """
    if wants_html_page(request):
        response = strict_html_response(server_error_page(), status_code=500)
    else:
        response = JSONResponse({"detail": SERVER_ERROR_DETAIL}, status_code=500)
    response.headers.update({
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    })
    return _noindex(response)


def install(app) -> None:
    app.add_exception_handler(RateLimitExceeded, rate_limited)
    app.add_exception_handler(StarletteHTTPException, http_error)
    app.add_exception_handler(Exception, server_error)
