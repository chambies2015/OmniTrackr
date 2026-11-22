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
                   "music": "Album", "book": "Book", "manga": "Manga", "podcast": "Podcast", "audiobook": "Audiobook"}


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


# The homepage is in English, so its three quotes are too: a review in Polish or Spanish there
# reads to a new visitor like spam, even though /reviews rightly shows every language.
ENGLISH_WORDS = frozenset("the and a an to of is it in i this that was for but with you on not as are be its my "
                          "so if at by from have has had they he she we what all just more than very really".split())
ENGLISH_SHARE = 0.12
ACCENTED_SHARE = 0.04
# Everyday words of the other languages members write in (Spanish, Portuguese, Polish, French,
# German, Italian) that aren't English words too. A Spanish review with an English phrase in it
# ("unsettling at times pero eso añade a la experiencia") clears the share above on "a" and "at"
# alone; these outnumber the English ones in it. Polish "i", "a", "to" and "on" count as English
# above, so Polish needs its own words here.
# Words that are also everyday English ("do", "per", "con", "pour") are left out.
OTHER_WORDS = frozenset("que de la el los las y es una un por muy pero se del lo su para como más también "
                        "não é uma com os muito mas da são "
                        "jest nie się na w z że ale jak bardzo tak już tylko "
                        "le les et est des une pas qui dans du très avec "
                        "und der das ist nicht ein eine mit sehr auch ich "
                        "che di il è non sono molto anche".split())


def reads_as_english(text: str) -> bool:
    """True when common English words make up a fair share of the text and clearly outnumber
    the everyday words of other languages (a rough check, no library)."""
    words = [word.strip(".,;:!?\"'()[]…-—’“”").casefold() for word in (text or "").split()]
    words = [word for word in words if word]
    if len(words) < 8:
        return False
    english = sum(word in ENGLISH_WORDS for word in words)
    other = sum(word in OTHER_WORDS for word in words)
    letters = [char for char in text if char.isalpha()]
    # About one letter in seventeen of Polish is ą, ł, ś or the like; English rarely needs more
    # than a "Pokémon" or a "Sōsō no Frieren".
    accented = sum(not char.isascii() for char in letters)
    return (english / len(words) >= ENGLISH_SHARE and english > 2 * other
            and accented <= ACCENTED_SHARE * len(letters))


def pick_reviews(reviews: list[dict]) -> list[dict]:
    """Newest standalone reviews in English, one per member, preferring a mix of media types."""
    chosen, members, categories = [], set(), set()
    standalone = [r for r in reviews if r.get("search_ready") and not r.get("spoilers") and (r.get("title") or "").strip()
                  and reads_as_english(r.get("review") or "")]
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
    for model in (models.Movie, models.TVShow, models.Anime, models.VideoGame, models.Music, models.Book, models.Manga, models.Podcast, models.Audiobook):
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
        badge = '<span class="lp-voice__badge">Review of the week</span> · ' if review.get("spotlight") else ""
        cards.append(
            f'<li class="lp-voice{" lp-voice--spotlight" if review.get("spotlight") else ""}">'
            f'<p class="lp-voice__meta"><span>{badge}{escape(CATEGORY_LABELS.get(review["category"], "Title"))}</span>{rating_html}</p>'
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
    try:
        from . import review_spotlight
        spotlight = review_spotlight.build(db)
    except Exception:
        spotlight = None
    if spotlight:
        key = (spotlight["category"], spotlight["id"])
        feed = [dict(spotlight, spotlight=True)] + [r for r in feed if (r["category"], r["id"]) != key]
    chosen = pick_reviews(feed)
    reviews_router._attach_profile_urls(db, chosen)
    # The member and title counts sit in the numbers band above (pulse_html), not here too.
    return section_html(chosen, {})


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
        _counts_cache["at"], _counts_cache["counts"] = 0.0, None
        _pulse_cache["at"], _pulse_cache["html"] = 0.0, None


_counts_cache = {"at": 0.0, "counts": None}


def hero_proof_html(counts: dict) -> str:
    """One line under the hero buttons, shown only once the numbers are worth saying."""
    members, titles = counts.get("members", 0), counts.get("titles", 0)
    if members < MIN_MEMBERS_SHOWN:
        return ""
    line = f"<strong>{round_down(members)}</strong> members"
    if titles >= 100:
        line += f" have tracked <strong>{round_down(titles)}</strong> titles here"
    else:
        line += " keep their lists here"
    return f'<p class="lp-hero__proof">{line}.</p>'


def hero_section(session_factory=None) -> str:
    """Cached hero proof line (refreshed every 10 minutes; never raises)."""
    now = time.monotonic()
    with _lock:
        counts = _counts_cache["counts"]
        fresh = counts is not None and now - _counts_cache["at"] < CACHE_SECONDS
    if not fresh:
        try:
            if session_factory is None:
                from .database import SessionLocal as session_factory
            db = session_factory()
            try:
                counts = stats(db)
            finally:
                db.close()
        except Exception:
            counts = counts or {}
        with _lock:
            _counts_cache["at"], _counts_cache["counts"] = now, counts
    return hero_proof_html(counts or {})


# ---------------------------------------------------------------- numbers band
# A row of live counts on the homepage. Each number is read from the database,
# rounded down (round_down) and only shown once it clears its floor, so a quiet
# month shows fewer numbers instead of small ones. The band needs two numbers.
PULSE_DAYS = 30
PULSE_FLOORS = {"members": MIN_MEMBERS_SHOWN, "titles": 100, "added": 50, "finished": 25}
PULSE_LABELS = (
    ("members", "members", "with a library here"),
    ("titles", "titles", "in members' libraries"),
    ("added", "added", f"in the last {PULSE_DAYS} days"),
    ("finished", "finished", f"logged in the last {PULSE_DAYS} days"),
)
_pulse_cache = {"at": 0.0, "html": None}


def pulse_counts(db, now=None) -> dict:
    from datetime import datetime, timedelta

    from sqlalchemy import func

    from . import models
    since = (now or datetime.utcnow()) - timedelta(days=PULSE_DAYS)
    counts = stats(db)
    added = 0
    for model in (models.Movie, models.TVShow, models.Anime, models.VideoGame, models.Music, models.Book, models.Manga, models.Podcast, models.Audiobook):
        added += db.query(func.count(model.id)).filter(model.added_at >= since).scalar() or 0
    finished = db.query(func.count(models.ActivityEntry.id)).filter(
        models.ActivityEntry.action.in_(("completed", "revisited")), models.ActivityEntry.occurred_at >= since).scalar() or 0
    counts.update(added=int(added), finished=int(finished))
    return counts


def pulse_html(counts: dict) -> str:
    shown = [(key, noun, note) for key, noun, note in PULSE_LABELS if counts.get(key, 0) >= PULSE_FLOORS[key]]
    if len(shown) < 2:
        return ""
    cells = "".join(
        f'<li class="lp-pulse__cell"><strong class="lp-pulse__num">{round_down(int(counts[key]))}</strong>'
        f'<span class="lp-pulse__noun">{noun}</span><span class="lp-pulse__note">{note}</span></li>'
        for key, noun, note in shown)
    return (
        '<section class="lp-pulse" aria-labelledby="lp-pulse-title"><div class="lp-wrap lp-pulse__inner">'
        '<h2 id="lp-pulse-title" class="lp-pulse__title">OmniTrackr right now <span>Live counts, rounded down</span></h2>'
        f'<ul class="lp-pulse__list lp-pulse__list--{len(shown)}">{cells}</ul>'
        '</div></section>'
    )


def pulse_section(session_factory=None) -> str:
    """Cached numbers band (refreshed every 10 minutes; never raises)."""
    now = time.monotonic()
    with _lock:
        if _pulse_cache["html"] is not None and now - _pulse_cache["at"] < CACHE_SECONDS:
            return _pulse_cache["html"]
    html = ""
    try:
        if session_factory is None:
            from .database import SessionLocal as session_factory
        db = session_factory()
        try:
            html = pulse_html(pulse_counts(db))
        finally:
            db.close()
    except Exception:
        html = ""
    with _lock:
        _pulse_cache["at"], _pulse_cache["html"] = now, html
    return html
