"""Public title pages (/titles/<kind>/<slug>) and the /titles directory."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import date
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, title_metadata, title_pages
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..site_chrome import apply_site_chrome, message_page

router = APIRouter(tags=["titles"])
SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
CSS_VERSION = "20261002-profiles-1"
JS_VERSION = "20261001-titles-1"
SCHEMA_TYPES = {"movie": "Movie", "tv": "TVSeries", "anime": "TVSeries", "game": "VideoGame", "album": "MusicAlbum", "book": "Book"}
CREATOR_SCHEMA = {"movie": "director", "album": "byArtist", "book": "author"}
CREATOR_LABEL = {"movie": "Director", "album": "Artist", "book": "Author"}
KIND_PLURALS = {"movie": "Movies", "tv": "TV shows", "anime": "Anime", "game": "Games", "album": "Albums", "book": "Books"}
GUEST_LIST_MAX = 30
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
        item["description"] = _excerpt(metadata.get("description") or metadata.get("short_description"), 300)
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
        description = f'<div class="title-description">{_paragraphs(metadata["description"])}{credit}</div>'
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
        reviews = (f'<p class="title-empty">No public reviews yet. Track {_e(group.title)} on OmniTrackr and share yours '
                   f'— it will appear here.</p>')
    return (f'<section class="title-section" aria-labelledby="community-title"><h2 id="community-title">On OmniTrackr</h2>'
            f'<div class="title-stats">{"".join(tiles)}</div>'
            f'<h3 class="title-subhead">Member reviews</h3><div class="title-reviews">{reviews}</div></section>')


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


def render(group, summary: dict, metadata: Optional[dict], indexable: bool, signed_in: bool) -> str:
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
    reviews_link = (f'<a class="site-btn site-btn--ghost" href="#community-title">Read {len(summary["reviews"])} member review'
                    f'{"s" if len(summary["reviews"]) != 1 else ""}</a>' if summary["reviews"] else "")
    body = "".join([
        _trailer_html(group, metadata), _about_html(group, summary, metadata), _gallery_html(group, metadata),
        _tracks_html(metadata), _community_html(group, summary), _collections_html(summary), _related_html(summary),
    ])
    og_image = f'<meta property="og:image" content="{_e(image)}">' if image else ""
    ad_loader = '<script src="/static/ad-loader.js" defer></script>' if indexable and not signed_in else ""
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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
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
          <div class="title-hero__actions">{track}{reviews_link}<button type="button" class="site-btn site-btn--ghost" data-share data-share-title="{_e(group.title + year)} on OmniTrackr">Share</button></div>
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
    if slug != group.path.rsplit("/", 1)[1]:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(group.path, status_code=301)
    indexable = title_pages.is_indexable(summary, metadata)
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    response = strict_html_response(render(group, summary, metadata, indexable, signed_in))
    response.headers["Cache-Control"] = "private, no-store" if signed_in else "public, max-age=600"
    response.headers["Vary"] = "Cookie"
    if not indexable:
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
    robots = "index, follow" if total >= 8 else "noindex, follow"
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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
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
    <div class="site-wrap title-body">{"".join(sections) or '<p class="title-empty">Titles appear here once members start tracking them.</p>'}</div>
  </main>
  <!--SITE_FOOTER-->
</body>
</html>"""
    response = strict_html_response(apply_site_chrome(page))
    response.headers["Cache-Control"] = "public, max-age=900"
    if total < 8:
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
