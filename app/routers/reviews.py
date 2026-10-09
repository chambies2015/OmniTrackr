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

from .. import affiliate, models, schemas
from ..site_chrome import apply_site_chrome, editorial_picks, message_page
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..review_quality import AD_MIN_REVIEW_WORDS, MIN_INDEXED_LISTING_REVIEWS, evaluate_public_review, word_count
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
    return message_page(
        "Review Category Not Found", "Review category not found",
        "This review category is unavailable. Browse the public reviews directory to find movies, TV shows, anime, games, music, and books with substantial public review text.",
        eyebrow="Public reviews", actions=(("Browse public reviews", "/reviews"), ("Go to the homepage", "/")),
    )


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
    return _safe_media_url(review.get("poster_url") or review.get("cover_art_url")) or "/static/poster-placeholder.svg"


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


def _review_affiliate_html(review: dict) -> str:
    """Optional, clearly labelled shopping link; empty unless an affiliate tag is configured."""
    category = review.get("category") or ""
    creator = review.get("author") or review.get("artist") or review.get("director") or ""
    links = affiliate.links_html(category, review.get("title") or "", creator, css_class="review-affiliate-links")
    if not links:
        return ""
    return f'<div class="review-affiliate">{links}{affiliate.disclosure_html("review-affiliate-disclosure")}</div>'


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
          <img src="{_escape(_review_image(review))}" alt="" loading="lazy" width="64" height="88" data-fallback-src="/static/poster-placeholder.svg" class="review-poster">
          <div class="review-card-title">
            <h3>{title}</h3>
            <p class="review-item-meta">{_escape(_review_meta(review))}</p>
          </div>
        </div>
        <p class="review-preview">{_escape(preview)}</p>
        {expanded_text}
        <div class="review-meta">
          <span class="review-author">By {_author_html(review)}</span>
          {rating_html}
        </div>
        <div class="review-card-actions">
          <a class="review-save-link" rel="nofollow" href="/reviews/{review['id']}/save?category={_escape(review['category'])}" aria-label="Save {_escape(review.get('title'))} to my library">Save to my library</a>
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
    opening_tag = '<script type="application/ld+json" id="server-review-item-list">'
    script = f'{opening_tag}{json_ld}</script>'
    # Locate the template's dedicated block without backtracking over user content.
    start = page.find(opening_tag)
    if start != -1:
        end = page.find("</script>", start + len(opening_tag))
        if end != -1:
            return page[:start] + script + page[end + len("</script>"):]
    return page.replace("</head>", f"  {script}\n</head>", 1)


def _noindex_empty_review_category(page: str) -> str:
    page = page.replace(
        '<meta name="robots" content="index, follow, max-image-preview:large">',
        '<meta name="robots" content="noindex, follow">',
        1,
    )
    return page


def _inject_ad_loader_for_review_detail(page: str, request: Request, review: dict | None = None) -> str:
    if request.cookies.get(AUTH_COOKIE_NAME):
        return page
    if review is not None and word_count(review.get("review")) < AD_MIN_REVIEW_WORDS:
        return page
    if "/static/ad-loader.js" in page or "</head>" not in page:
        return page
    return page.replace("</head>", '  <script src="/static/ad-loader.js" defer></script>\n</head>', 1)


def _not_found_review_html() -> str:
    return message_page(
        "Review Not Found", "Review not found",
        "This review is unavailable, private, or no longer meets the public review quality threshold.",
        eyebrow="Public reviews", actions=(("Browse public reviews", "/reviews"), ("Go to the homepage", "/")),
    )


def _author_html(review: dict) -> str:
    """The reviewer's name, linked to their public profile when they have switched one on."""
    name = _escape(review.get("username"))
    url = review.get("profile_url")
    if isinstance(url, str) and url.startswith("/u/"):
        name = f'<a class="review-author-link" href="{_escape(url)}">{name}</a>'
    from ..supporters import chip_html
    return name + chip_html(review.get("supporter"))


def _attach_supporter_badges(db: Session, reviews: list) -> None:
    """Mark reviews by current Ko-fi supporters who show their badge. Optional: never blocks a page."""
    try:
        from ..supporters import public_badges
        badges = public_badges(db, [review.get("user_id") for review in reviews])
    except Exception:
        return
    for review in reviews:
        review["supporter"] = badges.get(review.get("user_id"))


def _attach_profile_urls(db: Session, reviews: list) -> None:
    try:
        from ..public_profiles import enabled_profile_paths
        paths = enabled_profile_paths(db, [review.get("user_id") for review in reviews])
    except Exception:
        return
    for review in reviews:
        if review.get("user_id") in paths:
            review["profile_url"] = paths[review["user_id"]]


def _title_page_link(review: dict) -> str:
    from ..title_pages import path_for_review_category
    path = path_for_review_category(review.get("category"), review.get("title") or "", review.get("year"), review.get("release_date"))
    if not path:
        return ""
    return f'<p class="review-title-link"><a href="{_escape(path)}">Trailer, details and more reviews of {_escape(review.get("title"))} <span aria-hidden="true">→</span></a></p>'


def _review_detail_html(review: dict, more_reviews: Optional[list] = None, helpful_count: int = 0) -> str:
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

    details_html = "\n".join(f"<p><span>{_escape(label)}</span> {_escape(value)}</p>" for label, value in detail_rows)
    more_html = ""
    if more_reviews:
        cards = "\n".join(_review_card_html(item) for item in more_reviews)
        label = CATEGORY_LABELS.get(category, "")
        more_html = (
            '<section class="review-more site-wrap" aria-labelledby="review-more-title">'
            f'<div class="review-more__head"><h2 id="review-more-title">More {_escape(label.lower())} reviews</h2>'
            f'<a href="/reviews?category={_escape(category)}">See all <span aria-hidden="true">→</span></a></div>'
            f'<div class="reviews-grid">{cards}</div></section>'
        )
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
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">
  <link rel="stylesheet" href="/static/public-legacy.css?v=20261004-legacy-1">
  <link rel="stylesheet" href="/static/reviews.css?v=20261002-profiles-1">
  <link rel="stylesheet" href="/static/review-detail.css?v=20261007-helpful-1">
  <script type="application/ld+json">{_safe_json_ld(json_ld)}</script>
  <script type="application/ld+json">{_safe_json_ld(breadcrumb_json_ld)}</script>
  <script src="/static/review_report.js?v=20261007-helpful-1" defer></script>
  <script src="/static/share.js?v=20261004-share-1" defer></script>
</head>
<body class="dark-mode site review-page">
  <!--SITE_NAV:reviews-->
  <main>
    <article class="review-article">
      <header class="review-hero">
        <div class="review-hero__backdrop" aria-hidden="true"><img src="{_escape(_review_image(review))}" alt=""></div>
        <div class="site-wrap review-hero__grid">
          <img src="{_escape(_review_image(review))}" alt="{_escape(review.get("title"))} poster" class="review-poster-large">
          <div class="review-header-info">
            <nav class="review-crumbs" aria-label="Breadcrumb"><a href="/reviews">Public reviews</a><span aria-hidden="true">/</span><a href="/reviews?category={_escape(category)}">{_escape(CATEGORY_LABELS.get(category, category))}</a></nav>
            <h1>{_escape(review.get("title"))}</h1>
            {_title_page_link(review)}
            <div class="review-hero__meta">{rating_html}<span class="review-byline">Reviewed by <strong>{_author_html(review)}</strong></span><button type="button" class="site-btn site-btn--ghost site-btn--sm review-share" data-share data-share-title="{_escape(review.get("title"))} review on OmniTrackr">Share</button></div>
            <div class="review-meta-info">{details_html}</div>
          </div>
        </div>
      </header>
      <div class="site-wrap review-body">
        <div class="review-main">
          <section class="review-content" aria-label="Review">{_escape(review.get("review"))}</section>
          {_helpful_html(review, helpful_count)}
        </div>
        <aside class="review-aside" aria-label="Keep this title">
          <p class="site-eyebrow">Sounds like your kind of thing?</p>
          <h2>Keep it for later</h2>
          <p class="review-save-note">Save it to your own private library. You preview any existing match before confirming.</p>
          <a class="review-save-link site-btn site-btn--primary" rel="nofollow" href="/reviews/{review['id']}/save?category={_escape(category)}">Save to my library</a>
          {_review_affiliate_html(review)}
          {_review_report_html(review)}
        </aside>
      </div>
    </article>
    {more_html}
  </main>
  <!--SITE_FOOTER-->
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
        page = apply_site_chrome(file.read())
    if category:
        chip = f'<a href="/reviews?category={_normalized_category(category)}">'
        page = page.replace(chip, chip[:-1] + ' aria-current="page">', 1)
    feed = _public_review_feed(db, category, q, 20, 0)
    reviews = feed["reviews"]
    _attach_profile_urls(db, reviews)
    if reviews:
        cards = "\n".join(_review_card_html(review) for review in reviews)
    elif q:
        cards = '<section class="no-reviews"><h2>No matching reviews yet</h2><p>Try another title or choose All Categories.</p></section>'
    else:
        cards = editorial_picks(
            "Start with an editorial guide",
            "No member has shared a public review in this section yet. These OmniTrackr guides compare films, "
            "series, anime, games, albums, and books, and explain who each pick suits.",
        )
    replacements = {
        "SERVER_REVIEWS": cards, "CATEGORY": _escape(category or ""), "QUERY": _escape(q),
        "NEXT_OFFSET": str(feed["next_offset"]), "HAS_MORE": str(feed["has_more"]).lower(),
    }
    # One substitution pass keeps literal template tokens in user content inert.
    page = re.sub(r"\{\{(SERVER_REVIEWS|CATEGORY|QUERY|NEXT_OFFSET|HAS_MORE)\}\}", lambda match: replacements[match[1]], page)
    page = _inject_reviews_item_list_json_ld(page, reviews, category)
    page = _apply_category_review_context(page, category)
    standalone = sum(1 for review in reviews if _review_is_standalone(review))
    noindex = bool(q) or standalone < MIN_INDEXED_LISTING_REVIEWS
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
            more = []
            try:
                feed = _public_review_feed(db, review["category"], "", 7, 0)["reviews"]
                more = [item for item in feed if item["id"] != review["id"]][:4]
            except Exception:
                more = []  # Related reviews are optional; never block the page.
            _attach_profile_urls(db, [review])
            _attach_supporter_badges(db, [review])
            helpful = review_helpful_counts(db, [(review["category"], review["id"])]).get((review["category"], int(review["id"])), 0)
            page = apply_site_chrome(_review_detail_html(review, more, helpful))
            return strict_html_response(_inject_ad_loader_for_review_detail(page, request, review))
        except HTTPException:
            return strict_html_response(_not_found_review_html(), status_code=404)

    html_file = os.path.join(os.path.dirname(__file__), "..", "templates", "review_detail.html")
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as file:
            return strict_html_response(apply_site_chrome(file.read()))
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
    _attach_supporter_badges(db, reviews)
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
            page = apply_site_chrome(template.read())
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


# ---------------------------------------------------------------- "Helpful" marks (Oct 2026)

HELPFUL_MILESTONES = (1, 3, 10, 25, 50, 100, 250, 500, 1000)


def review_helpful_counts(db: Session, keys) -> dict:
    """{(category, item_id): count} for the given reviews, in one query."""
    keys = [(category, int(item_id)) for category, item_id in keys]
    if not keys:
        return {}
    ids_by_category: dict = {}
    for category, item_id in keys:
        ids_by_category.setdefault(category, set()).add(item_id)
    counts = {}
    table = models.ReviewReaction
    for category, ids in ids_by_category.items():
        rows = db.query(table.item_id, func.count(table.id)).filter(
            table.category == category, table.item_id.in_(sorted(ids))).group_by(table.item_id).all()
        counts.update({(category, item_id): int(count) for item_id, count in rows})
    return counts


def _helpful_label(count: int) -> str:
    if count <= 0:
        return "Be the first to mark this helpful"
    return "1 person found this helpful" if count == 1 else f"{count} people found this helpful"


def _helpful_html(review: dict, count: int) -> str:
    return (
        f'<div class="review-helpful" data-review-helpful data-category="{_escape(review["category"])}" '
        f'data-review-id="{_escape(review["id"])}">'
        '<button type="button" class="site-btn site-btn--ghost site-btn--sm review-helpful__button" '
        'aria-pressed="false">👍 Helpful</button>'
        f'<span class="review-helpful__count" aria-live="polite">{_escape(_helpful_label(count))}</span></div>'
    )


def _signed_in_user_id(request: Request) -> Optional[int]:
    from ..auth import decode_access_token
    token = request.cookies.get(AUTH_COOKIE_NAME)
    payload = decode_access_token(token) if token else None
    uid = payload.get("uid") if isinstance(payload, dict) else None
    return uid if isinstance(uid, int) else None


@router.post("/api/public/reviews/{category}/{review_id}/helpful", include_in_schema=False)
async def mark_review_helpful(category: str, review_id: int, request: Request, db: Session = Depends(get_db)):
    """One mark per browser; the writer hears about it at milestones, never per click."""
    model_cls = CATEGORY_MODELS.get(category)
    if not model_cls:
        raise HTTPException(status_code=400, detail="Invalid category")
    item = db.query(model_cls).join(models.User, model_cls.user_id == models.User.id).filter(
        model_cls.id == review_id,
        model_cls.review_public == True,  # noqa: E712
        model_cls.review.isnot(None),
        models.User.is_active == True,  # noqa: E712
    ).first()
    quality = evaluate_public_review(item.review if item else None, PUBLIC_REVIEW_MIN_CHARS, PUBLIC_REVIEW_DETAIL_MIN_CHARS)
    if not item or not quality.community_ready:
        raise HTTPException(status_code=404, detail="Review not found")
    state_row = db.query(models.PublicReviewState).filter(
        models.PublicReviewState.category == category, models.PublicReviewState.item_id == item.id).first()
    if _current_state_hides_review(state_row, category, item):
        raise HTTPException(status_code=404, detail="Review not found")
    if _signed_in_user_id(request) == item.user_id:
        raise HTTPException(status_code=403, detail="You can't mark your own review as helpful.")

    visitor_hash, visitor_token, _ = visitor_identity(request)
    table = models.ReviewReaction
    already = db.query(table.id).filter(table.category == category, table.item_id == item.id,
                                        table.visitor_hash == visitor_hash).first()
    if not already:
        db.add(table(category=category, item_id=item.id, visitor_hash=visitor_hash))
        try:
            db.flush()
            count = review_helpful_counts(db, [(category, item.id)]).get((category, item.id), 0)
            if count in HELPFUL_MILESTONES:
                who = "Someone" if count == 1 else f"{count} people"
                verb = "found" if count == 1 else "have found"
                db.add(models.Notification(
                    user_id=item.user_id, type="review_helpful",
                    message=f'{who} {verb} your review of "{item.title}" helpful. Thanks for writing it!',
                ))
            db.commit()
        except IntegrityError:
            db.rollback()
    count = review_helpful_counts(db, [(category, item.id)]).get((category, item.id), 0)
    response = JSONResponse({"helpful": True, "count": count, "label": _helpful_label(count)})
    response.headers["Cache-Control"] = "no-store"
    set_visitor_cookie(response, visitor_token)
    return response


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
