"""
Public review endpoints for the OmniTrackr API.
"""
import html
import json
import os
import re
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from .. import models, schemas
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_db
from ..review_quality import is_public_review_safe

router = APIRouter(tags=["reviews"])

SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
PUBLIC_REVIEW_MIN_CHARS = int(os.getenv("PUBLIC_REVIEW_MIN_CHARS", "80"))
PUBLIC_REVIEW_DETAIL_MIN_CHARS = int(os.getenv("PUBLIC_REVIEW_DETAIL_MIN_CHARS", "240"))
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
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


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
  <link rel="stylesheet" href="/styles.css">
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
        "Discover thoughtful reviews and insights from the OmniTrackr community. Explore reviews for movies, TV shows, anime, video games, music, and books shared by our users.",
        _escape(context["intro"]),
        1,
    )
    page = page.replace(f'<option value="{category}">', f'<option value="{category}" selected>', 1)
    return page


def _review_is_substantial(review: dict) -> bool:
    review_text = (review.get("review") or "").strip()
    return len(review_text) >= PUBLIC_REVIEW_MIN_CHARS and is_public_review_safe(review_text)


def _review_is_standalone(review: dict) -> bool:
    review_text = (review.get("review") or "").strip()
    return len(review_text) >= PUBLIC_REVIEW_DETAIL_MIN_CHARS and is_public_review_safe(review_text)


def _review_detail_url(review: dict) -> str:
    return f"/reviews/{review['id']}?category={review['category']}"


def _review_image(review: dict) -> str:
    return review.get("poster_url") or review.get("cover_art_url") or "/static/default-avatar.svg"


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


def _review_card_html(review: dict) -> str:
    standalone = _review_is_standalone(review)
    review_url = _review_detail_url(review)
    preview = (review.get("review") or "").strip()
    if len(preview) > 260:
        preview = f"{preview[:257].rstrip()}..."
    rating = review.get("rating")
    rating_html = f'<span class="review-rating">Rating: {_escape(rating)}/10</span>' if rating is not None else ""
    tag_open = f'<a class="review-card" href="{_escape(review_url)}">' if standalone else '<article class="review-card review-card--summary">'
    tag_close = "</a>" if standalone else "</article>"
    return f"""
      {tag_open}
        <span class="review-category">{_escape(CATEGORY_LABELS.get(review["category"], review["category"]))}</span>
        <div class="review-card-header">
          <img src="{_escape(_review_image(review))}" alt="{_escape(review.get("title"))} poster" class="review-poster">
          <div class="review-card-title">
            <h3>{_escape(review.get("title"))}</h3>
            <p>{_escape(_review_meta(review))}</p>
          </div>
        </div>
        <p class="review-preview">{_escape(preview)}</p>
        <div class="review-meta">
          <span>By {_escape(review.get("username"))}</span>
          {rating_html}
        </div>
      {tag_close}
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
    for position, review in enumerate(reviews, start=1):
        standalone = _review_is_standalone(review)
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
    updated_page, count = re.subn(pattern, f"\n  {script}", page, count=1, flags=re.DOTALL)
    if count:
        return updated_page
    return page.replace("</head>", f"  {script}\n</head>", 1)


def _remove_ad_loader_for_authenticated_request(page: str, request: Request) -> str:
    if request.cookies.get(AUTH_COOKIE_NAME):
        return page.replace('  <script src="/static/ad-loader.js" defer></script>\n', "")
    return page


def _remove_public_ad_loader(page: str) -> str:
    return page.replace('  <script src="/static/ad-loader.js" defer></script>\n', "")


def _noindex_empty_review_category(page: str) -> str:
    page = page.replace(
        '<meta name="robots" content="index, follow, max-image-preview:large">',
        '<meta name="robots" content="noindex, follow">',
        1,
    )
    return _remove_public_ad_loader(page)


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
  <link rel="stylesheet" href="/styles.css">
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
  <link rel="stylesheet" href="/styles.css">
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
    @media (max-width: 768px) {{
      .review-header {{ flex-direction: column; }}
      .review-poster-large {{ height: auto; max-height: 400px; width: 100%; }}
      .review-container {{ padding: 25px; }}
    }}
  </style>
  <script type="application/ld+json">{_safe_json_ld(json_ld)}</script>
  <script type="application/ld+json">{_safe_json_ld(breadcrumb_json_ld)}</script>
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
      <footer class="review-author">
        <p><strong>Review by:</strong> {_escape(review.get("username"))}</p>
      </footer>
    </article>
  </main>
</body>
</html>"""


@router.get("/reviews")
async def reviews_index(
    request: Request,
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None, description="Filter by category")
):
    """Serve the public reviews index page."""
    if category is not None and not _normalized_category(category):
        return strict_html_response(_not_found_reviews_category_html(), status_code=404)

    html_file = os.path.join(os.path.dirname(__file__), "..", "templates", "reviews.html")
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as file:
            page = file.read()
        substantial_reviews = []
        try:
            reviews = await get_public_reviews(
                db=db,
                category=category,
                limit=100,
                offset=0,
                min_chars=PUBLIC_REVIEW_MIN_CHARS,
            )
            substantial_reviews = [review for review in reviews if _review_is_substantial(review)][:20]
            if substantial_reviews:
                server_reviews_html = "\n".join(_review_card_html(review) for review in substantial_reviews)
            else:
                server_reviews_html = """
      <section class="no-reviews">
        <h2>Community reviews are being curated</h2>
        <p>OmniTrackr publishes user reviews that include enough context to help other readers decide what to watch, play, hear, or read next. Check back as more detailed public reviews are shared.</p>
      </section>
                """
            page = re.sub(
                r'<div id="reviewsContainer" class="reviews-grid">\s*<div class="loading">Loading reviews\.\.\.</div>\s*</div>',
                f'<div id="reviewsContainer" class="reviews-grid">\n{server_reviews_html}\n    </div>',
                page,
                count=1,
            )
            page = _inject_reviews_item_list_json_ld(page, substantial_reviews, category)
        except Exception:
            pass
        page = _apply_category_review_context(page, category)
        if _normalized_category(category) and not substantial_reviews:
            page = _noindex_empty_review_category(page)
        page = _remove_ad_loader_for_authenticated_request(page, request)
        return strict_html_response(page)
    raise HTTPException(status_code=404, detail="Reviews page not found")


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


@router.get("/api/public/reviews", response_model=List[dict], tags=["public"])
async def get_public_reviews(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None, description="Filter by category: movie, tv_show, anime, video_game, music, book"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of reviews to return"),
    offset: int = Query(0, ge=0, description="Number of reviews to skip"),
    min_chars: int = Query(PUBLIC_REVIEW_MIN_CHARS, ge=1, le=2000, description="Minimum trimmed review length")
):
    """Get public reviews from all users. Defaults to substantial review text for public discovery quality."""
    reviews = []
    user_ids = _active_user_ids_query(db)

    def base_filter(model_cls):
        return and_(
            model_cls.review.isnot(None),
            model_cls.review != "",
            model_cls.review_public == True,
            func.length(func.trim(model_cls.review)) >= min_chars,
            model_cls.user_id.in_(user_ids)
        )

    if category == "movie":
        query_conditions = [("movie", db.query(models.Movie).filter(base_filter(models.Movie)).order_by(models.Movie.id.desc()).offset(offset).limit(limit).all())]
    elif category == "tv_show":
        query_conditions = [("tv_show", db.query(models.TVShow).filter(base_filter(models.TVShow)).order_by(models.TVShow.id.desc()).offset(offset).limit(limit).all())]
    elif category == "anime":
        query_conditions = [("anime", db.query(models.Anime).filter(base_filter(models.Anime)).order_by(models.Anime.id.desc()).offset(offset).limit(limit).all())]
    elif category == "video_game":
        query_conditions = [("video_game", db.query(models.VideoGame).filter(base_filter(models.VideoGame)).order_by(models.VideoGame.id.desc()).offset(offset).limit(limit).all())]
    elif category == "music":
        query_conditions = [("music", db.query(models.Music).filter(base_filter(models.Music)).order_by(models.Music.id.desc()).offset(offset).limit(limit).all())]
    elif category == "book":
        query_conditions = [("book", db.query(models.Book).filter(base_filter(models.Book)).order_by(models.Book.id.desc()).offset(offset).limit(limit).all())]
    else:
        per_cat = (offset + limit) // 6 + 2
        query_conditions = [
            ("movie", db.query(models.Movie).filter(base_filter(models.Movie)).order_by(models.Movie.id.desc()).limit(per_cat).all()),
            ("tv_show", db.query(models.TVShow).filter(base_filter(models.TVShow)).order_by(models.TVShow.id.desc()).limit(per_cat).all()),
            ("anime", db.query(models.Anime).filter(base_filter(models.Anime)).order_by(models.Anime.id.desc()).limit(per_cat).all()),
            ("video_game", db.query(models.VideoGame).filter(base_filter(models.VideoGame)).order_by(models.VideoGame.id.desc()).limit(per_cat).all()),
            ("music", db.query(models.Music).filter(base_filter(models.Music)).order_by(models.Music.id.desc()).limit(per_cat).all()),
            ("book", db.query(models.Book).filter(base_filter(models.Book)).order_by(models.Book.id.desc()).limit(per_cat).all()),
        ]

    for cat, items in query_conditions:
        for item in items:
            user = db.query(models.User).filter(models.User.id == item.user_id).first()
            if not user or not user.is_active:
                continue

            review_data = {
                "id": item.id,
                "category": cat,
                "title": item.title,
                "review": item.review,
                "rating": item.rating,
                "username": user.username,
                "user_id": user.id,
            }

            if not is_public_review_safe(review_data["review"]):
                continue

            if cat == "movie":
                review_data.update({
                    "director": item.director,
                    "year": item.year,
                    "poster_url": item.poster_url,
                })
            elif cat in ["tv_show", "anime"]:
                review_data.update({
                    "year": item.year,
                    "seasons": item.seasons,
                    "episodes": item.episodes,
                    "poster_url": item.poster_url,
                })
            elif cat == "video_game":
                review_data.update({
                    "release_date": item.release_date.isoformat() if item.release_date else None,
                    "genres": item.genres,
                    "cover_art_url": item.cover_art_url,
                })
            elif cat == "music":
                review_data.update({
                    "artist": item.artist,
                    "year": item.year,
                    "cover_art_url": item.cover_art_url,
                })
            elif cat == "book":
                review_data.update({
                    "author": item.author,
                    "year": item.year,
                    "cover_art_url": item.cover_art_url,
                })

            reviews.append(review_data)

    if not category:
        reviews.sort(key=lambda item: item["id"], reverse=True)
        return reviews[offset:offset + limit]
    return reviews[:limit]


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

    item = None
    if category == "movie":
        item = db.query(models.Movie).filter(base_filter(models.Movie)).first()
    elif category == "tv_show":
        item = db.query(models.TVShow).filter(base_filter(models.TVShow)).first()
    elif category == "anime":
        item = db.query(models.Anime).filter(base_filter(models.Anime)).first()
    elif category == "video_game":
        item = db.query(models.VideoGame).filter(base_filter(models.VideoGame)).first()
    elif category == "music":
        item = db.query(models.Music).filter(base_filter(models.Music)).first()
    elif category == "book":
        item = db.query(models.Book).filter(base_filter(models.Book)).first()
    else:
        raise HTTPException(status_code=400, detail="Invalid category")

    if not item:
        raise HTTPException(status_code=404, detail="Review not found")
    if not is_public_review_safe(item.review):
        raise HTTPException(status_code=404, detail="Review not found")

    user = db.query(models.User).filter(models.User.id == item.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="Review not found")

    review_data = {
        "id": item.id,
        "category": category,
        "title": item.title,
        "review": item.review,
        "rating": item.rating,
        "username": user.username,
        "user_id": user.id,
    }

    if category == "movie":
        review_data.update({
            "director": item.director,
            "year": item.year,
            "poster_url": item.poster_url,
        })
    elif category in ["tv_show", "anime"]:
        review_data.update({
            "year": item.year,
            "seasons": item.seasons,
            "episodes": item.episodes,
            "poster_url": item.poster_url,
        })
    elif category == "video_game":
        review_data.update({
            "release_date": item.release_date.isoformat() if item.release_date else None,
            "genres": item.genres,
            "cover_art_url": item.cover_art_url,
        })
    elif category == "music":
        review_data.update({
            "artist": item.artist,
            "year": item.year,
            "cover_art_url": item.cover_art_url,
        })
    elif category == "book":
        review_data.update({
            "author": item.author,
            "year": item.year,
            "cover_art_url": item.cover_art_url,
        })

    return review_data
