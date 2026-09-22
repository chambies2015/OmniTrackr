"""
Public review endpoints for the OmniTrackr API.
"""
import html
import hashlib
import heapq
import json
import os
import re
from datetime import datetime
from typing import List, Optional
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError

from .. import models, schemas
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..review_quality import evaluate_public_review
from ..visitor_identity import set_visitor_cookie, visitor_identity

router = APIRouter(tags=["reviews"])

SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
PUBLIC_REVIEW_MIN_CHARS = int(os.getenv("PUBLIC_REVIEW_MIN_CHARS", "80"))
PUBLIC_REVIEW_DETAIL_MIN_CHARS = int(os.getenv("PUBLIC_REVIEW_DETAIL_MIN_CHARS", "240"))
PUBLIC_REVIEW_REPORT_THRESHOLD = max(2, int(os.getenv("PUBLIC_REVIEW_REPORT_THRESHOLD", "3")))
ADSENSE_PUBLISHER_ID = os.getenv("ADSENSE_PUBLISHER_ID", "pub-7271682066779719")
ADSENSE_ACCOUNT = ADSENSE_PUBLISHER_ID if ADSENSE_PUBLISHER_ID.startswith("ca-") else f"ca-{ADSENSE_PUBLISHER_ID}"

CATEGORY_LABELS = {
    "movie": "Movie",
    "tv_show": "TV Show",
    "anime": "Anime",
    "video_game": "Video Game",
    "music": "Music",
    "book": "Book",
}
CATEGORY_MODELS = {
    "movie": models.Movie,
    "tv_show": models.TVShow,
    "anime": models.Anime,
    "video_game": models.VideoGame,
    "music": models.Music,
    "book": models.Book,
}
LIBRARY_CATEGORIES = {
    "movie": "movies", "tv_show": "tv-shows", "anime": "anime",
    "video_game": "video-games", "music": "music", "book": "books",
}
# These fields are already exposed in public reviews. Personal state is never copied.
PUBLIC_METADATA_FIELDS = {
    "movie": ("director", "year", "poster_url"),
    "tv_show": ("year", "seasons", "episodes", "poster_url"),
    "anime": ("year", "seasons", "episodes", "poster_url"),
    "video_game": ("release_date", "genres", "cover_art_url"),
    "music": ("artist", "year", "cover_art_url"),
    "book": ("author", "year", "cover_art_url"),
}

CATEGORY_REVIEW_CONTEXT = {
    "movie": {
        "plural": "Movie",
        "title": "Movie Reviews - OmniTrackr",
        "description": "Read public OmniTrackr movie reviews with ratings, director and year context, pacing notes, rewatch value, and personal recommendations.",
        "intro": "Browse public movie reviews from OmniTrackr users, including ratings, director details, release year context, pacing notes, rewatch value, and personal recommendations.",
    },
    "tv_show": {
        "plural": "TV Show",
        "title": "TV Show Reviews - OmniTrackr",
        "description": "Read public OmniTrackr TV show reviews with ratings, season context, episode notes, binge value, pacing, and viewer recommendations.",
        "intro": "Browse public TV show reviews from OmniTrackr users, including season context, episode notes, binge value, pacing, and viewer recommendations.",
    },
    "anime": {
        "plural": "Anime",
        "title": "Anime Reviews - OmniTrackr",
        "description": "Read public OmniTrackr anime reviews with ratings, season context, episode notes, tone, pacing, and personal recommendations.",
        "intro": "Browse public anime reviews from OmniTrackr users, including season context, episode notes, tone, pacing, and personal recommendations.",
    },
    "video_game": {
        "plural": "Video Game",
        "title": "Video Game Reviews - OmniTrackr",
        "description": "Read public OmniTrackr video game reviews with ratings, genre context, backlog fit, mechanics, difficulty, replay value, and recommendations.",
        "intro": "Browse public video game reviews from OmniTrackr users, including genre context, backlog fit, mechanics, difficulty, replay value, and recommendations.",
    },
    "music": {
        "plural": "Music",
        "title": "Music Reviews - OmniTrackr",
        "description": "Read public OmniTrackr music reviews with ratings, artist and year context, album moods, relisten value, and listener recommendations.",
        "intro": "Browse public music reviews from OmniTrackr users, including artist and year context, album moods, relisten value, and listener recommendations.",
    },
    "book": {
        "plural": "Book",
        "title": "Book Reviews - OmniTrackr",
        "description": "Read public OmniTrackr book reviews with ratings, author and year context, reading pace, audience fit, reread value, and recommendations.",
        "intro": "Browse public book reviews from OmniTrackr users, including author and year context, reading pace, audience fit, reread value, and recommendations.",
    },
}


def _escape(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _safe_json_ld(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")


def _json_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        converted = float(value)
        return int(converted) if converted.is_integer() else converted
    except (TypeError, ValueError, AttributeError):
        return str(value)


def _normalized_category(category: Optional[str]) -> Optional[str]:
    return category if category in CATEGORY_REVIEW_CONTEXT else None


def _not_found_reviews_category_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="robots" content="noindex, follow">
  <title>Review Category Not Found - OmniTrackr</title>
  <link rel="stylesheet" href="/styles.css?v=20260917-review-safety-v1">
  <style>
    body { min-height: 100vh; padding: 20px; }
    .review-wrapper { max-width: 900px; margin: 0 auto; }
    .review-container { background: var(--card-bg); border: 1px solid var(--border); border-radius: 16px; color: var(--fg); margin: 20px 0; padding: 40px; }
    .back-link { color: var(--primary); display: inline-block; font-weight: 500; margin-bottom: 20px; text-decoration: none; }
  </style>
</head>
<body class="dark-mode">
  <main class="review-wrapper">
    <a href="/reviews" class="back-link">Back to Reviews</a>
    <section class="review-container">
      <h1>Review category not found</h1>
      <p>This review category is unavailable. Browse the public reviews directory to find movies, TV shows, anime, games, music, and books with substantial public review text.</p>
    </section>
  </main>
</body>
</html>"""


def _apply_category_review_context(page: str, category: Optional[str]) -> str:
    category = _normalized_category(category)
    if not category:
        return page

    context = CATEGORY_REVIEW_CONTEXT[category]
    category_url = f"{SITE_URL}/reviews?category={category}"
    page = page.replace(
        "<title>Public Media Reviews for Movies, Shows, Games, Music & Books - OmniTrackr</title>",
        f"<title>{_escape(context['title'])}</title>",
    )
    page = page.replace(
        '<meta name="description" content="Read public OmniTrackr reviews for movies, TV shows, anime, video games, music, and books. Discover ratings and recommendations from media fans.">',
        f'<meta name="description" content="{_escape(context["description"])}">',
    )
    page = page.replace(
        '<link rel="canonical" href="https://omnitrackr.xyz/reviews">',
        f'<link rel="canonical" href="{_escape(category_url)}">',
        1,
    )
    page = page.replace(
        '<meta property="og:url" content="https://omnitrackr.xyz/reviews">',
        f'<meta property="og:url" content="{_escape(category_url)}">',
        1,
    )
    page = page.replace(
        '<meta property="og:title" content="Public Media Reviews - OmniTrackr">',
        f'<meta property="og:title" content="{_escape(context["title"])}">',
    )
    page = page.replace(
        '<meta property="og:description" content="Read public reviews and ratings for movies, TV shows, anime, video games, music, and books from the OmniTrackr community.">',
        f'<meta property="og:description" content="{_escape(context["description"])}">',
    )
    page = page.replace(
        '<meta name="twitter:url" content="https://omnitrackr.xyz/reviews">',
        f'<meta name="twitter:url" content="{_escape(category_url)}">',
        1,
    )
    page = page.replace(
        '<meta name="twitter:title" content="Public Media Reviews - OmniTrackr">',
        f'<meta name="twitter:title" content="{_escape(context["title"])}">',
    )
    page = page.replace(
        '<meta name="twitter:description" content="Read public reviews and ratings for movies, shows, anime, games, music, and books.">',
        f'<meta name="twitter:description" content="{_escape(context["description"])}">',
    )
    page = page.replace(
        '<h1>Public Reviews</h1>',
        f"<h1>{_escape(context['plural'])} Reviews</h1>",
        1,
    )
    page = page.replace(
        "Find your next favorite through the movies, shows, games, music, and books people are talking about.",
        _escape(context["intro"]),
        1,
    )
    page = page.replace(f'<option value="{category}">', f'<option value="{category}" selected>', 1)
    return page


def _review_is_substantial(review: dict) -> bool:
    if "community_ready" in review:
        return bool(review["community_ready"])
    return evaluate_public_review(
        review.get("review"), PUBLIC_REVIEW_MIN_CHARS, PUBLIC_REVIEW_DETAIL_MIN_CHARS
    ).community_ready


def _review_is_standalone(review: dict) -> bool:
    if not (review.get("title") or "").strip():
        return False
    if "search_ready" in review:
        return bool(review["search_ready"])
    return evaluate_public_review(
        review.get("review"), PUBLIC_REVIEW_MIN_CHARS, PUBLIC_REVIEW_DETAIL_MIN_CHARS
    ).search_ready


def _review_content_hash(category: str, item_id: int, review_text: str | None) -> str:
    normalized = " ".join(str(review_text or "").split())
    return hashlib.sha256(f"{category}:{item_id}:{normalized}".encode("utf-8")).hexdigest()


def _current_state_hides_review(state: models.PublicReviewState | None, category: str, item) -> bool:
    return bool(
        state
        and state.suspended_at
        and state.content_hash == _review_content_hash(category, item.id, item.review)
    )


def _review_detail_url(review: dict) -> str:
    return f"/reviews/{review['id']}?category={review['category']}"


def _review_image(review: dict) -> str:
    return _safe_media_url(review.get("poster_url") or review.get("cover_art_url")) or "/static/default-avatar.svg"


def _safe_media_url(value):
    try:
        return schemas.validate_public_url(value)
    except ValueError:
        return None


def _absolute_url(path_or_url: str) -> str:
    if not path_or_url:
        return f"{SITE_URL}/omnitrackr_vortex.png"
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    return f"{SITE_URL}{path_or_url if path_or_url.startswith('/') else '/' + path_or_url}"


def _review_meta(review: dict) -> str:
    category = review.get("category")
    if category == "movie":
        return f"{review.get('director') or 'Unknown director'} - {review.get('year') or 'Unknown year'}"
    if category == "video_game":
        release_year = review.get("release_date", "")[:4] if review.get("release_date") else "Unknown year"
        return f"{review.get('genres') or 'Various genres'} - {release_year}"
    if category == "music":
        return f"{review.get('artist') or 'Unknown artist'} - {review.get('year') or 'Unknown year'}"
    if category == "book":
        return f"{review.get('author') or 'Unknown author'} - {review.get('year') or 'Unknown year'}"
    if category in {"tv_show", "anime"}:
        details = [str(review.get("year") or "Unknown year")]
        if review.get("seasons"):
            details.append(f"{review['seasons']} season{'s' if review['seasons'] != 1 else ''}")
        if review.get("episodes"):
            details.append(f"{review['episodes']} episode{'s' if review['episodes'] != 1 else ''}")
        return " - ".join(details)
    return ""


def _review_report_html(review: dict) -> str:
    return f"""
      <details class="review-report">
        <summary>Report this review</summary>
        <form data-review-report="true" data-category="{_escape(review['category'])}" data-review-id="{_escape(review['id'])}">
          <label>What is the issue?
            <select name="reason" required>
              <option value="">Choose a reason</option>
              <option value="spam">Spam or promotion</option>
              <option value="harassment">Harassment</option>
              <option value="personal_information">Personal information</option>
              <option value="copied_content">Copied content</option>
              <option value="other">Other safety issue</option>
            </select>
          </label>
          <button type="submit">Send report</button>
          <p class="review-report__status" aria-live="polite"></p>
        </form>
      </details>
    """


def _review_card_html(review: dict) -> str:
    standalone = _review_is_standalone(review)
    review_url = _review_detail_url(review)
    preview = (review.get("review") or "").strip()
    full_text = preview
    if len(preview) > 420:
        preview = f"{preview[:417].rstrip()}..."
    rating = review.get("rating")
    rating_html = f'<span class="review-rating">Rating: {_escape(rating)}/10</span>' if rating is not None else ""
    title = _escape(review.get("title"))
    if standalone:
        title = f'<a class="review-title-link" href="{_escape(review_url)}">{title}</a>'
    report_html = "" if standalone else _review_report_html(review)
    detail_link = f'<a class="review-detail-link" href="{_escape(review_url)}" aria-label="Read the full review of {_escape(review.get("title"))}">Read full review</a>' if standalone else ""
    expanded_text = (
        f'<details class="review-full-text"><summary>Read full review</summary><p>{_escape(full_text)}</p></details>'
        if not standalone and len(full_text) > 420 else ""
    )
    return f"""
      <article class="review-card{'' if standalone else ' review-card--summary'}" data-review-key="{_escape(review['category'])}:{review['id']}">
        <span class="review-category">{_escape(CATEGORY_LABELS.get(review["category"], review["category"]))}</span>
        <div class="review-card-header">
          <img src="{_escape(_review_image(review))}" alt="" loading="lazy" width="64" height="88" data-fallback-src="/static/default-avatar.svg" class="review-poster">
          <div class="review-card-title">
            <h3>{title}</h3>
            <p class="review-item-meta">{_escape(_review_meta(review))}</p>
          </div>
        </div>
        <p class="review-preview">{_escape(preview)}</p>
        {expanded_text}
        <div class="review-meta">
          <span class="review-author">By {_escape(review.get("username"))}</span>
          {rating_html}
        </div>
        <div class="review-card-actions">
          <a class="review-save-link" href="/reviews/{review['id']}/save?category={_escape(review['category'])}" aria-label="Save {_escape(review.get('title'))} to my library">Save to my library</a>
          {detail_link}
        </div>
        {report_html}
      </article>
    """


def _review_item_reviewed_json_ld(review: dict) -> dict:
    category = review.get("category")
    title = review.get("title")
    if category == "movie":
        item = {"@type": "Movie", "name": title}
        if review.get("director"):
            item["director"] = {"@type": "Person", "name": review["director"]}
        if review.get("year"):
            item["datePublished"] = str(review["year"])
        return item
    if category == "video_game":
        item = {"@type": "VideoGame", "name": title}
        if review.get("release_date"):
            item["datePublished"] = review["release_date"]
        if review.get("genres"):
            item["genre"] = review["genres"]
        return item
    if category == "music":
        item = {"@type": "MusicRecording", "name": title}
        if review.get("artist"):
            item["byArtist"] = {"@type": "MusicGroup", "name": review["artist"]}
        if review.get("year"):
            item["datePublished"] = str(review["year"])
        return item
    if category == "book":
        item = {"@type": "Book", "name": title}
        if review.get("author"):
            item["author"] = {"@type": "Person", "name": review["author"]}
        if review.get("year"):
            item["datePublished"] = str(review["year"])
        return item
    item = {"@type": "TVSeries", "name": title}
    if review.get("year"):
        item["datePublished"] = str(review["year"])
    if review.get("episodes"):
        item["numberOfEpisodes"] = review["episodes"]
    if review.get("seasons"):
        item["numberOfSeasons"] = review["seasons"]
    return item


def _reviews_item_list_json_ld(reviews: list[dict], category: Optional[str] = None) -> dict:
    normalized_category = _normalized_category(category)
    context = CATEGORY_REVIEW_CONTEXT.get(normalized_category or "")
    page_url = f"{SITE_URL}/reviews"
    if normalized_category:
        page_url = f"{page_url}?category={normalized_category}"
    name = context["title"] if context else "Public Media Reviews - OmniTrackr"
    description = context["description"] if context else "Public user reviews for movies, TV shows, anime, video games, music, and books."

    item_list = []
    search_ready_reviews = [review for review in reviews if _review_is_standalone(review)]
    for position, review in enumerate(search_ready_reviews, start=1):
        standalone = True
        review_url = f"{SITE_URL}{_review_detail_url(review)}"
        review_item = {
            "@type": "ListItem",
            "position": position,
            "item": {
                "@type": "Review",
                "name": f"{review.get('title')} {CATEGORY_LABELS.get(review.get('category'), 'Media')} Review",
                "author": {"@type": "Person", "name": review.get("username")},
                "reviewBody": review.get("review"),
                "itemReviewed": _review_item_reviewed_json_ld(review),
            },
        }
        if standalone:
            review_item["url"] = review_url
            review_item["item"]["url"] = review_url
        if review.get("rating") is not None:
            review_item["item"]["reviewRating"] = {
                "@type": "Rating",
                "ratingValue": _json_number(review["rating"]),
                "bestRating": 10,
                "worstRating": 1,
            }
        item_list.append(review_item)

    return {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": name,
        "description": description,
        "url": page_url,
        "dateModified": datetime.utcnow().strftime("%Y-%m-%d"),
        "inLanguage": "en-US",
        "isPartOf": {"@type": "WebSite", "name": "OmniTrackr", "url": SITE_URL},
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": len(item_list),
            "itemListElement": item_list,
        },
    }


def _inject_reviews_item_list_json_ld(page: str, reviews: list[dict], category: Optional[str] = None) -> str:
    json_ld = _safe_json_ld(_reviews_item_list_json_ld(reviews, category))
    script = f'<script type="application/ld+json" id="server-review-item-list">{json_ld}</script>'
    pattern = (
        r'\s*<script type="application/ld\+json">\s*\{\s*"@context": "https://schema\.org",\s*'
        r'"@type": "CollectionPage",\s*"name": "Public Reviews - OmniTrackr".*?'
        r'"itemListElement": \[\]\s*\}\s*\}\s*</script>'
    )
    updated_page, count = re.subn(pattern, lambda _: f"\n  {script}", page, count=1, flags=re.DOTALL)
    if count:
        return updated_page
    return page.replace("</head>", f"  {script}\n</head>", 1)


def _noindex_empty_review_category(page: str) -> str:
    page = page.replace(
        '<meta name="robots" content="index, follow, max-image-preview:large">',
        '<meta name="robots" content="noindex, follow">',
        1,
    )
    return page


def _inject_ad_loader_for_review_detail(page: str, request: Request) -> str:
    if request.cookies.get(AUTH_COOKIE_NAME):
        return page
    if "/static/ad-loader.js" in page or "</head>" not in page:
        return page
    return page.replace("</head>", '  <script src="/static/ad-loader.js" defer></script>\n</head>', 1)


def _not_found_review_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="robots" content="noindex, follow">
  <title>Review Not Found - OmniTrackr</title>
  <link rel="stylesheet" href="/styles.css?v=20260917-review-safety-v1">
  <style>
    body { min-height: 100vh; padding: 20px; }
    .review-wrapper { max-width: 900px; margin: 0 auto; }
    .review-container { background: var(--card-bg); border: 1px solid var(--border); border-radius: 16px; color: var(--fg); margin: 20px 0; padding: 40px; }
    .back-link { color: var(--primary); display: inline-block; font-weight: 500; margin-bottom: 20px; text-decoration: none; }
  </style>
</head>
<body class="dark-mode">
  <main class="review-wrapper">
    <a href="/reviews" class="back-link">Back to Reviews</a>
    <section class="review-container">
      <h1>Review not found</h1>
      <p>This review is unavailable, private, or no longer meets the public review quality threshold.</p>
    </section>
  </main>
</body>
</html>"""


def _review_detail_html(review: dict) -> str:
    category_label = CATEGORY_LABELS.get(review.get("category"), "Media")
    title = f"{review.get('title')} {category_label} Review by {review.get('username')} - OmniTrackr"
    review_excerpt = (review.get("review") or "").strip().replace("\n", " ")
    rating = review.get("rating")
    rating_text = f"{rating}/10 " if rating is not None else ""
    description = f"Read {review.get('username')}'s {rating_text}review of {review.get('title')} on OmniTrackr: {review_excerpt}"
    if len(description) > 158:
        description = f"{description[:155].rstrip()}..."
    canonical_url = f"{SITE_URL}/reviews/{review['id']}?category={review['category']}"
    image_url = _absolute_url(_review_image(review))
    rating_html = f'<div class="review-rating-large">Rating: {_escape(rating)}/10</div>' if rating is not None else ""

    detail_rows = []
    category = review.get("category")
    if category == "movie":
        detail_rows.extend([("Director", review.get("director") or "Unknown"), ("Year", review.get("year") or "N/A")])
        item_reviewed = {"@type": "Movie", "name": review.get("title")}
        if review.get("director"):
            item_reviewed["director"] = {"@type": "Person", "name": review["director"]}
    elif category == "video_game":
        detail_rows.extend([("Genres", review.get("genres") or "Various"), ("Release Date", review.get("release_date") or "N/A")])
        item_reviewed = {"@type": "VideoGame", "name": review.get("title")}
    elif category == "music":
        detail_rows.extend([("Artist", review.get("artist") or "Unknown"), ("Year", review.get("year") or "N/A")])
        item_reviewed = {"@type": "MusicRecording", "name": review.get("title")}
    elif category == "book":
        detail_rows.extend([("Author", review.get("author") or "Unknown"), ("Year", review.get("year") or "N/A")])
        item_reviewed = {"@type": "Book", "name": review.get("title")}
    else:
        detail_rows.append(("Year", review.get("year") or "N/A"))
        if review.get("seasons"):
            detail_rows.append(("Seasons", review.get("seasons")))
        if review.get("episodes"):
            detail_rows.append(("Episodes", review.get("episodes")))
        item_reviewed = {"@type": "TVSeries", "name": review.get("title")}

    details_html = "\n".join(f"<p><strong>{_escape(label)}:</strong> {_escape(value)}</p>" for label, value in detail_rows)
    json_ld = {
        "@context": "https://schema.org",
        "@type": "Review",
        "url": canonical_url,
        "headline": title,
        "reviewBody": review.get("review"),
        "author": {"@type": "Person", "name": review.get("username")},
        "itemReviewed": item_reviewed,
    }
    if rating is not None:
        json_ld["reviewRating"] = {"@type": "Rating", "ratingValue": rating, "bestRating": 10, "worstRating": 1}

    breadcrumb_json_ld = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Public Reviews", "item": f"{SITE_URL}/reviews"},
            {"@type": "ListItem", "position": 3, "name": f"{review.get('title')} Review", "item": canonical_url},
        ],
    }

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="google-adsense-account" content="{_escape(ADSENSE_ACCOUNT)}">
  <meta name="description" content="{_escape(description)}">
  <meta name="robots" content="index, follow, max-image-preview:large">
  <title>{_escape(title)}</title>
  <link rel="canonical" href="{_escape(canonical_url)}">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{_escape(canonical_url)}">
  <meta property="og:title" content="{_escape(title)}">
  <meta property="og:description" content="{_escape(description)}">
  <meta property="og:image" content="{_escape(image_url)}">
  <meta property="og:image:alt" content="{_escape(review.get("title"))} review artwork">
  <meta property="article:author" content="{_escape(review.get("username"))}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{_escape(title)}">
  <meta name="twitter:description" content="{_escape(description)}">
  <meta name="twitter:image" content="{_escape(image_url)}">
  <meta name="twitter:image:alt" content="{_escape(review.get("title"))} review artwork">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/styles.css?v=20260917-review-safety-v1">
  <style>
    body {{ min-height: 100vh; padding: 20px; }}
    .review-wrapper {{ max-width: 900px; margin: 0 auto; }}
    .review-container {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 16px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3); color: var(--fg); margin: 20px 0; padding: 40px; }}
    .review-header {{ border-bottom: 2px solid var(--border); display: flex; gap: 30px; margin-bottom: 30px; padding-bottom: 30px; }}
    .review-poster-large {{ border-radius: 12px; flex-shrink: 0; height: 225px; object-fit: cover; width: 150px; }}
    .review-header-info {{ flex: 1; }}
    .review-header-info h1 {{ color: var(--fg); font-size: 2rem; margin: 0 0 15px; }}
    .review-meta-info {{ color: var(--fg-secondary); line-height: 1.8; margin-bottom: 15px; }}
    .review-rating-large {{ color: var(--primary); font-size: 1.5rem; font-weight: 600; margin-bottom: 15px; }}
    .review-category-badge {{ background: var(--primary); border-radius: 16px; color: white; display: inline-block; font-size: 0.9rem; margin-bottom: 15px; padding: 6px 16px; }}
    .review-content {{ color: var(--fg); font-size: 1.1rem; line-height: 1.9; margin-bottom: 30px; white-space: pre-wrap; }}
    .review-author {{ border-top: 1px solid var(--border); color: var(--fg-secondary); padding-top: 20px; }}
    .back-link {{ color: var(--primary); display: inline-block; font-weight: 500; margin-bottom: 20px; text-decoration: none; }}
    .back-link:hover {{ text-decoration: underline; }}
    .review-save-link {{ display: inline-flex; align-items: center; justify-content: center; min-height: 44px; padding: 10px 18px; border-radius: 9px; background: var(--primary); color: white; text-decoration: none; font-weight: 600; }}
    .review-save-link:focus-visible {{ outline: 3px solid var(--fg); outline-offset: 4px; }}
    .review-save-note {{ color: var(--fg-secondary); margin-top: 10px; line-height: 1.6; }}
    @media (max-width: 768px) {{
      .review-header {{ flex-direction: column; }}
      .review-poster-large {{ height: auto; max-height: 400px; width: 100%; }}
      .review-container {{ padding: 25px; }}
    }}
  </style>
  <script type="application/ld+json">{_safe_json_ld(json_ld)}</script>
  <script type="application/ld+json">{_safe_json_ld(breadcrumb_json_ld)}</script>
  <script src="/static/review_report.js?v=20260917-review-safety-v1" defer></script>
</head>
<body class="dark-mode">
  <main class="review-wrapper">
    <a href="/reviews" class="back-link">Back to Reviews</a>
    <article class="review-container">
      <header class="review-header">
        <img src="{_escape(_review_image(review))}" alt="{_escape(review.get("title"))} poster" class="review-poster-large">
        <div class="review-header-info">
          <span class="review-category-badge">{_escape(CATEGORY_LABELS.get(category, category))}</span>
          <h1>{_escape(review.get("title"))}</h1>
          {rating_html}
          <div class="review-meta-info">{details_html}</div>
        </div>
      </header>
      <section class="review-content">{_escape(review.get("review"))}</section>
      <a class="review-save-link" href="/reviews/{review['id']}/save?category={_escape(category)}">Save to my library</a>
      <p class="review-save-note">Keep this title for later. Preview your library match before confirming.</p>
      <footer class="review-author">
        <p><strong>Review by:</strong> {_escape(review.get("username"))}</p>
      </footer>
      {_review_report_html(review)}
    </article>
  </main>
</body>
</html>"""


@router.get("/reviews")
def reviews_index(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None, description="Filter by category"),
    q: str = Query("", max_length=100, description="Search review titles"),
):
    """Serve the same first page used by the progressively enhanced directory."""
    if category and not _normalized_category(category):
        return strict_html_response(_not_found_reviews_category_html(), status_code=404)
    category = category or None
    q = q.strip()
    html_file = os.path.join(os.path.dirname(__file__), "..", "templates", "reviews.html")
    with open(html_file, "r", encoding="utf-8") as file:
        page = file.read()
    feed = _public_review_feed(db, category, q, 20, 0)
    reviews = feed["reviews"]
    if reviews:
        cards = "\n".join(_review_card_html(review) for review in reviews)
    elif q:
        cards = '<section class="no-reviews"><h2>No matching reviews yet</h2><p>Try another title or choose All Categories.</p></section>'
    else:
        cards = '<section class="no-reviews"><h2>Community reviews are being curated</h2><p>Thoughtful public reviews will appear here as members share them.</p></section>'
    replacements = {
        "SERVER_REVIEWS": cards, "CATEGORY": _escape(category or ""), "QUERY": _escape(q),
        "NEXT_OFFSET": str(feed["next_offset"]), "HAS_MORE": str(feed["has_more"]).lower(),
    }
    # One substitution pass keeps literal template tokens in user content inert.
    page = re.sub(r"\{\{(SERVER_REVIEWS|CATEGORY|QUERY|NEXT_OFFSET|HAS_MORE)\}\}", lambda match: replacements[match[1]], page)
    page = _inject_reviews_item_list_json_ld(page, reviews, category)
    page = _apply_category_review_context(page, category)
    noindex = bool(q) or not any(_review_is_standalone(review) for review in reviews)
    if noindex:
        page = _noindex_empty_review_category(page)
    response = strict_html_response(page)
    if noindex:
        response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


@router.get("/reviews/{review_id}")
async def review_detail(
    request: Request,
    review_id: int,
    category: Optional[str] = Query(None, description="Category: movie, tv_show, anime, video_game, music, or book"),
    db: Session = Depends(get_db)
):
    """Serve the public review detail page."""
    if category:
        try:
            review = await get_public_review(review_id=review_id, category=category, db=db)
            if not _review_is_standalone(review):
                return strict_html_response(_not_found_review_html(), status_code=404)
            return strict_html_response(_inject_ad_loader_for_review_detail(_review_detail_html(review), request))
        except HTTPException:
            return strict_html_response(_not_found_review_html(), status_code=404)

    html_file = os.path.join(os.path.dirname(__file__), "..", "templates", "review_detail.html")
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as file:
            return strict_html_response(file.read())
    raise HTTPException(status_code=404, detail="Review detail page not found")


def _active_user_ids_query(db: Session):
    return db.query(models.User.id).filter(models.User.is_active == True)


def _serialize_public_review(category, item, user, quality):
    review = {
        "id": item.id, "category": category, "title": item.title,
        "review": item.review, "rating": item.rating,
        "username": user.username, "user_id": user.id,
        "community_ready": quality.community_ready, "search_ready": quality.search_ready,
    }
    for field in PUBLIC_METADATA_FIELDS[category]:
        value = getattr(item, field)
        if field == "release_date" and value:
            value = value.isoformat()
        elif field in {"poster_url", "cover_art_url"}:
            value = _safe_media_url(value)
        review[field] = value
    return review


def _eligible_public_reviews(db, category, q, min_chars):
    """Stream joined rows; review quality and moderation run before pagination."""
    for cat, model in CATEGORY_MODELS.items():
        if category and cat != category:
            continue
        rows = db.query(model, models.User, models.PublicReviewState).join(
            models.User, model.user_id == models.User.id,
        ).outerjoin(models.PublicReviewState, and_(
            models.PublicReviewState.category == cat,
            models.PublicReviewState.item_id == model.id,
        )).filter(
            models.User.is_active == True,
            model.review_public == True,
            model.review.isnot(None),
            func.length(func.trim(model.review)) >= min_chars,
        )
        if q:
            rows = rows.filter(func.lower(model.title).contains(q.lower(), autoescape=True))
        for item, user, review_state in rows.yield_per(200):
            if not (item.title or "").strip():
                continue
            quality = evaluate_public_review(item.review, PUBLIC_REVIEW_MIN_CHARS, PUBLIC_REVIEW_DETAIL_MIN_CHARS)
            if not quality.safe or (min_chars >= PUBLIC_REVIEW_MIN_CHARS and not quality.community_ready):
                continue
            if _current_state_hides_review(review_state, cat, item):
                continue
            yield _serialize_public_review(cat, item, user, quality)


def _public_review_feed(db, category, q, limit, offset, min_chars=PUBLIC_REVIEW_MIN_CHARS):
    if category and category not in CATEGORY_MODELS:
        raise HTTPException(400, "Invalid category")
    # IDs overlap across media tables. Category is a deterministic final tie-breaker.
    # Keeping only this page's prefix bounds memory while evaluating every candidate.
    prefix = heapq.nsmallest(
        offset + limit + 1,
        _eligible_public_reviews(db, category, q.strip(), min_chars),
        key=lambda review: (not review["search_ready"], -review["id"], review["category"]),
    )
    reviews = prefix[offset:offset + limit]
    return {"reviews": reviews, "has_more": len(prefix) > offset + limit, "next_offset": offset + len(reviews)}


@router.get("/api/public/reviews", response_model=List[dict], tags=["public"])
def get_public_reviews(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    min_chars: int = Query(PUBLIC_REVIEW_MIN_CHARS, ge=1, le=2000),
    q: str = Query("", max_length=100),
):
    """Retain the existing array contract with complete, stable pagination."""
    return _public_review_feed(db, category, q, limit, offset, min_chars)["reviews"]


@router.get("/api/public/review-feed", response_model=dict, tags=["public"])
def get_public_review_feed(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None, description="Filter by category"),
    q: str = Query("", max_length=100),
    limit: int = Query(20, ge=1, le=40),
    offset: int = Query(0, ge=0),
):
    return _public_review_feed(db, category, q, limit, offset)


@router.get("/api/public/reviews/{review_id}", response_model=dict, tags=["public"])
async def get_public_review(
    review_id: int,
    category: str = Query(..., description="Category: movie, tv_show, anime, video_game, music, or book"),
    db: Session = Depends(get_db)
):
    """Get a specific public review by ID and category."""
    user_ids = _active_user_ids_query(db)

    def base_filter(model_cls):
        return and_(
            model_cls.id == review_id,
            model_cls.review.isnot(None),
            model_cls.review != "",
            model_cls.review_public == True,
            model_cls.user_id.in_(user_ids)
        )

    model_cls = CATEGORY_MODELS.get(category)
    if not model_cls:
        raise HTTPException(status_code=400, detail="Invalid category")
    item = db.query(model_cls).filter(base_filter(model_cls)).first()

    if not item:
        raise HTTPException(status_code=404, detail="Review not found")
    quality = evaluate_public_review(item.review, PUBLIC_REVIEW_MIN_CHARS, PUBLIC_REVIEW_DETAIL_MIN_CHARS)
    if not quality.safe:
        raise HTTPException(status_code=404, detail="Review not found")
    state = db.query(models.PublicReviewState).filter(
        models.PublicReviewState.category == category,
        models.PublicReviewState.item_id == item.id,
    ).first()
    if _current_state_hides_review(state, category, item):
        raise HTTPException(status_code=404, detail="Review not found")

    user = db.query(models.User).filter(models.User.id == item.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="Review not found")

    return _serialize_public_review(category, item, user, quality)


def _saveable_review(db, review_id, category, *, lock=False):
    model = CATEGORY_MODELS.get(category)
    if model is None:
        raise HTTPException(400, "Invalid category", headers={"Cache-Control": "private, no-store"})
    query = db.query(model, models.User, models.PublicReviewState).join(
        models.User, model.user_id == models.User.id,
    ).outerjoin(models.PublicReviewState, and_(
        models.PublicReviewState.category == category,
        models.PublicReviewState.item_id == model.id,
    )).filter(model.id == review_id, model.review_public == True, models.User.is_active == True)
    if lock:
        query = query.with_for_update(of=model)
    row = query.populate_existing().first()
    if row:
        item, user, review_state = row
        quality = evaluate_public_review(item.review, PUBLIC_REVIEW_MIN_CHARS, PUBLIC_REVIEW_DETAIL_MIN_CHARS)
        if quality.community_ready and not _current_state_hides_review(review_state, category, item) and (item.title or "").strip():
            return _serialize_public_review(category, item, user, quality)
    raise HTTPException(404, "Review not found", headers={"Cache-Control": "private, no-store"})


def _review_save_metadata(review):
    return {"title": review["title"], **{field: review.get(field) for field in PUBLIC_METADATA_FIELDS[review["category"]]}}


def _review_save_version(review):
    payload = {"category": review["category"], "id": review["id"], "metadata": _review_save_metadata(review)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _existing_review_title(db, user_id, review):
    model = CATEGORY_MODELS[review["category"]]
    # Keep matching deliberately conservative. A match is opened, never overwritten.
    return db.query(model).filter(
        model.user_id == user_id,
        func.lower(func.trim(model.title)) == review["title"].strip().lower(),
    ).order_by(model.id).first()


@router.get("/reviews/{review_id}/save")
def review_save_page(
    review_id: int, category: str = Query(...), db: Session = Depends(get_db),
):
    try:
        review = _saveable_review(db, review_id, category)
    except HTTPException:
        response = strict_html_response(_not_found_review_html(), status_code=404)
    else:
        path = f"/reviews/{review_id}/save?category={category}"
        filename = os.path.join(os.path.dirname(__file__), "..", "templates", "review_save.html")
        with open(filename, "r", encoding="utf-8") as template:
            page = template.read()
        values = {
            "TITLE": f"Save {review['title']} - OmniTrackr", "CATEGORY": category,
            "CATEGORY_LABEL": CATEGORY_LABELS[category], "REVIEW_ID": review_id,
            "SOURCE_TITLE": review["title"],
            "REVIEW_URL": _review_detail_url(review) if review["search_ready"] else f"/reviews?category={category}",
            "SIGNIN_URL": "/?next=" + quote(path, safe="") + "#landing-auth",
        }
        page = re.sub(r"\{\{([A-Z_]+)\}\}", lambda match: _escape(values[match[1]]) if match[1] in values else match[0], page)
        response = strict_html_response(page)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


@router.get("/api/public/reviews/{review_id}/save-preview")
def review_save_preview(
    review_id: int, response: Response, category: str = Query(...),
    user=Depends(get_current_user), db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "private, no-store"
    review = _saveable_review(db, review_id, category)
    existing = _existing_review_title(db, user.id, review)
    return {
        "title": review["title"], "category": category,
        "library_category": LIBRARY_CATEGORIES[category], "version": _review_save_version(review),
        "existing": existing is not None, "item_id": existing.id if existing else None,
    }


class ReviewSaveSelection(BaseModel):
    version: str = Field(pattern=r"^[a-f0-9]{64}$")


@router.post("/api/public/reviews/{review_id}/save")
def save_review_title(
    review_id: int, selection: ReviewSaveSelection, response: Response,
    category: str = Query(...), user=Depends(get_current_user), db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "private, no-store"
    # Match Discover's lock so simultaneous saves and retries serialize per account.
    db.query(models.User).filter(models.User.id == user.id).with_for_update().first()
    try:
        review = _saveable_review(db, review_id, category, lock=True)
        if selection.version != _review_save_version(review):
            raise HTTPException(409, "This title changed. Preview it again before saving.", headers={"Cache-Control": "private, no-store"})
        item = _existing_review_title(db, user.id, review)
        created = item is None
        if created:
            metadata = _review_save_metadata(review)
            if category == "video_game" and metadata.get("release_date"):
                metadata["release_date"] = datetime.fromisoformat(metadata["release_date"])
            item = CATEGORY_MODELS[category](user_id=user.id, rating=None, review=None, review_public=False, **metadata)
            db.add(item)
            db.flush()
        result = {"created": created, "reused": not created, "item_id": item.id, "category": LIBRARY_CATEGORIES[category], "title": item.title}
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.post(
    "/api/public/reviews/{category}/{review_id}/report",
    status_code=status.HTTP_201_CREATED,
    tags=["public"],
)
async def report_public_review(
    category: str,
    review_id: int,
    payload: schemas.PublicReviewReportCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Record one signed-browser report and automatically unlist at the threshold."""
    model_cls = CATEGORY_MODELS.get(category)
    if not model_cls:
        raise HTTPException(status_code=400, detail="Invalid category")
    item = db.query(model_cls).join(models.User, model_cls.user_id == models.User.id).filter(
        model_cls.id == review_id,
        model_cls.review_public == True,
        model_cls.review.isnot(None),
        models.User.is_active == True,
    ).first()
    quality = evaluate_public_review(
        item.review if item else None, PUBLIC_REVIEW_MIN_CHARS, PUBLIC_REVIEW_DETAIL_MIN_CHARS
    )
    if not item or not quality.community_ready:
        raise HTTPException(status_code=404, detail="Review not found")

    current_hash = _review_content_hash(category, item.id, item.review)
    visitor_hash, visitor_token, _ = visitor_identity(request)
    duplicate = False
    newly_unlisted = False
    try:
        state_row = db.query(models.PublicReviewState).filter(
            models.PublicReviewState.category == category,
            models.PublicReviewState.item_id == item.id,
        ).first()
        if state_row and state_row.content_hash == current_hash and state_row.suspended_at:
            raise HTTPException(status_code=404, detail="Review not found")
        if not state_row:
            state_row = models.PublicReviewState(
                user_id=item.user_id,
                category=category,
                item_id=item.id,
                content_hash=current_hash,
                report_count=0,
            )
            db.add(state_row)
            db.flush()
        elif state_row.content_hash != current_hash:
            db.query(models.PublicReviewReport).filter(
                models.PublicReviewReport.state_id == state_row.id
            ).delete(synchronize_session=False)
            state_row.user_id = item.user_id
            state_row.content_hash = current_hash
            state_row.report_count = 0
            state_row.suspended_at = None

        existing = db.query(models.PublicReviewReport.id).filter(
            models.PublicReviewReport.state_id == state_row.id,
            models.PublicReviewReport.visitor_hash == visitor_hash,
        ).first()
        duplicate = bool(existing)
        if not duplicate:
            db.add(models.PublicReviewReport(
                state_id=state_row.id,
                visitor_hash=visitor_hash,
                reason=payload.reason,
            ))
            db.flush()
            db.query(models.PublicReviewState).filter(
                models.PublicReviewState.id == state_row.id,
                models.PublicReviewState.content_hash == current_hash,
            ).update(
                {models.PublicReviewState.report_count: models.PublicReviewState.report_count + 1},
                synchronize_session=False,
            )
            db.flush()
            db.refresh(state_row)
            if state_row.report_count >= PUBLIC_REVIEW_REPORT_THRESHOLD and not state_row.suspended_at:
                state_row.suspended_at = datetime.utcnow()
                newly_unlisted = True
                db.add(models.Notification(
                    user_id=item.user_id,
                    type="review_unlisted",
                    message=(
                        f'Your public review of "{item.title}" was automatically unlisted after '
                        "reports from multiple independent visitors. Edit the review to publish a revised version."
                    ),
                ))
        db.commit()
    except IntegrityError:
        db.rollback()
        duplicate = True
        current_state = db.query(models.PublicReviewState).filter(
            models.PublicReviewState.category == category,
            models.PublicReviewState.item_id == item.id,
        ).first()
        newly_unlisted = _current_state_hides_review(current_state, category, item)

    visibility = "unlisted" if newly_unlisted else "visible"
    response = JSONResponse(
        {"reported": True, "duplicate": duplicate, "visibility": visibility},
        status_code=status.HTTP_201_CREATED,
    )
    response.headers["Cache-Control"] = "no-store"
    set_visitor_cookie(response, visitor_token)
    return response
