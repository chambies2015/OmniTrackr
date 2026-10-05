"""Homepage proof that real people use OmniTrackr: a few recent member reviews and live counts.

Only reviews members chose to make public, that pass the same standalone-quality and
moderation checks as /reviews, are shown (at most one per member). Counts come from the
database and are rounded down, never inflated. The section disappears entirely when there
isn't enough to show, and the homepage never fails because of it.
"""
from __future__ import annotations

import threading
import time
from html import escape

CACHE_SECONDS = 600
MIN_REVIEWS = 2
MAX_REVIEWS = 3
EXCERPT_CHARS = 220
MIN_MEMBERS_SHOWN = 50

_lock = threading.Lock()
_cache = {"at": 0.0, "html": None}

CATEGORY_LABELS = {"movie": "Movie", "tv_show": "TV show", "anime": "Anime", "video_game": "Game",
                   "music": "Album", "book": "Book"}


def _excerpt(text: str) -> str:
    text = " ".join((text or "").split())
    if len(text) <= EXCERPT_CHARS:
        return text
    return text[:EXCERPT_CHARS].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"


def round_down(count: int) -> str:
    """'206' -> '200+', '1,234' -> '1,200+': honest, and doesn't need updating every day."""
    if count < 100:
        return str(count)
    step = 100 if count < 1000 else (500 if count < 10000 else 1000)
    return f"{(count // step) * step:,}+"


def pick_reviews(reviews: list[dict]) -> list[dict]:
    """Newest standalone reviews, one per member, preferring a mix of media types."""
    chosen, members, categories = [], set(), set()
    standalone = [r for r in reviews if r.get("search_ready") and (r.get("title") or "").strip()]
    for prefer_new_category in (True, False):
        for review in standalone:
            if len(chosen) >= MAX_REVIEWS:
                break
            if review in chosen or review.get("user_id") in members:
                continue
            if prefer_new_category and review.get("category") in categories:
                continue
            chosen.append(review)
            members.add(review.get("user_id"))
            categories.add(review.get("category"))
    return chosen


def stats(db) -> dict:
    from sqlalchemy import func

    from . import models
    members = db.query(func.count(models.User.id)).filter(
        models.User.is_active == True, models.User.is_verified == True).scalar() or 0  # noqa: E712
    titles = 0
    for model in (models.Movie, models.TVShow, models.Anime, models.VideoGame, models.Music, models.Book):
        titles += db.query(func.count(model.id)).scalar() or 0
    return {"members": int(members), "titles": int(titles)}


def section_html(reviews: list[dict], counts: dict) -> str:
    if len(reviews) < MIN_REVIEWS:
        return ""
    cards = []
    for review in reviews:
        url = f"/reviews/{int(review['id'])}?category={escape(review['category'], quote=True)}"
        rating = review.get("rating")
        rating_html = (f'<span class="lp-voice__rating" aria-label="Rated {float(rating):g} out of 10">{float(rating):g}/10</span>'
                       if rating is not None else "")
        name = escape(review.get("username") or "A member")
        profile = review.get("profile_url")
        author = (f'<a href="{escape(profile, quote=True)}">{name}</a>'
                  if isinstance(profile, str) and profile.startswith("/u/") else name)
        cards.append(
            '<li class="lp-voice">'
            f'<p class="lp-voice__meta"><span>{escape(CATEGORY_LABELS.get(review["category"], "Title"))}</span>{rating_html}</p>'
            f'<h3 class="lp-voice__title"><a href="{url}">{escape(review["title"])}</a></h3>'
            f'<blockquote class="lp-voice__quote"><p>{escape(_excerpt(review.get("review") or ""))}</p></blockquote>'
            f'<p class="lp-voice__by">— {author} · <a href="{url}">Read the review</a></p>'
            '</li>'
        )
    facts = []
    if counts.get("members", 0) >= MIN_MEMBERS_SHOWN:
        facts.append(f'<strong>{round_down(counts["members"])}</strong> members')
    if counts.get("titles", 0) >= 100:
        facts.append(f'<strong>{round_down(counts["titles"])}</strong> titles tracked')
    facts_html = f'<p class="lp-voices__facts">{" · ".join(facts)}</p>' if facts else ""
    return (
        '<section class="lp-section lp-voices" aria-labelledby="lp-voices-title"><div class="lp-wrap">'
        '<div class="lp-section-head"><p class="lp-eyebrow">From the community</p>'
        '<h2 id="lp-voices-title">What members are saying</h2>'
        f'{facts_html}</div>'
        f'<ul class="lp-voices__list">{"".join(cards)}</ul>'
        '<p class="lp-voices__more"><a href="/reviews">Read more member reviews</a> · '
        '<a href="#landing-auth" data-action="show-register-form">Write your own, free</a></p>'
        '</div></section>'
    )


def build(db) -> str:
    from .routers import reviews as reviews_router
    feed = reviews_router._public_review_feed(db, None, "", 40, 0)["reviews"]
    chosen = pick_reviews(feed)
    reviews_router._attach_profile_urls(db, chosen)
    return section_html(chosen, stats(db))


def homepage_section(session_factory=None) -> str:
    """Cached HTML for the homepage (refreshed every 10 minutes; never raises)."""
    now = time.monotonic()
    with _lock:
        if _cache["html"] is not None and _cache["at"] and now - _cache["at"] < CACHE_SECONDS:
            return _cache["html"]
    html = ""
    try:
        if session_factory is None:
            from .database import SessionLocal as session_factory
        db = session_factory()
        try:
            html = build(db)
        finally:
            db.close()
    except Exception:
        html = ""
    with _lock:
        _cache["at"], _cache["html"] = now, html
    return html


def clear_cache() -> None:
    with _lock:
        _cache["at"], _cache["html"] = 0.0, None
