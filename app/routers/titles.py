"""Public title pages (/titles/<kind>/<slug>) and the /titles directory."""
from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
from datetime import date, datetime, timedelta
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, title_metadata, title_pages
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..site_chrome import apply_site_chrome, editorial_picks, message_page

router = APIRouter(tags=["titles"])
SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
CSS_VERSION = "20261009-take-1"
JS_VERSION = "20261009-take-1"
SCHEMA_TYPES = {"movie": "Movie", "tv": "TVSeries", "anime": "TVSeries", "game": "VideoGame", "album": "MusicAlbum", "book": "Book"}
CREATOR_SCHEMA = {"movie": "director", "album": "byArtist", "book": "author"}
CREATOR_LABEL = {"movie": "Director", "album": "Artist", "book": "Author"}
KIND_PLURALS = {"movie": "Movies", "tv": "TV shows", "anime": "Anime", "game": "Games", "album": "Albums", "book": "Books"}
GUEST_LIST_MAX = 30
TAKE_DAYS = 60
TAKE_TOKEN = re.compile(r"[A-Za-z0-9_-]{16,64}")
VERBS = {"movie": "watched", "tv": "watched", "anime": "watched", "game": "played", "album": "listened to", "book": "read"}


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _pretty_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        if len(value) >= 10:
            day = date.fromisoformat(value[:10])
            return f"{day:%B} {day.day}, {day.year}"
        if len(value) == 7:
            day = date.fromisoformat(value + "-01")
            return f"{day:%B} {day.year}"
    except ValueError:
        return value
    return value


def _excerpt(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def _lead_sentences(text: str, sentences: int = 2, limit: int = 320) -> str:
    """The first sentence or two of a borrowed description (pages lead with our own content)."""
    text = " ".join((text or "").split())
    end, found = 0, 0
    while found < sentences:
        cut = min((i for i in (text.find(". ", end), text.find("! ", end), text.find("? ", end)) if i != -1), default=-1)
        if cut == -1 or cut + 1 > limit:
            break
        end, found = cut + 1, found + 1
    if found:
        return text[:end]
    return _excerpt(text, limit)


def _paragraphs(text: str) -> str:
    return "".join(f"<p>{_e(part.strip())}</p>" for part in (text or "").split("\n") if part.strip())


def _genres(metadata: dict) -> list[str]:
    cleaned = []
    for genre in metadata.get("genres") or []:
        text = str(genre)
        for suffix in (" film", " video game", " television series", " television program", " novel", " music", " anime"):
            if text.endswith(suffix) and len(text) > len(suffix) + 2:
                text = text[: -len(suffix)]
        text = text[:1].upper() + text[1:]
        if text not in cleaned:
            cleaned.append(text)
    return cleaned[:6]


def _metadata_creator(kind: str, summary: dict) -> Optional[str]:
    return summary.get("creator")


def _take_for(db: Session, token: Optional[str], group):
    """A live "what did you think?" request for this title, with its asker (or None)."""
    if not token or not TAKE_TOKEN.fullmatch(token):
        return None
    take = db.query(models.TakeRequest).filter(models.TakeRequest.token == token).first()
    if (take is None or take.expires_at <= datetime.utcnow()
            or take.kind != group.kind or take.slug != group.path.rsplit("/", 1)[1]):
        return None
    asker = db.get(models.User, take.asker_id)
    if asker is None or not asker.is_active:
        return None
    return take, asker


async def _load(request: Request, db: Session, kind: str, slug: str):
    group = title_pages.find(db, kind, slug)
    if group is None:
        return None, None, None
    summary = title_pages.summarize(db, group)
    client = getattr(request.app.state, "external_api_client", None)
    metadata = await title_metadata.get_or_fetch(
        db, client, kind, group.normalized, group.title, group.year, _metadata_creator(kind, summary))
    return group, summary, metadata


def _json_ld(group, summary: dict, metadata: dict, canonical: str, image: Optional[str]) -> str:
    item: dict = {"@context": "https://schema.org", "@type": SCHEMA_TYPES[group.kind], "name": group.title, "url": canonical}
    if metadata.get("release_date"):
        item["datePublished"] = metadata["release_date"]
    elif group.year:
        item["datePublished"] = str(group.year)
    if image:
        item["image"] = image
    if metadata.get("short_description") or metadata.get("description"):
        item["description"] = _lead_sentences(metadata.get("description") or metadata.get("short_description"), limit=300)
    if _genres(metadata):
        item["genre"] = _genres(metadata)[:4]
    creator = summary.get("creator")
    if creator and group.kind in CREATOR_SCHEMA:
        item[CREATOR_SCHEMA[group.kind]] = {"@type": "MusicGroup" if group.kind == "album" else "Person", "name": creator}
    if metadata.get("trailer"):
        item["trailer"] = {"@type": "VideoObject", "name": f"{group.title} trailer",
                           "embedUrl": f"https://www.youtube-nocookie.com/embed/{metadata['trailer']}",
                           "thumbnailUrl": f"https://i.ytimg.com/vi/{metadata['trailer']}/hqdefault.jpg",
                           "uploadDate": metadata.get("release_date") or str(group.year or "")}
        if not item["trailer"]["uploadDate"]:
            item.pop("trailer")
    if summary.get("average_rating") is not None:
        item["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": summary["average_rating"],
                                   "ratingCount": summary["rated"], "bestRating": 10, "worstRating": 0}
    reviews = [r for r in summary["reviews"] if r["search_ready"]][:3]
    if reviews:
        item["review"] = [{"@type": "Review", "author": {"@type": "Person", "name": r["username"]},
                           "reviewBody": _excerpt(r["review"], 500), "url": SITE_URL + r["url"],
                           **({"reviewRating": {"@type": "Rating", "ratingValue": r["rating"], "bestRating": 10, "worstRating": 0}}
                              if r["rating"] is not None else {})} for r in reviews]
    breadcrumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_URL}/"},
        {"@type": "ListItem", "position": 2, "name": "Titles", "item": f"{SITE_URL}/titles"},
        {"@type": "ListItem", "position": 3, "name": group.title, "item": canonical},
    ]}
    dump = lambda data: json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return (f'<script type="application/ld+json">{dump(item)}</script>\n'
            f'<script type="application/ld+json">{dump(breadcrumbs)}</script>')


def _scores_html(summary: dict, metadata: dict) -> str:
    chips = []
    if summary.get("average_rating") is not None:
        chips.append(f'<div class="title-score title-score--ours"><strong>{_e(summary["average_rating"])}<small>/10</small></strong>'
                     f'<span>OmniTrackr members ({_e(summary["rated"])} ratings)</span></div>')
    for score in metadata.get("scores") or []:
        chips.append(f'<div class="title-score"><strong>{_e(score["value"])}</strong><span>{_e(score["source"])}</span></div>')
    return f'<div class="title-scores" aria-label="Scores">{"".join(chips)}</div>' if chips else ""


def _trailer_html(group, metadata: dict) -> str:
    video = metadata.get("trailer")
    if not video:
        return ""
    return (
        '<section class="title-section" aria-labelledby="trailer-title"><h2 id="trailer-title">Trailer</h2>'
        f'<button type="button" class="title-trailer" data-youtube-id="{_e(video)}" aria-label="Play the {_e(group.title)} trailer">'
        f'<img src="https://i.ytimg.com/vi/{_e(video)}/hqdefault.jpg" alt="" loading="lazy" width="480" height="360">'
        '<span class="title-trailer__play" aria-hidden="true">▶</span>'
        '<span class="title-trailer__note">Plays from YouTube (privacy-enhanced mode)</span></button></section>'
    )


def _gallery_html(group, metadata: dict) -> str:
    shots = metadata.get("gallery") or []
    if not shots:
        return ""
    label = "Screenshots" if group.kind == "game" else "Images"
    tiles = "".join(
        f'<a class="title-gallery__item" href="{_e(shot["url"])}" target="_blank" rel="noopener">'
        f'<img src="{_e(shot.get("thumb") or shot["url"])}" alt="{_e(group.title)} image {index + 1}" loading="lazy"></a>'
        for index, shot in enumerate(shots)
    )
    return f'<section class="title-section" aria-labelledby="gallery-title"><h2 id="gallery-title">{label}</h2><div class="title-gallery">{tiles}</div></section>'


def _about_html(group, summary: dict, metadata: dict) -> str:
    rows = []
    release = _pretty_date(metadata.get("release_date")) or (str(group.year) if group.year else None)
    if release:
        rows.append(("First released" if group.kind not in ("tv", "anime") else "Premiered", release))
    if metadata.get("end_date") and group.kind in ("tv", "anime"):
        rows.append(("Ended", _pretty_date(metadata["end_date"])))
    if summary.get("creator") and group.kind in CREATOR_LABEL and not any(f["label"] == CREATOR_LABEL[group.kind] for f in metadata.get("facts") or []):
        rows.append((CREATOR_LABEL[group.kind], summary["creator"]))
    rows += [(fact["label"], fact["value"]) for fact in metadata.get("facts") or []]
    if _genres(metadata):
        rows.append(("Genres", ", ".join(_genres(metadata))))
    description = ""
    if metadata.get("description"):
        source = metadata.get("description_source") or {}
        credit = ""
        if source.get("name"):
            license_part = (f' under <a href="{_e(source.get("license_url"))}" rel="noopener license">{_e(source["license"])}</a>'
                            if source.get("license_url") else "")
            credit = (f'<p class="title-credit">Description from <a href="{_e(source.get("url"))}" rel="noopener">{_e(source["name"])}</a>'
                      f'{license_part}.</p>')
        more = (f' <a class="title-readmore" href="{_e(source.get("url"))}" rel="noopener">Read more on {_e(source["name"])} ↗</a>'
                if source.get("url") and source.get("name") else "")
        description = (f'<div class="title-description"><p>{_e(_lead_sentences(metadata["description"]))}{more}</p>'
                       f'{credit}</div>')
    facts = "".join(f"<div><dt>{_e(label)}</dt><dd>{_e(value)}</dd></div>" for label, value in rows if value)
    if not description and not facts:
        return ""
    return (f'<section class="title-section title-about" aria-labelledby="about-title"><h2 id="about-title">About {_e(group.title)}</h2>'
            f'{description}<dl class="title-facts">{facts}</dl></section>')


def _tracks_html(metadata: dict) -> str:
    tracks = metadata.get("tracks") or []
    if not tracks:
        return ""
    rows = "".join(f'<li><span>{_e(track["name"])}</span><span>{_e(track.get("duration"))}</span></li>' for track in tracks)
    return f'<section class="title-section" aria-labelledby="tracks-title"><h2 id="tracks-title">Track list</h2><ol class="title-tracks">{rows}</ol></section>'


def _community_html(group, summary: dict) -> str:
    verb = VERBS[group.kind]
    tiles = [f'<div><strong>{_e(summary["members"])}</strong><span>member{"s" if summary["members"] != 1 else ""} tracking it</span></div>',
             f'<div><strong>{_e(summary["finished"])}</strong><span>have {verb} it</span></div>']
    if summary.get("average_rating") is not None:
        tiles.append(f'<div><strong>{_e(summary["average_rating"])}/10</strong><span>average member rating</span></div>')
    else:
        tiles.append(f'<div><strong>{_e(summary["rated"])}</strong><span>member rating{"s" if summary["rated"] != 1 else ""}</span></div>')
    reviews = ""
    for review in summary["reviews"][:6]:
        rating = f'<span class="title-review__rating">{_e(review["rating"])}/10</span>' if review["rating"] is not None else ""
        author = (f'<a class="title-review__author" href="{_e(review["profile_url"])}">{_e(review["username"])}</a>'
                  if review.get("profile_url") else _e(review["username"]))
        reviews += (f'<article class="title-review"><header><strong>{author}</strong>{rating}</header>'
                    f'<p>{_e(_excerpt(review["review"], 420))}</p>'
                    f'<a href="{_e(review["url"])}">Read the full review <span aria-hidden="true">→</span></a></article>')
    if not reviews:
        reviews = (f'<p class="title-empty">No public reviews yet. <a href="#write-review">Be the first to review '
                   f'{_e(group.title)}</a>.</p>')
    return (f'<section class="title-section" aria-labelledby="community-title"><h2 id="community-title">On OmniTrackr</h2>'
            f'<div class="title-stats">{"".join(tiles)}</div>'
            f'<h3 class="title-subhead">Member reviews</h3><div class="title-reviews">{reviews}</div></section>')


def _write_review_html(group, summary: dict, signed_in: bool, take=None) -> str:
    """The prompt (and, for members, the form) that turns a visitor into the next reviewer."""
    verb = VERBS[group.kind]
    first = not summary["reviews"]
    heading = f"Be the first to review {group.title}" if first else f"Add your review of {group.title}"
    asked = ""
    if take:
        heading = f"Share your take on {group.title}"
        asked = (f'<p class="title-write__asked"><strong>{_e(take[1].username)}</strong> asked what you thought of '
                 f'{_e(group.title)}. Your review appears on this page, and they get a note when it does.</p>')
    lead = (f"Have you {verb} it? A few honest sentences help the next person decide. "
            "Reviews of a few sentences (about 50 words) get their own page and can show up in search.")
    slug = group.path.rsplit("/", 1)[1]
    if signed_in:
        take_attr = f' data-take="{_e(take[0].token)}"' if take else ""
        action = (
            f'<form class="title-write__form" data-title-review data-title-kind="{_e(group.kind)}" data-title-slug="{_e(slug)}"'
            f'{take_attr} novalidate>'
            '<label class="title-write__label" for="titleReviewText">Your review</label>'
            f'<textarea id="titleReviewText" name="review" rows="6" maxlength="10000" required '
            f'placeholder="What stayed with you? Who would you recommend it to?"></textarea>'
            '<p class="title-write__meter" id="titleReviewMeter" aria-live="polite"></p>'
            '<div class="title-write__row">'
            '<label class="title-write__rating" for="titleReviewRating"><span>Rating <small>(optional, out of 10)</small></span>'
            '<input id="titleReviewRating" name="rating" type="number" min="0" max="10" step="0.1" inputmode="decimal"></label>'
            '<label class="title-write__public"><input id="titleReviewPublic" name="public" type="checkbox" checked> Show it on this page</label>'
            '</div>'
            '<p class="title-write__note">Saving adds the title to your library if it isn\'t there yet. You can edit or hide the review any time.</p>'
            '<button type="submit" class="site-btn site-btn--primary">Save review</button>'
            '<p class="title-write__status" role="status" aria-live="polite"></p></form>'
        )
    else:
        from urllib.parse import quote
        query = f"?take={take[0].token}" if take else ""
        signin = "/?next=" + quote(f"{group.path}{query}#write-review", safe="") + "#landing-auth"
        action = (f'<div class="title-write__actions"><a class="site-btn site-btn--primary" href="{_e(signin)}">Sign in to write a review</a>'
                  '<a class="site-btn site-btn--ghost" href="/#signup">Create a free account</a></div>'
                  '<p class="title-write__note">Free, and your library stays private unless you choose to share a review.</p>')
    return (f'<section class="title-section title-write" id="write-review" aria-labelledby="write-review-title">'
            f'<h2 id="write-review-title">{_e(heading)}</h2>{asked}<p class="title-write__lead">{_e(lead)}</p>{action}</section>')


def _collections_html(summary: dict) -> str:
    if not summary["collections"]:
        return ""
    cards = "".join(f'<a class="title-collection" href="{_e(c["url"])}"><strong>{_e(c["name"])}</strong>'
                    f'<span>{_e(_excerpt(c["description"], 140))}</span></a>' for c in summary["collections"])
    return f'<section class="title-section" aria-labelledby="collections-title"><h2 id="collections-title">In public collections</h2><div class="title-collections">{cards}</div></section>'


def _related_html(summary: dict) -> str:
    if not summary["related"]:
        return ""
    cards = ""
    for item in summary["related"]:
        art = (f'<img src="{_e(item["image"])}" alt="" loading="lazy">' if item.get("image")
               else f'<span>{_e(item["title"][:1].upper())}</span>')
        year = f' · {item["year"]}' if item.get("year") else ""
        cards += (f'<a class="title-related" href="{_e(item["url"])}"><span class="title-related__art">{art}</span>'
                  f'<strong>{_e(item["title"])}</strong><small>{_e(item["label"])}{_e(year)}</small></a>')
    return f'<section class="title-section" aria-labelledby="related-title"><h2 id="related-title">Members who track this also track</h2><div class="title-related-grid">{cards}</div></section>'


def _links_html(metadata: dict) -> str:
    links = metadata.get("links") or []
    if not links:
        return ""
    items = "".join(f'<a href="{_e(link["url"])}" target="_blank" rel="noopener">{_e(link["label"])} ↗</a>' for link in links)
    return f'<nav class="title-links" aria-label="Elsewhere">{items}</nav>'


def _sources_html(metadata: dict) -> str:
    sources = metadata.get("sources") or []
    if not sources:
        return ""
    parts = ", ".join(
        f'<a href="{_e(s["url"])}" rel="noopener">{_e(s["name"])}</a>' + (f" ({_e(s['license'])})" if s.get("license") else "")
        for s in sources
    )
    return (f'<p class="title-sources">Title information from {parts}. Scores belong to their publishers; '
            'member data is aggregated from OmniTrackr libraries and never identifies who tracks a title.</p>')


def render(group, summary: dict, metadata: Optional[dict], indexable: bool, signed_in: bool, take=None) -> str:
    metadata = metadata or {}
    kind_label = title_pages.KINDS[group.kind][3]
    canonical = SITE_URL + group.path
    image = metadata.get("poster") or summary.get("image")
    year = f" ({group.year})" if group.year else ""
    page_title = f"{group.title}{year}: reviews, trailer and details | OmniTrackr"
    lead = metadata.get("short_description") or ""
    description_bits = [f"{group.title}{year} — {lead}." if lead else f"{group.title}{year} ({kind_label.lower()})."]
    if summary["reviews"]:
        description_bits.append(f"{len(summary['reviews'])} member review{'s' if len(summary['reviews']) != 1 else ''}")
    if summary["members"]:
        description_bits.append(f"tracked by {summary['members']} OmniTrackr member{'s' if summary['members'] != 1 else ''}")
    if metadata.get("trailer"):
        description_bits.append("trailer")
    meta_description = _excerpt(", ".join(description_bits) + ".", 158)
    robots = "index, follow, max-image-preview:large" if indexable else "noindex, follow"
    poster = (f'<img class="title-hero__poster" src="{_e(image)}" alt="{_e(group.title)} poster" width="300" height="450" fetchpriority="high">'
              if image else f'<div class="title-hero__poster title-hero__poster--empty" aria-hidden="true">{_e(group.title[:1].upper())}</div>')
    backdrop = metadata.get("backdrop") or image
    backdrop_html = f'<img class="title-hero__backdrop" src="{_e(backdrop)}" alt="" aria-hidden="true">' if backdrop else ""
    genres = "".join(f'<span class="site-chip">{_e(g)}</span>' for g in _genres(metadata)[:4])
    release = _pretty_date(metadata.get("release_date"))
    meta_line = " · ".join(filter(None, [kind_label, release or (str(group.year) if group.year else None),
                                         summary.get("creator")]))
    track = ('<button type="button" class="site-btn site-btn--primary" data-title-add '
             f'data-title-kind="{_e(group.kind)}" data-title-slug="{_e(group.path.rsplit("/", 1)[1])}">Add to my library</button>'
             if signed_in else
             ('<button type="button" class="site-btn site-btn--primary" data-guest-save aria-pressed="false" '
              f'data-guest-kind="{_e(group.kind)}" data-guest-slug="{_e(group.path.rsplit("/", 1)[1])}" '
              f'data-guest-title="{_e(group.title)}">Save to my list</button>'
              '<a class="site-btn site-btn--ghost" href="/#signup">Create free account</a>'))
    ask = (f'<button type="button" class="site-btn site-btn--ghost" id="ask-friend" data-take-ask '
           f'data-title-kind="{_e(group.kind)}" data-title-slug="{_e(group.path.rsplit("/", 1)[1])}" '
           f'data-take-title="{_e(group.title)}">Ask a friend for their take</button>' if signed_in else "")
    reviews_link = (f'<a class="site-btn site-btn--ghost" href="#community-title">Read {len(summary["reviews"])} member review'
                    f'{"s" if len(summary["reviews"]) != 1 else ""}</a>' if summary["reviews"]
                    else '<a class="site-btn site-btn--ghost" href="#write-review">Write the first review</a>')
    body = "".join([
        # Our own content first: member reviews and stats, then collections and "also track".
        _community_html(group, summary), _write_review_html(group, summary, signed_in, take),
        _trailer_html(group, metadata), _about_html(group, summary, metadata),
        _collections_html(summary), _related_html(summary), _gallery_html(group, metadata), _tracks_html(metadata),
    ])
    og_image = f'<meta property="og:image" content="{_e(image)}">' if image else ""
    ad_loader = ('<script src="/static/ad-loader.js" defer></script>'
                 if indexable and not signed_in and title_pages.is_ad_eligible(summary, metadata) else "")
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_e(page_title)}</title>
  <meta name="description" content="{_e(meta_description)}">
  <meta name="robots" content="{robots}">
  <link rel="canonical" href="{_e(canonical)}">
  <meta property="og:title" content="{_e(group.title + year)}">
  <meta property="og:description" content="{_e(meta_description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{_e(canonical)}">
  {og_image}
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">
  <link rel="stylesheet" href="/static/title-page.css?v={CSS_VERSION}">
  <script src="/static/title-page.js?v={JS_VERSION}" defer></script>
  <script src="/static/share.js?v=20261004-share-1" defer></script>
  {'' if signed_in else '<script src="/static/guest-list.js?v=20261003-guest-2" defer></script>'}
  {ad_loader}
  {_json_ld(group, summary, metadata, canonical, image)}
</head>
<body class="site title-page">
  <!--SITE_NAV:-->
  <main>
    <section class="title-hero">
      {backdrop_html}
      <div class="site-wrap title-hero__inner">
        {poster}
        <div class="title-hero__copy">
          <nav class="title-crumbs" aria-label="Breadcrumb"><a href="/titles">Titles</a> <span aria-hidden="true">/</span> <a href="/titles#{_e(group.kind)}">{_e(KIND_PLURALS[group.kind])}</a></nav>
          <h1>{_e(group.title)}{f' <span class="title-hero__year">{_e(group.year)}</span>' if group.year else ''}</h1>
          <p class="title-hero__meta">{_e(meta_line)}</p>
          {f'<p class="title-hero__lead">{_e(lead[:1].upper() + lead[1:])}</p>' if lead else ''}
          <div class="title-hero__chips">{genres}</div>
          {_scores_html(summary, metadata)}
          <div class="title-hero__actions">{track}{reviews_link}{ask}<button type="button" class="site-btn site-btn--ghost" data-share data-share-title="{_e(group.title + year)} on OmniTrackr">Share</button></div>
          <p class="title-hero__status" role="status" aria-live="polite"></p>
          {_links_html(metadata)}
        </div>
      </div>
    </section>
    <div class="site-wrap title-body">
      {body}
      {_sources_html(metadata)}
    </div>
  </main>
  <!--SITE_FOOTER-->
</body>
</html>"""
    return apply_site_chrome(page)


@router.get("/titles/{kind}/{slug}", include_in_schema=False)
async def title_page(kind: str, slug: str, request: Request, db: Session = Depends(get_db)):
    if kind not in title_pages.KINDS:
        raise HTTPException(404, "Unknown title type")
    group, summary, metadata = await _load(request, db, kind, slug)
    if group is None:
        raise HTTPException(404, "Title not found")
    token = request.query_params.get("take")
    if slug != group.path.rsplit("/", 1)[1]:
        from fastapi.responses import RedirectResponse
        keep = f"?take={token}" if token and TAKE_TOKEN.fullmatch(token) else ""
        return RedirectResponse(group.path + keep, status_code=301)
    indexable = title_pages.is_indexable(summary, metadata)
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    take = _take_for(db, token, group)
    response = strict_html_response(render(group, summary, metadata, indexable, signed_in, take))
    response.headers["Cache-Control"] = "private, no-store" if signed_in or token else "public, max-age=600"
    response.headers["Vary"] = "Cookie"
    if not indexable or token:
        # Personal ?take= links stay out of search; the canonical page carries the content.
        response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


def add_group_to_library(db: Session, user, group) -> tuple[str, object]:
    """Add a title to the member's library with public details only (never anyone's rating or notes).

    Returns ("existing" | "created", record). Does not commit.
    """
    model, _, library_category, _, _ = title_pages.KINDS[group.kind]
    normalized = func.lower(func.trim(model.title))
    existing = db.query(model).filter(model.user_id == user.id, normalized == group.normalized).first()
    if existing:
        return "existing", existing
    from ..for_you import LIBRARY
    fields = LIBRARY[library_category][1]
    source = max(group.items, key=lambda item: sum(bool(getattr(item, f, None)) for f in fields))
    payload = {f: getattr(source, f, None) for f in fields}
    payload["title"] = group.title
    for image_field in ("poster_url", "cover_art_url", "rawg_link"):
        if image_field in payload and not title_pages._safe_image(payload[image_field]):
            payload[image_field] = None
    if group.kind == "movie" and payload.get("director") is None:
        payload["director"] = ""
    record = model(user_id=user.id, **payload)
    db.add(record)
    db.flush()
    return "created", record


@router.post("/api/titles/{kind}/{slug}/add")
def add_title(kind: str, slug: str, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Add this title to the member's library with public details only (never anyone's rating or notes)."""
    response.headers["Cache-Control"] = "private, no-store"
    group = title_pages.find(db, kind, slug)
    if group is None:
        raise HTTPException(404, "Title not found")
    state, record = add_group_to_library(db, user, group)
    db.commit()
    return {"state": state, "title": record.title, "category": title_pages.KINDS[kind][2]}


class TitleReview(BaseModel):
    review: str = Field(..., min_length=1, max_length=10000)
    rating: Optional[float] = Field(None, ge=0, le=10)
    public: bool = True
    # The review text the composer loaded; a mismatch means it was edited elsewhere since.
    expected_review: str = Field("", max_length=10000)
    # Present when the member arrived through a friend's "what did you think?" link.
    take: Optional[str] = Field(None, max_length=64)

    @field_validator("review")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Write a few words first")
        return value


def _own_item(db: Session, user, group):
    model = title_pages.KINDS[group.kind][0]
    normalized = func.lower(func.trim(model.title))
    return db.query(model).filter(model.user_id == user.id, normalized == group.normalized).first()


@router.post("/api/titles/{kind}/{slug}/ask")
def ask_for_takes(kind: str, slug: str, request: Request, response: Response,
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    """A link the member can send friends: the title page, asking for their review."""
    response.headers["Cache-Control"] = "private, no-store"
    group = title_pages.find(db, kind, slug)
    if group is None:
        raise HTTPException(404, "Title not found")
    page_slug = group.path.rsplit("/", 1)[1]
    now = datetime.utcnow()
    take = db.query(models.TakeRequest).filter(
        models.TakeRequest.asker_id == user.id, models.TakeRequest.kind == group.kind,
        models.TakeRequest.slug == page_slug, models.TakeRequest.expires_at > now + timedelta(days=7),
    ).order_by(models.TakeRequest.expires_at.desc()).first()
    if take is None:
        take = models.TakeRequest(asker_id=user.id, kind=group.kind, slug=page_slug, title=group.title,
                                  token=secrets.token_urlsafe(18), created_at=now, expires_at=now + timedelta(days=TAKE_DAYS))
        db.add(take)
        db.commit()
    return {
        "url": f"{SITE_URL}{group.path}?take={take.token}#write-review",
        "title": f"{group.title} on OmniTrackr",
        "text": f"What did you think of {group.title}? I'd love your take.",
        "expires_at": take.expires_at.isoformat(),
    }


def _deliver_take(db: Session, token: Optional[str], group, responder) -> Optional[str]:
    """Tell the asker (once per friend) that a friend answered; returns the asker's username."""
    found = _take_for(db, token, group)
    if not found:
        return None
    take, asker = found
    if asker.id == responder.id:
        return None
    if db.query(models.TakeResponse).filter_by(request_id=take.id, responder_id=responder.id).first():
        return asker.username
    db.add(models.TakeResponse(request_id=take.id, responder_id=responder.id))
    db.add(models.Notification(user_id=asker.id, type="take_received", link=f"{group.path}#community-title",
                               message=f"{responder.username} shared their take on {group.title}."))
    try:
        db.commit()
    except Exception:
        db.rollback()  # A double submit raced the unique constraint; the note already went out.
    return asker.username


@router.get("/api/titles/{kind}/{slug}/my-review")
def my_title_review(kind: str, slug: str, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """The member's own entry for this title, so the title page composer can start from it."""
    response.headers["Cache-Control"] = "private, no-store"
    group = title_pages.find(db, kind, slug)
    if group is None:
        raise HTTPException(404, "Title not found")
    item = _own_item(db, user, group)
    if item is None:
        return {"in_library": False, "review": "", "rating": None, "public": True}
    return {"in_library": True, "review": item.review or "", "rating": item.rating, "public": bool(item.review_public)}


@router.put("/api/titles/{kind}/{slug}/review")
def save_title_review(kind: str, slug: str, payload: TitleReview, request: Request, response: Response,
                      user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Write or update the member's review from the title page (adds the title to their library if needed)."""
    from ..review_quality import evaluate_public_review
    from .reviews import PUBLIC_REVIEW_DETAIL_MIN_CHARS, PUBLIC_REVIEW_MIN_CHARS
    response.headers["Cache-Control"] = "private, no-store"
    group = title_pages.find(db, kind, slug)
    if group is None:
        raise HTTPException(404, "Title not found")
    item = _own_item(db, user, group)
    if item is not None and (item.review or "").strip() != payload.expected_review.strip():
        raise HTTPException(409, "Your review for this title changed somewhere else. Reload the page to see the latest version.")
    state = "existing"
    if item is None:
        state, item = add_group_to_library(db, user, group)
    item.review = payload.review
    item.review_public = payload.public
    if payload.rating is not None:
        item.rating = round(payload.rating, 1)
    db.commit()
    quality = evaluate_public_review(payload.review, PUBLIC_REVIEW_MIN_CHARS, PUBLIC_REVIEW_DETAIL_MIN_CHARS)
    review_category = title_pages.KINDS[kind][1]
    standalone = payload.public and quality.search_ready
    listed = payload.public and quality.community_ready
    # Only a review the friend can actually read on the page counts as an answer.
    asked_by = _deliver_take(db, payload.take, group, user) if listed and payload.take else None
    return {
        "asked_by": asked_by,
        "state": state,
        "public": payload.public,
        "word_count": quality.word_count,
        "listed": listed,
        "standalone": standalone,
        "review_url": f"/reviews/{item.id}?category={review_category}" if standalone else None,
    }


class GuestListItem(BaseModel):
    kind: str = Field(..., max_length=10)
    slug: str = Field(..., max_length=130)


class GuestListImport(BaseModel):
    items: list[GuestListItem] = Field(default_factory=list, max_length=GUEST_LIST_MAX)


@router.post("/api/guest-list/import")
def import_guest_list(
    payload: GuestListImport,
    request: Request,
    response: Response,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Move titles a visitor saved before signing up (kept in their browser) into their new library."""
    response.headers["Cache-Control"] = "private, no-store"
    added, existing, missing = [], [], 0
    seen = set()
    for item in payload.items:
        key = (item.kind, item.slug)
        if key in seen:
            continue
        seen.add(key)
        group = title_pages.find(db, item.kind, item.slug) if item.kind in title_pages.KINDS else None
        if group is None:
            missing += 1
            continue
        state, record = add_group_to_library(db, user, group)
        entry = {"title": record.title, "category": title_pages.KINDS[item.kind][2]}
        (added if state == "created" else existing).append(entry)
    db.commit()
    if added:
        from .. import funnel
        funnel.record("guest_list_imported", request)
    return {"added": added, "existing": existing, "missing": missing}


@router.get("/titles", include_in_schema=False)
def titles_index(request: Request, db: Session = Depends(get_db)):
    sections, total = [], 0
    for kind in title_pages.KINDS:
        items = title_pages.popular(db, kind, limit=18)
        total += len(items)
        if not items:
            continue
        cards = ""
        for item in items:
            art = (f'<img src="{_e(item["image"])}" alt="" loading="lazy">' if item.get("image")
                   else f'<span>{_e(item["title"][:1].upper())}</span>')
            year = f" · {item['year']}" if item.get("year") else ""
            cards += (f'<a class="title-related" href="{_e(item["url"])}"><span class="title-related__art">{art}</span>'
                      f'<strong>{_e(item["title"])}</strong><small>{_e(item["members"])} members{_e(year)}</small></a>')
        sections.append(f'<section class="title-section" id="{kind}" aria-labelledby="{kind}-heading">'
                        f'<h2 id="{kind}-heading">{_e(KIND_PLURALS[kind])}</h2><div class="title-related-grid">{cards}</div></section>')
    if not sections:
        sections.append(editorial_picks(
            "Looking for something to start?",
            "Titles appear here as members track them. Meanwhile, these OmniTrackr guides compare picks across "
            "every medium and explain who each one suits.",
        ))
    # The directory itself is mostly links; it's only worth indexing once enough titles have member reviews.
    index_directory = len(title_pages.reviewed_titles(db)) >= 8
    robots = "index, follow" if index_directory else "noindex, follow"
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Popular titles on OmniTrackr: movies, shows, anime, games, books and albums</title>
  <meta name="description" content="The movies, TV shows, anime, games, books and albums OmniTrackr members track most, each with details, trailers, scores and member reviews.">
  <meta name="robots" content="{robots}">
  <link rel="canonical" href="{SITE_URL}/titles">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">
  <link rel="stylesheet" href="/static/title-page.css?v={CSS_VERSION}">
</head>
<body class="site title-page">
  <!--SITE_NAV:titles-->
  <main>
    <section class="site-hero"><div class="site-wrap">
      <p class="site-eyebrow">Titles</p>
      <h1>What OmniTrackr members are tracking</h1>
      <p>The most-tracked movies, shows, anime, games, books and albums on OmniTrackr. Every title has its details, trailer, scores and what members thought of it.</p>
    </div></section>
    <div class="site-wrap title-body">{"".join(sections)}</div>
  </main>
  <!--SITE_FOOTER-->
</body>
</html>"""
    response = strict_html_response(apply_site_chrome(page))
    response.headers["Cache-Control"] = "public, max-age=900"
    if not index_directory:
        response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


def sitemap_entries(db: Session, limit: int = 500) -> list[str]:
    """Indexable title pages for the sitemap (metadata must already be cached)."""
    seen, paths = set(), []
    candidates = title_pages.reviewed_titles(db)
    for kind in title_pages.KINDS:
        candidates += [dict(item) for item in title_pages.popular(db, kind, limit=150, min_members=title_pages.INDEX_MIN_MEMBERS)]
    for candidate in candidates:
        if candidate["url"] in seen or len(paths) >= limit:
            continue
        seen.add(candidate["url"])
        group = title_pages.find(db, candidate["kind"], candidate["url"].rsplit("/", 1)[1])
        if group is None:
            continue
        summary = title_pages.summarize(db, group)
        metadata, _ = title_metadata.cached(db, title_metadata.cache_key(group.kind, group.normalized, group.year))
        if title_pages.is_indexable(summary, metadata):
            paths.append(group.path)
    return paths


async def warm_metadata(session_factory, client, batch: int = 8) -> int:
    """Fetch facts for titles that are likely to get traffic but aren't cached yet."""
    db = session_factory()
    fetched = 0
    try:
        candidates = title_pages.reviewed_titles(db)
        for kind in title_pages.KINDS:
            candidates += title_pages.popular(db, kind, limit=60, min_members=2)
        for candidate in candidates:
            if fetched >= batch:
                break
            group = title_pages.find(db, candidate["kind"], candidate["url"].rsplit("/", 1)[1])
            if group is None:
                continue
            key = title_metadata.cache_key(group.kind, group.normalized, group.year)
            _, fresh = title_metadata.cached(db, key)
            if fresh:
                continue
            creator = title_pages.summarize(db, group).get("creator")
            await title_metadata.get_or_fetch(db, client, group.kind, group.normalized, group.title, group.year, creator, wait=20)
            fetched += 1
            await asyncio.sleep(2)  # Be gentle with Wikipedia and friends.
    finally:
        db.close()
    return fetched


async def warm_loop(app) -> None:
    from ..database import SessionLocal
    await asyncio.sleep(240)
    while True:
        try:
            client = getattr(app.state, "external_api_client", None)
            if client is not None:
                await warm_metadata(SessionLocal, client)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Title metadata warm-up failed: {error}")
        await asyncio.sleep(1200)
