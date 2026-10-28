"""Public title pages (/titles/<kind>/<slug>) and the /titles directory."""
from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import threading
import time
from datetime import date, datetime, timedelta
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import models, pick, review_spoilers, supporters, title_charts, title_metadata, title_pages, title_search, where_to_watch
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..progress import lock_progress_owner
from ..site_chrome import apply_site_chrome, editorial_picks, message_page

router = APIRouter(tags=["titles"])
SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
CSS_VERSION = "20261028-people-1"
JS_VERSION = "20261025-title-refresh-1"
SCHEMA_TYPES = {"movie": "Movie", "tv": "TVSeries", "anime": "TVSeries", "game": "VideoGame", "album": "MusicAlbum", "book": "Book",
                "manga": "Book", "podcast": "PodcastSeries"}
CREATOR_SCHEMA = {"movie": "director", "album": "byArtist", "book": "author", "manga": "author", "podcast": "author"}
CREATOR_LABEL = {"movie": "Director", "album": "Artist", "book": "Author", "manga": "Mangaka", "podcast": "Host"}
KIND_PLURALS = {"movie": "Movies", "tv": "TV shows", "anime": "Anime", "game": "Games", "album": "Albums", "book": "Books",
                "manga": "Manga", "podcast": "Podcasts"}
GUEST_LIST_MAX = 30
TAKE_DAYS = 60
FRIEND_RECS_VERSION = "20261024-friend-recs-1"
TAKE_TOKEN = re.compile(r"[A-Za-z0-9_-]{16,64}")
FINISHED_LABEL = {"movie": "watched", "tv": "watched", "anime": "watched", "game": "played", "album": "heard", "book": "read",
                  "manga": "read", "podcast": "heard"}
VERBS = {"movie": "watched", "tv": "watched", "anime": "watched", "game": "played", "album": "listened to", "book": "read",
         "manga": "read", "podcast": "listened to"}


def _singular(kind: str) -> str:
    label = title_pages.KINDS[kind][3]
    return label if kind == "tv" else label.lower()


def _plural(kind: str) -> str:
    return KIND_PLURALS[kind] if kind == "tv" else KIND_PLURALS[kind].lower()


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _script_json(data) -> str:
    """JSON for an inline <script> block: no "<", ">" or "&" that HTML could read as markup."""
    return (json.dumps(data, ensure_ascii=False)
            .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))


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


def _find_and_summarize(db: Session, kind: str, slug: str):
    group = title_pages.find(db, kind, slug)
    return (group, title_pages.summarize(db, group)) if group is not None else (None, None)


async def _load(request: Request, db: Session, kind: str, slug: str):
    # Database reads run in the threadpool, never on the event loop (see dependencies.get_current_user).
    group, summary = await run_in_threadpool(_find_and_summarize, db, kind, slug)
    if group is None:
        return None, None, None
    client = getattr(request.app.state, "external_api_client", None)
    metadata = await title_metadata.get_or_fetch(
        db, client, kind, group.normalized, group.title, group.year, _metadata_creator(kind, summary))
    summary["where"] = await where_to_watch.get_or_fetch(
        db, client, kind, group.normalized, group.title, group.year, metadata, wait=4)
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
    reviews = [r for r in summary["reviews"] if r["search_ready"] and not r.get("spoilers")][:3]
    if reviews:
        item["review"] = [{"@type": "Review", "author": {"@type": "Person", "name": r["username"]},
                           "reviewBody": _excerpt(r["review"], 500), "url": SITE_URL + r["url"],
                           **({"reviewRating": {"@type": "Rating", "ratingValue": r["rating"], "bestRating": 10, "worstRating": 0}}
                              if r["rating"] is not None else {})} for r in reviews]
    breadcrumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_URL}/"},
        {"@type": "ListItem", "position": 2, "name": "Titles", "item": f"{SITE_URL}/titles"},
        {"@type": "ListItem", "position": 3, "name": KIND_PLURALS[group.kind], "item": f"{SITE_URL}/titles/{group.kind}"},
        {"@type": "ListItem", "position": 4, "name": group.title, "item": canonical},
    ]}
    dump = _script_json
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
    links = summary.get("credit_links") or {}
    facts = "".join(f"<div><dt>{_e(label)}</dt><dd>{_fact_value_html(group.kind, label, value, links)}</dd></div>"
                    for label, value in rows if value)
    if not description and not facts:
        return ""
    return (f'<section class="title-section title-about" aria-labelledby="about-title"><h2 id="about-title">About {_e(group.title)}</h2>'
            f'{description}<dl class="title-facts">{facts}</dl></section>')


def _fact_value_html(kind: str, label: str, value, links: dict) -> str:
    """A fact's value, with each credited name that has a people or studio page linked to it."""
    from ..people_pages import FACT_ROLES, LIBRARY_ROLES, split_names
    role = (FACT_ROLES.get(kind) or {}).get(label, (None, None))[1]
    if role is None and label == CREATOR_LABEL.get(kind):
        role = LIBRARY_ROLES.get(kind)
    if not links or role is None:
        return _e(value)
    names = split_names(str(value), role)
    if not any(name in links for name in names):
        return _e(value)
    return ", ".join(f'<a href="{_e(links[name])}">{_e(name)}</a>' if name in links else _e(name) for name in names)


WHERE_HEADINGS = {"game": "Where to play {title}"}


def _where_html(group, summary: dict) -> str:
    """Services that stream, rent, sell or first aired the title, with the credits the data needs."""
    where = summary.get("where") or {}
    if not where.get("groups"):
        return ""
    rows = []
    for entry in where["groups"]:
        chips = []
        for provider in entry["providers"]:
            logo = (f'<img src="{_e(provider["logo"])}" alt="" width="28" height="28" loading="lazy">'
                    if provider.get("logo") else f'<span class="title-where__mono" aria-hidden="true">{_e(provider["name"][:1].upper())}</span>')
            inner = f'{logo}<span>{_e(provider["name"])}</span>'
            chips.append(f'<li><a class="title-where__provider" href="{_e(provider["url"])}" target="_blank" rel="noopener nofollow">{inner}</a></li>'
                         if provider.get("url") else f'<li><span class="title-where__provider">{inner}</span></li>')
        rows.append(f'<div class="title-where__group"><h3>{_e(entry["label"])}</h3><ul>{"".join(chips)}</ul></div>')
    heading = WHERE_HEADINGS.get(group.kind, "Where to watch {title}").format(title=group.title)
    notes = []
    if where.get("region"):
        checked = _pretty_date(where.get("fetched")) or where.get("fetched") or ""
        notes.append(f'<p class="title-where__note">Showing {_e(where["region"])} availability, checked {_e(checked)}. Services change their catalogues often.</p>')
    credits = where.get("credits") or []
    if credits:
        named = ", ".join(f'<a href="{_e(c["url"])}" rel="noopener">{_e(c["name"])}</a>' for c in credits)
        tmdb = " This product uses the TMDB API but is not endorsed or certified by TMDB." if where.get("justwatch") else ""
        notes.append(f'<p class="title-where__note">Data from {named}.{tmdb}</p>')
    more = ""
    if group.kind in where_to_watch.VIDEO_KINDS:
        more = (f'<a class="title-where__more" href="{_e(where.get("link") or where_to_watch.justwatch_search(group.title))}" '
                f'target="_blank" rel="noopener nofollow">Compare every service{" on JustWatch" if not where.get("link") else ""} ↗</a>')
    return (f'<section class="title-section title-where" aria-labelledby="where-title"><h2 id="where-title">{_e(heading)}</h2>'
            f'<div class="title-where__groups">{"".join(rows)}</div>{more}'
            f'{"".join(notes)}</section>')


def _tracks_html(metadata: dict) -> str:
    tracks = metadata.get("tracks") or []
    if not tracks:
        return ""
    rows = "".join(f'<li><span>{_e(track["name"])}</span><span>{_e(track.get("duration"))}</span></li>' for track in tracks)
    return f'<section class="title-section" aria-labelledby="tracks-title"><h2 id="tracks-title">Track list</h2><ol class="title-tracks">{rows}</ol></section>'

# The first few reviews show open; the rest stay on the page behind "Show more".
REVIEWS_OPEN = 6
REVIEWS_SHOWN = 30


def _review_card_html(review: dict, top: bool = False) -> str:
    rating = f'<span class="title-review__rating">{_e(review["rating"])}/10</span>' if review["rating"] is not None else ""
    author = (f'<a class="title-review__author" href="{_e(review["profile_url"])}">{_e(review["username"])}</a>'
              if review.get("profile_url") else _e(review["username"]))
    helpful = review.get("helpful", 0)
    badge = '<span class="title-review__top">Most helpful</span>' if top and helpful >= 2 else ""
    # Short reviews show in full here; only standalone reviews have a page of their own to link to.
    text = _excerpt(review["review"], 420) if review["search_ready"] else " ".join(review["review"].split())
    read = (f'<a class="title-review__more" href="{_e(review["url"])}">Read the full review <span aria-hidden="true">→</span></a>'
            if review["search_ready"] else "")
    count = _helpful_label(helpful) if helpful else ""
    body = review_spoilers.wrap(review, f'<p>{_e(text)}</p>{read}')
    return (f'<article class="title-review"><header><strong>{author}{supporters.chip_html(review.get("supporter"))}</strong>{rating}</header>'
            f'{badge}{body}'
            f'<footer class="title-review__actions"><div class="review-helpful" data-review-helpful data-category="{_e(review["category"])}" '
            f'data-review-id="{_e(review["id"])}"><button type="button" class="site-btn site-btn--ghost site-btn--sm review-helpful__button" '
            f'aria-pressed="false">👍 Helpful</button><span class="review-helpful__count" aria-live="polite">{_e(count)}</span></div>'
            f'{_report_html(review)}</footer></article>')


def _helpful_label(count: int) -> str:
    from .reviews import _helpful_label as label
    return label(count)


def _report_html(review: dict) -> str:
    from .reviews import _review_report_html
    return " ".join(_review_report_html(review).split())



def _community_html(group, summary: dict) -> str:
    verb = VERBS[group.kind]
    tiles = [f'<div><strong>{_e(summary["members"])}</strong><span>member{"s" if summary["members"] != 1 else ""} tracking it</span></div>',
             f'<div><strong>{_e(summary["finished"])}</strong><span>have {verb} it</span></div>']
    if summary.get("average_rating") is not None:
        tiles.append(f'<div><strong>{_e(summary["average_rating"])}/10</strong><span>average member rating</span></div>')
    else:
        tiles.append(f'<div><strong>{_e(summary["rated"])}</strong><span>member rating{"s" if summary["rated"] != 1 else ""}</span></div>')
    cards = [_review_card_html(review, top=index == 0) for index, review in enumerate(summary["reviews"][:REVIEWS_SHOWN])]
    if cards:
        reviews = f'<div class="title-reviews">{"".join(cards[:REVIEWS_OPEN])}</div>'
        more = len(cards) - REVIEWS_OPEN
        if more > 0:
            reviews += (f'<details class="title-reviews-more"><summary>Show {more} more review{"s" if more != 1 else ""}</summary>'
                        f'<div class="title-reviews">{"".join(cards[REVIEWS_OPEN:])}</div></details>')
    else:
        reviews = (f'<p class="title-empty">No public reviews yet. <a href="#write-review">Be the first to review '
                   f'{_e(group.title)}</a>.</p>')
    return (f'<section class="title-section" aria-labelledby="community-title"><h2 id="community-title">On OmniTrackr</h2>'
            f'{_verdict_html(group, summary)}<div class="title-stats">{"".join(tiles)}</div>{_spread_html(group, summary)}'
            f'<h3 class="title-subhead">Member reviews</h3>{reviews}</section>')


def _rank_html(group, summary: dict) -> str:
    rank = summary.get("chart_rank")
    if not rank:
        return ""
    return (f'<a class="title-rank" href="/titles/{_e(group.kind)}#rank-{_e(rank["rank"])}">'
            f'<strong>#{_e(rank["rank"])}</strong> highest-rated {_e(_singular(group.kind))} on OmniTrackr '
            f'<span aria-hidden="true">→</span></a>')


def _spread_html(group, summary: dict) -> str:
    """How member ratings split across bands (only once enough members have rated)."""
    spread = summary.get("spread")
    if not spread:
        return ""
    rows = "".join(
        f'<li><span class="title-spread__label">{_e(band["label"])}</span>'
        f'<span class="title-spread__bar"><span style="--w:{max(band["percent"], 1 if band["count"] else 0)}%"></span></span>'
        f'<span class="title-spread__value">{_e(band["percent"])}%</span></li>' for band in spread)
    return (f'<h3 class="title-subhead" id="spread-title">How members rate {_e(group.title)}</h3>'
            f'<ul class="title-spread" aria-labelledby="spread-title">{rows}</ul>'
            f'<p class="title-spread__note">From {_e(summary["rated"])} member ratings out of 10, one per member. '
            f'<a href="/titles/{_e(group.kind)}">See the {_e(_plural(group.kind))} chart</a>.</p>')


def _percent(part: int, whole: int) -> int:
    return round(100 * part / whole) if whole else 0


def _verdict_html(group, summary: dict) -> str:
    """A few plain sentences drawn from member data: what OmniTrackr members make of this title."""
    title, verb = group.title, VERBS[group.kind]
    sentences = []
    if summary.get("average_rating") is not None:
        line = f"Members rate {title} {summary['average_rating']}/10 on average across {summary['rated']} ratings"
        spread = summary.get("spread")
        if spread:
            high = sum(band["count"] for band in spread if band["label"] in ("9 to 10", "8 to 8.9"))
            line += f", and {_percent(high, summary['rated'])}% of them gave it 8 or more"
        sentences.append(line + ".")
        rank = summary.get("chart_rank")
        if rank:
            sentences.append(f"That makes it the #{rank['rank']} highest-rated {_singular(group.kind)} on OmniTrackr "
                             f"out of {rank['of']} on the chart.")
    members, finished = summary["members"], summary["finished"]
    if members >= title_pages.INDEX_MIN_MEMBERS:
        rest = members - finished
        line = f"{finished} of the {members} members tracking it have {verb} it ({_percent(finished, members)}%)"
        sentences.append(line + (f"; the other {rest} {'has' if rest == 1 else 'have'} it on their list." if rest else "."))
    if summary.get("recent_members"):
        sentences.append(f"{summary['recent_members']} members added it to their library in the last "
                         f"{title_pages.RECENT_DAYS} days.")
    written = len(summary["reviews"])
    if written:
        sentences.append(f"{written} member{'s have' if written != 1 else ' has'} shared a public review below.")
    if len(sentences) < 2:
        return ""
    return (f'<div class="title-verdict"><p class="title-verdict__label">The member verdict</p>'
            f'<p>{_e(" ".join(sentences))}</p></div>')


GLANCE_FACTS = ("Running time", "Episode length", "Episodes", "Seasons", "Average playtime", "Pages", "Length",
                "Tracks", "Studio", "Network", "Platforms")


def _glance_html(group, summary: dict, metadata: dict, signed_in: bool) -> str:
    """The sidebar summary: member numbers first, then the few facts people check before starting."""
    rows = []
    average = summary.get("average_rating")
    if average is not None:
        rows.append(f'<div class="title-glance__score" style="--score:{_e(round(float(average) * 10))}">'
                    f'<span class="title-glance__ring" aria-hidden="true"><strong>{_e(average)}</strong></span>'
                    f'<span><b>Member score</b><small>{_e(summary["rated"])} ratings out of 10</small></span></div>')
    members, finished = summary["members"], summary["finished"]
    if members >= title_pages.INDEX_MIN_MEMBERS:
        share = _percent(finished, members)
        rows.append(f'<div class="title-glance__meter"><span><b>{share}%</b> have {_e(VERBS[group.kind])} it</span>'
                    f'<span class="title-glance__bar"><span style="--w:{share}%"></span></span>'
                    f'<small>{_e(finished)} of {_e(members)} members tracking it</small></div>')
    facts = []
    rank = summary.get("chart_rank")
    if rank:
        facts.append(("Member chart", f'<a href="/titles/{_e(group.kind)}#rank-{_e(rank["rank"])}">#{_e(rank["rank"])} of {_e(rank["of"])} {_e(_plural(group.kind))}</a>'))
    if summary.get("recent_members"):
        facts.append(("Recently added", f'{_e(summary["recent_members"])} members in the last {title_pages.RECENT_DAYS} days'))
    release = _pretty_date(metadata.get("release_date")) or (str(group.year) if group.year else None)
    if release:
        facts.append(("Released" if group.kind not in ("tv", "anime") else "Premiered", _e(release)))
    if summary.get("creator") and group.kind in CREATOR_LABEL:
        facts.append((CREATOR_LABEL[group.kind], _e(summary["creator"])))
    found = {fact["label"]: fact["value"] for fact in metadata.get("facts") or [] if fact.get("value")}
    facts += [(label, _e(found[label])) for label in GLANCE_FACTS if label in found][:3]
    services = where_to_watch.names(summary.get("where"))
    if services:
        facts.append(("Where to play" if group.kind == "game" else "Where to watch",
                      f'<a href="#where-title">{_e(", ".join(services))}</a>'))
    if _genres(metadata):
        facts.append(("Genres", _e(", ".join(_genres(metadata)[:3]))))
    if not rows and not facts:
        return ""
    fact_html = "".join(f"<div><dt>{_e(label)}</dt><dd>{value}</dd></div>" for label, value in facts)
    if signed_in:
        cta = ('<a class="site-btn site-btn--ghost title-glance__cta" href="#write-review">Rate and review it</a>')
    else:
        cta = (f'<div class="title-glance__join"><strong>Track {_e(group.title)} with OmniTrackr</strong>'
               '<p>One free library for movies, shows, anime, games, music and books, with ratings, reviews and friends.</p>'
               '<a class="site-btn site-btn--primary title-glance__cta" href="/#signup">Start your free library</a></div>')
    return (f'<aside class="title-glance" aria-labelledby="glance-title"><h2 id="glance-title">At a glance</h2>'
            f'{"".join(rows)}{f"<dl>{fact_html}</dl>" if fact_html else ""}{cta}</aside>')


def _by_creator_html(group, summary: dict) -> str:
    items = summary.get("by_creator") or []
    creator = summary.get("creator")
    if not items or not creator:
        return ""
    link = (summary.get("credit_links") or {}).get(creator)
    more = (f'<a href="{_e(link)}">Every {_e(creator)} title, ranked <span aria-hidden="true">→</span></a>' if link else "")
    return (f'<section class="title-section" aria-labelledby="creator-title"><div class="title-section__head">'
            f'<h2 id="creator-title">More from {_e(creator)}</h2>{more}</div>'
            f'<div class="title-related-grid">{_related_cards(items)}</div></section>')


def _section_nav(sections: list[tuple[str, str, str]]) -> str:
    """Jump links to the sections this page actually has."""
    links = "".join(f'<a href="#{_e(anchor)}">{_e(label)}</a>' for html, anchor, label in sections if html)
    if links.count("<a ") < 3:
        return ""
    return f'<nav class="title-tabs" aria-label="On this page"><div class="site-wrap title-tabs__inner">{links}</div></nav>'


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
            '<label class="title-write__public"><input id="titleReviewSpoilers" name="spoilers" type="checkbox"> Contains spoilers</label>'
            '</div>'
            '<p class="title-write__note">Saving adds the title to your library if it isn\'t there yet. You can edit or hide the review any time.</p>'
            '<button type="submit" class="site-btn site-btn--primary">Save review</button>'
            '<p class="title-write__status" role="status" aria-live="polite"></p></form>'
        )
    else:
        from urllib.parse import quote
        query = f"?take={take[0].token}" if take else ""
        signin = "/?next=" + quote(f"{group.path}{query}#write-review", safe="") + "#landing-auth"
        action = (f'<div class="title-write__actions"><a class="site-btn site-btn--primary" rel="nofollow" href="{_e(signin)}">Sign in to write a review</a>'
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


def _related_cards(items: list) -> str:
    cards = ""
    for item in items:
        art = (f'<img src="{_e(item["image"])}" alt="" loading="lazy">' if item.get("image")
               else f'<span>{_e(item["title"][:1].upper())}</span>')
        year = f' · {item["year"]}' if item.get("year") else ""
        cards += (f'<a class="title-related" href="{_e(item["url"])}"><span class="title-related__art">{art}</span>'
                  f'<strong>{_e(item["title"])}</strong><small>{_e(item["label"])}{_e(year)}</small></a>')
    return cards


def _related_html(summary: dict) -> str:
    if not summary["related"]:
        return ""
    cards = _related_cards(summary["related"])
    return f'<section class="title-section" aria-labelledby="related-title"><h2 id="related-title">Members who track this also track</h2><div class="title-related-grid">{cards}</div></section>'


def _if_you_liked_html(group) -> str:
    """A link to the hand-written "If you liked" guide about this title, when one exists."""
    from .. import if_you_liked
    slug = if_you_liked.for_title(group.kind, group.title)
    if slug is None:
        return ""
    guide = if_you_liked.guide(slug)
    names = ", ".join(item["title"] for item in guide["picks"][:3])
    return (f'<section class="title-section title-liked" aria-labelledby="liked-title"><h2 id="liked-title">Loved it? Here is what to try next</h2>'
            f'<p>Our guide picks {len(guide["picks"])} titles that share what made {_e(guide["anchor"]["title"])} work, '
            f'across formats, including {_e(names)}.</p>'
            f'<a class="site-btn site-btn--ghost" href="{_e(if_you_liked.path(slug))}">If you liked {_e(guide["anchor"]["title"])} →</a></section>')


def _in_order_html(group) -> str:
    """Where this title sits in the "In order" guides that include it."""
    from .. import in_order
    found = in_order.for_title(group.kind, group.title, getattr(group, "year", None))
    if not found:
        return ""
    cards = []
    for slug, item in found[:2]:
        guide = in_order.guide(slug)
        first = guide["orders"][0]
        where = (f'#{first["ids"].index(item["id"]) + 1} of {len(first["ids"])} in the order we recommend'
                 if item["id"] in first["ids"] else f'one of {len(guide["entries"])} entries')
        also = "the other orders, what you can skip" if len(guide["orders"]) > 1 else "what you can skip"
        cards.append(f'<p>{_e(group.title)} is {_e(where)} in our {_e(guide["name"])} guide, which also covers '
                     f'{also} and where to start.</p>'
                     f'<a class="site-btn site-btn--ghost" href="{_e(in_order.path(slug))}#{_e(in_order.anchor_id(item))}">'
                     f'{_e(guide["name"])} in order →</a>')
    return (f'<section class="title-section title-in-order" aria-labelledby="in-order-title"><h2 id="in-order-title">Part of a series? Here is the order</h2>'
            f'{"".join(cards)}</section>')


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
    streaming = where_to_watch.stream_names(summary.get("where"), limit=2)
    if streaming and group.kind in where_to_watch.VIDEO_KINDS:
        description_bits.append("where to watch it (" + " and ".join(streaming) + ")")
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
    recommend = (f'<button type="button" class="site-btn site-btn--ghost" data-friend-rec-open '
                 f'data-rec-kind="{_e(group.kind)}" data-rec-slug="{_e(group.path.rsplit("/", 1)[1])}" '
                 f'data-rec-title="{_e(group.title)}">Recommend to a friend</button>' if signed_in else "")
    reviews_link = (f'<a class="site-btn site-btn--ghost" href="#community-title">Read {len(summary["reviews"])} member review'
                    f'{"s" if len(summary["reviews"]) != 1 else ""}</a>' if summary["reviews"]
                    else '<a class="site-btn site-btn--ghost" href="#write-review">Write the first review</a>')
    # Our own content first: member reviews and stats, then collections and "also track".
    sections = [
        (_community_html(group, summary), "community-title", "Reviews"),
        (_write_review_html(group, summary, signed_in, take), "write-review", "Write a review"),
        (summary.get("discussions_html", ""), "discussions-title", "Discussions"),
        (_trailer_html(group, metadata), "trailer-title", "Trailer"),
        (_where_html(group, summary), "where-title", "Where to play" if group.kind == "game" else "Where to watch"),
        (_about_html(group, summary, metadata), "about-title", "About"),
        (_if_you_liked_html(group), "liked-title", "What to try next"),
        (_in_order_html(group), "in-order-title", "Series order"),
        (_collections_html(summary), "collections-title", "Collections"),
        (_related_html(summary), "related-title", "Members also track"),
        (_by_creator_html(group, summary), "creator-title", f"More from {summary.get('creator') or ''}".strip()),
        (_gallery_html(group, metadata), "gallery-title", "Screenshots" if group.kind == "game" else "Images"),
        (_tracks_html(metadata), "tracks-title", "Track list"),
    ]
    body = "".join(html for html, _, _ in sections)
    nav = _section_nav([section for section in sections if section[1] != "write-review"])
    glance = _glance_html(group, summary, metadata, signed_in)
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
  <link rel="stylesheet" href="/static/discussions.css?v=20261028-discussions-1">
  <script src="/static/share.js?v=20261004-share-1" defer></script>
  <script src="/static/review_report.js?v=20261020-title-reviews-1" defer></script>
  {'' if signed_in else '<script src="/static/guest-list.js?v=20261012-hero-search-1" defer></script>'}
  {f'<link rel="stylesheet" href="/static/friend-recs.css?v={FRIEND_RECS_VERSION}"><script src="/static/friend-recs.js?v={FRIEND_RECS_VERSION}" defer></script>' if signed_in else ''}
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
          <nav class="title-crumbs" aria-label="Breadcrumb"><a href="/titles">Titles</a> <span aria-hidden="true">/</span> <a href="/titles/{_e(group.kind)}">{_e(KIND_PLURALS[group.kind])}</a></nav>
          <h1>{_e(group.title)}{f' <span class="title-hero__year">{_e(group.year)}</span>' if group.year else ''}</h1>
          <p class="title-hero__meta">{_e(meta_line)}</p>
          {_rank_html(group, summary)}
          {f'<p class="title-hero__lead">{_e(lead[:1].upper() + lead[1:])}</p>' if lead else ''}
          <div class="title-hero__chips">{genres}</div>
          {_scores_html(summary, metadata)}
          <div class="title-hero__actions">{track}{reviews_link}{recommend}{ask}<button type="button" class="site-btn site-btn--ghost" data-share data-share-title="{_e(group.title + year)} on OmniTrackr">Share</button></div>
          <p class="title-hero__status" role="status" aria-live="polite"></p>
          {_links_html(metadata)}
        </div>
      </div>
    </section>
    {nav}
    <div class="site-wrap title-body{' title-body--glance' if glance else ''}">
      {glance}
      <div class="title-main">
        {body}
      </div>
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

    def finish():
        summary["chart_rank"] = title_charts.rank_of(db, kind, group.path)
        from .title_discussions import title_section_html
        summary["discussions_html"] = title_section_html(db, group)
        from .. import people_pages
        try:
            summary["credit_links"] = people_pages.title_links(db, kind, metadata, summary.get("creator"),
                                                               bool(summary.get("by_creator")))
        except Exception:
            db.rollback()  # The page still shows the names, just without links.
        return render(group, summary, metadata, indexable, signed_in, _take_for(db, token, group))

    response = strict_html_response(await run_in_threadpool(finish))
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
    lock_progress_owner(db, user.id)
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
    lock_progress_owner(db, user.id)
    group = title_pages.find(db, kind, slug)
    if group is None:
        raise HTTPException(404, "Title not found")
    state, record = add_group_to_library(db, user, group)
    result = {"state": state, "title": record.title, "category": title_pages.KINDS[kind][2]}
    db.commit()
    return result


class TitleReview(BaseModel):
    review: str = Field(..., min_length=1, max_length=10000)
    rating: Optional[float] = Field(None, ge=0, le=10)
    public: bool = True
    # None leaves an existing spoiler flag alone (older pages that predate the checkbox).
    spoilers: Optional[bool] = None
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
        return {"in_library": False, "review": "", "rating": None, "public": True, "spoilers": False}
    return {"in_library": True, "review": item.review or "", "rating": item.rating, "public": bool(item.review_public),
            "spoilers": review_spoilers.is_flagged(db, title_pages.KINDS[kind][1], item)}


@router.put("/api/titles/{kind}/{slug}/review")
def save_title_review(kind: str, slug: str, payload: TitleReview, request: Request, response: Response,
                      user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Write or update the member's review from the title page (adds the title to their library if needed)."""
    from ..review_quality import evaluate_public_review
    from .reviews import PUBLIC_REVIEW_DETAIL_MIN_CHARS, PUBLIC_REVIEW_MIN_CHARS
    response.headers["Cache-Control"] = "private, no-store"
    lock_progress_owner(db, user.id)
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
    if payload.spoilers is not None:
        db.flush()
        review_spoilers.set_flag(db, title_pages.KINDS[kind][1], item, payload.spoilers)
    item_id = item.id
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
        "review_url": f"/reviews/{item_id}?category={review_category}" if standalone else None,
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
    lock_progress_owner(db, user.id)
    added, existing, missing = [], [], 0
    seen = set()
    for item in payload.items:
        key = (item.kind, item.slug)
        if key in seen:
            continue
        seen.add(key)
        group = title_pages.find(db, item.kind, item.slug) if item.kind in title_pages.KINDS else None
        curated = pick.find(item.kind, item.slug) if group is None else None
        if group is None and curated is None:
            # An OmniTrackr Daily answer no member tracks yet.
            from .. import daily
            curated = daily.find_answer(item.kind, item.slug)
        if group is None and curated is None:
            # An entry saved from an "In order" guide that no member tracks yet.
            from .. import in_order
            curated = in_order.find(item.kind, item.slug)
        if group is None and curated is None:
            missing += 1
            continue
        if group is not None:
            state, record = add_group_to_library(db, user, group)
        else:
            # A Pick for me suggestion no member tracks yet: copy the editors' title, year and creator.
            state, record = pick.add_to_library(db, user, curated)
        entry = {"title": record.title, "category": title_pages.KINDS[item.kind][2]}
        (added if state == "created" else existing).append(entry)
    db.commit()
    if added:
        from .. import funnel
        funnel.record("guest_list_imported", request)
    return {"added": added, "existing": existing, "missing": missing}


@router.get("/api/where-to-watch")
async def where_to_watch_lookup(request: Request, response: Response,
                                kind: str = Query(..., max_length=10),
                                title: str = Query(..., min_length=1, max_length=300),
                                year: Optional[int] = Query(None, ge=1800, le=2200),
                                user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Where a library title streams or sells, for the member's own rows (works for private libraries too)."""
    response.headers["Cache-Control"] = "private, no-store"
    if kind not in where_to_watch.KINDS:
        raise HTTPException(404, "Not available for this kind of title")
    display = " ".join(title.split())
    normalized = title_pages.normalize(display)
    if not normalized:
        raise HTTPException(422, "A title is required")
    client = getattr(request.app.state, "external_api_client", None)
    metadata = await title_metadata.get_or_fetch(db, client, kind, normalized, display, year)
    where = await where_to_watch.get_or_fetch(db, client, kind, normalized, display, year, metadata, wait=8) or {}
    return {
        "kind": kind,
        "title": display,
        "groups": where.get("groups") or [],
        "region": where.get("region"),
        "fetched": where.get("fetched"),
        "credits": where.get("credits") or [],
        "tmdb_notice": bool(where.get("justwatch")),
        "more": (where.get("link") or where_to_watch.justwatch_search(display)) if kind in where_to_watch.VIDEO_KINDS else None,
    }


@router.get("/api/titles/search")
def search_titles(request: Request, response: Response, q: str = Query("", max_length=200), db: Session = Depends(get_db)):
    """Homepage search over titles members track; anyone can use it, no account needed."""
    response.headers["Cache-Control"] = "public, max-age=300"
    return {"results": title_search.search(title_search.index(db), q)}


TITLES_INDEX_CACHE_SECONDS = 10 * 60
_titles_index_cache: dict = {"at": 0.0, "page": None}
_titles_index_lock = threading.Lock()


@router.get("/titles", include_in_schema=False)
def titles_index(request: Request, db: Session = Depends(get_db)):
    """The /titles directory, rebuilt at most every TITLES_INDEX_CACHE_SECONDS.

    It is the same for every visitor, and counting members per title across all six
    library tables takes most of a second.
    """
    if os.getenv("TESTING", "").lower() == "true":  # Tests change data between requests.
        page, index_directory = _titles_index_page(db)
    else:
        with _titles_index_lock:
            if (_titles_index_cache["page"] is None
                    or time.monotonic() - _titles_index_cache["at"] >= TITLES_INDEX_CACHE_SECONDS):
                _titles_index_cache["page"] = _titles_index_page(db)
                _titles_index_cache["at"] = time.monotonic()
            page, index_directory = _titles_index_cache["page"]
    response = strict_html_response(page)
    response.headers["Cache-Control"] = "public, max-age=900"
    if not index_directory:
        response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


def _titles_index_page(db: Session) -> tuple[str, bool]:
    sections, total, listed = [], 0, []
    for kind in title_pages.KINDS:
        items = title_pages.popular(db, kind, limit=18)
        total += len(items)
        if not items:
            continue
        cards = ""
        for item in items:
            listed.append(item)
            art = (f'<img src="{_e(item["image"])}" alt="" loading="lazy">' if item.get("image")
                   else f'<span>{_e(item["title"][:1].upper())}</span>')
            year = f" · {item['year']}" if item.get("year") else ""
            cards += (f'<a class="title-related" href="{_e(item["url"])}"><span class="title-related__art">{art}</span>'
                      f'<strong>{_e(item["title"])}</strong><small>{_e(item["members"])} members{_e(year)}</small></a>')
        sections.append(f'<section class="title-section" id="{kind}" aria-labelledby="{kind}-heading">'
                        f'<div class="title-section__head"><h2 id="{kind}-heading">{_e(KIND_PLURALS[kind])}</h2>'
                        f'<a href="/titles/{kind}">Highest-rated {_e(_plural(kind))} <span aria-hidden="true">→</span></a></div>'
                        f'<div class="title-related-grid">{cards}</div></section>')
    if not sections:
        sections.append(editorial_picks(
            "Looking for something to start?",
            "Titles appear here as members track them. Meanwhile, these OmniTrackr guides compare picks across "
            "every medium and explain who each one suits.",
        ))
    # The directory itself is mostly links; it's only worth indexing once enough titles have member reviews.
    index_directory = len(title_pages.reviewed_titles(db)) >= 8
    robots = "index, follow" if index_directory else "noindex, follow"
    index_description = ("The movies, TV shows, anime, games, books and albums OmniTrackr members track most, "
                         "each with details, trailers, scores and member reviews.")
    item_list = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Popular titles on OmniTrackr",
                 "url": f"{SITE_URL}/titles", "description": index_description,
                 "mainEntity": {"@type": "ItemList", "itemListElement": [
                     {"@type": "ListItem", "position": position, "name": item["title"], "url": SITE_URL + item["url"]}
                     for position, item in enumerate(listed[:100], start=1)]}}
    item_list_json = _script_json(item_list)
    structured = f'<script type="application/ld+json">{item_list_json}</script>' if listed else ""
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Popular titles on OmniTrackr: movies, shows, anime, games, books and albums</title>
  <meta name="description" content="{_e(index_description)}">
  <meta name="robots" content="{robots}">
  <link rel="canonical" href="{SITE_URL}/titles">
  <meta property="og:title" content="Popular titles on OmniTrackr">
  <meta property="og:description" content="{_e(index_description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{SITE_URL}/titles">
  <meta property="og:site_name" content="OmniTrackr">
  <meta property="og:image" content="{SITE_URL}/omnitrackr_vortex.png">
  <meta name="twitter:card" content="summary">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">
  <link rel="stylesheet" href="/static/title-page.css?v={CSS_VERSION}">
  {structured}
</head>
<body class="site title-page">
  <!--SITE_NAV:titles-->
  <main>
    <section class="site-hero"><div class="site-wrap">
      <p class="site-eyebrow">Titles</p>
      <h1>What OmniTrackr members are tracking</h1>
      <p>The most-tracked movies, shows, anime, games, books and albums on OmniTrackr. Every title has its details, trailer, scores and what members thought of it.</p>
      <nav class="title-chart__pills" aria-label="Browse by credit"><a class="site-chip" href="/people">Directors, actors and authors</a><a class="site-chip" href="/studios">Studios and developers</a></nav>
    </div></section>
    <div class="site-wrap title-body">{"".join(sections)}</div>
  </main>
  <!--SITE_FOOTER-->
</body>
</html>"""
    return apply_site_chrome(page), index_directory


def _chart_entry_html(entry: dict) -> str:
    art = (f'<img src="{_e(entry["image"])}" alt="" loading="lazy" width="72" height="108">' if entry.get("image")
           else f'<span>{_e(entry["title"][:1].upper())}</span>')
    meta = " · ".join(filter(None, [str(entry["year"]) if entry.get("year") else None, entry.get("creator")]))
    counts = (f'{entry["rated"]} member ratings · {entry["members"]} tracking · '
              f'{entry["finished"]} {FINISHED_LABEL[entry["kind"]]} it')
    quote = ""
    if entry.get("quote"):
        q = entry["quote"]
        who = (f'<a href="{_e(q["profile_url"])}">{_e(q["username"])}</a>' if q.get("profile_url") else _e(q["username"]))
        quote = (f'<blockquote class="title-chart__quote"><p>“{_e(q["text"])}”</p>'
                 f'<footer>{who} · <a href="{_e(q["url"])}">full review</a></footer></blockquote>')
    return (f'<li class="title-chart__entry" id="rank-{entry["rank"]}">'
            f'<span class="title-chart__rank" aria-label="Rank {entry["rank"]}">{entry["rank"]}</span>'
            f'<a class="title-chart__art" href="{_e(entry["url"])}" tabindex="-1" aria-hidden="true">{art}</a>'
            f'<div class="title-chart__body"><h3><a href="{_e(entry["url"])}">{_e(entry["title"])}</a></h3>'
            f'{f"<p class=title-chart__meta>{_e(meta)}</p>" if meta else ""}'
            f'<p class="title-chart__counts">{_e(counts)}</p>{quote}</div>'
            f'<span class="title-chart__score"><strong>{_e(entry["average"])}</strong><small>/10</small></span></li>')


@router.get("/titles/{kind}", include_in_schema=False)
def title_chart(kind: str, request: Request, db: Session = Depends(get_db)):
    """Member charts: the highest-rated and most-tracked titles of one kind."""
    if kind not in title_pages.KINDS:
        raise HTTPException(404, "Unknown title type")
    data = title_charts.chart(db, kind)
    plural, singular = _plural(kind), _singular(kind)
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    canonical = f"{SITE_URL}/titles/{kind}"
    heading = f"The highest-rated {plural} on OmniTrackr"
    ranked = data["ranked"]
    description = (f"The {len(ranked)} {plural} OmniTrackr members rate highest, from {data['ratings']} member ratings, "
                   "with what members wrote about them." if ranked else
                   f"The {plural} OmniTrackr members rate highest and track most, updated as members rate what they finish.")
    pills = "".join(
        f'<a class="site-chip{" title-chart__pill--on" if other == kind else ""}" href="/titles/{other}"'
        f'{" aria-current=page" if other == kind else ""}>{_e(KIND_PLURALS[other])}</a>' for other in title_pages.KINDS)
    if ranked:
        chart_html = (f'<section class="title-section" aria-labelledby="chart-heading"><h2 id="chart-heading">Top {len(ranked)} by member rating</h2>'
                      f'<ol class="title-chart">{"".join(_chart_entry_html(entry) for entry in ranked)}</ol></section>')
    else:
        chart_html = (f'<section class="title-section"><h2>Not enough ratings to chart yet</h2>'
                      f'<p class="title-empty">A {_e(singular)} joins this chart once {title_charts.CHART_MIN_RATINGS} members '
                      f'have rated it. Rate the {_e(plural)} you have finished and they will start to appear here.</p></section>')
    tracked = ""
    if data["tracked"]:
        cards = ""
        for entry in data["tracked"]:
            art = (f'<img src="{_e(entry["image"])}" alt="" loading="lazy">' if entry.get("image")
                   else f'<span>{_e(entry["title"][:1].upper())}</span>')
            year = f" · {entry['year']}" if entry.get("year") else ""
            cards += (f'<a class="title-related" href="{_e(entry["url"])}"><span class="title-related__art">{art}</span>'
                      f'<strong>{_e(entry["title"])}</strong><small>{_e(entry["members"])} members{_e(year)}</small></a>')
        tracked = (f'<section class="title-section" aria-labelledby="tracked-heading"><h2 id="tracked-heading">Most tracked {_e(plural)}</h2>'
                   f'<div class="title-related-grid">{cards}</div></section>')
    mean = f" The average member rating across every {_e(singular)} is {_e(data['mean'])} out of 10." if data["mean"] is not None else ""
    method = (
        '<section class="title-section title-chart__method" aria-labelledby="method-heading"><h2 id="method-heading">How this chart works</h2>'
        f'<p>Every rating here comes from an OmniTrackr member who rated a {_e(singular)} in their own library, out of 10. '
        f'Each member counts once per title, and a {_e(singular)} needs at least {title_charts.CHART_MIN_RATINGS} member ratings '
        'to chart.</p>'
        '<p>Titles are ranked by a weighted average rather than a plain one. A title with only a few ratings is pulled '
        'toward the typical rating until more members weigh in, so a handful of perfect scores does not automatically '
        f'outrank dozens of high ones.{mean}</p>'
        '<p>Members who keep a category private are never counted, our editors\' account is left out, and the chart never '
        'shows who rated what. Quotes come from reviews members chose to make public. The chart refreshes every few minutes.</p>'
        '</section>')
    if signed_in:
        cta = ('<section class="title-section title-write"><h2>Move a favorite up the chart</h2>'
               '<p class="title-write__lead">Rate the titles you have finished in your library and your ratings count here.</p>'
               '<div class="title-write__actions"><a class="site-btn site-btn--primary" href="/">Open my library</a></div></section>')
    else:
        cta = ('<section class="title-section title-write"><h2>Make your ratings count</h2>'
               f'<p class="title-write__lead">Track the {_e(plural)} you watch, play, read and listen to, rate them out of 10, '
               'and your ratings help decide what tops these charts. Free, and your library stays private unless you share it.</p>'
               '<div class="title-write__actions"><a class="site-btn site-btn--primary" href="/#signup">Create a free account</a>'
               '<a class="site-btn site-btn--ghost" href="/titles">Browse popular titles</a></div></section>')
    indexable = data["indexable"]
    robots = "index, follow" if indexable else "noindex, follow"
    structured = ""
    if ranked:
        item_list = {"@context": "https://schema.org", "@type": "ItemList", "name": heading, "url": canonical,
                     "numberOfItems": len(ranked), "itemListOrder": "https://schema.org/ItemListOrderDescending",
                     "itemListElement": [{"@type": "ListItem", "position": entry["rank"], "name": entry["title"],
                                          "url": SITE_URL + entry["url"]} for entry in ranked]}
        structured = f'<script type="application/ld+json">{_script_json(item_list)}</script>'
    breadcrumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_URL}/"},
        {"@type": "ListItem", "position": 2, "name": "Titles", "item": f"{SITE_URL}/titles"},
        {"@type": "ListItem", "position": 3, "name": KIND_PLURALS[kind], "item": canonical}]}
    structured += f'<script type="application/ld+json">{_script_json(breadcrumbs)}</script>'
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_e(f"Highest-rated {plural} by OmniTrackr members")}</title>
  <meta name="description" content="{_e(_excerpt(description, 158))}">
  <meta name="robots" content="{robots}">
  <link rel="canonical" href="{_e(canonical)}">
  <meta property="og:title" content="{_e(heading)}">
  <meta property="og:description" content="{_e(_excerpt(description, 200))}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{_e(canonical)}">
  <meta property="og:site_name" content="OmniTrackr">
  <meta property="og:image" content="{SITE_URL}/omnitrackr_vortex.png">
  <meta name="twitter:card" content="summary">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">
  <link rel="stylesheet" href="/static/title-page.css?v={CSS_VERSION}">
  {structured}
</head>
<body class="site title-page">
  <!--SITE_NAV:-->
  <main>
    <section class="site-hero"><div class="site-wrap">
      <nav class="title-crumbs" aria-label="Breadcrumb"><a href="/titles">Titles</a> <span aria-hidden="true">/</span> {_e(KIND_PLURALS[kind])}</nav>
      <p class="site-eyebrow">Member charts</p>
      <h1>{_e(heading)}</h1>
      <p>{_e(description)}</p>
      <nav class="title-chart__pills" aria-label="Charts by type">{pills}</nav>
    </div></section>
    <div class="site-wrap title-body">{chart_html}{cta}{tracked}{method}</div>
  </main>
  <!--SITE_FOOTER-->
</body>
</html>"""
    response = strict_html_response(apply_site_chrome(page))
    response.headers["Cache-Control"] = "private, no-store" if signed_in else "public, max-age=600"
    response.headers["Vary"] = "Cookie"
    if not indexable:
        response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


def sitemap_entries(db: Session, limit: int = 500) -> list[str]:
    """Indexable title pages for the sitemap (metadata must already be cached)."""
    seen, paths = set(), []
    candidates = title_pages.reviewed_titles(db)
    for kind in title_pages.KINDS:
        candidates += [dict(item) for item in title_pages.popular(db, kind, limit=150, min_members=title_pages.INDEX_MIN_MEMBERS)]
    # Only reviewed rows: a title page is indexable only with a search-ready public review.
    groups = {kind: title_pages.find_many(db, kind, [c["url"].rsplit("/", 1)[1] for c in candidates if c["kind"] == kind],
                                          reviewed_only=True)
              for kind in title_pages.KINDS}
    for candidate in candidates:
        if candidate["url"] in seen or len(paths) >= limit:
            continue
        seen.add(candidate["url"])
        group = groups[candidate["kind"]].get(candidate["url"].rsplit("/", 1)[1])
        if group is None:
            continue
        summary = title_pages.summarize(db, group, page_sections=False)
        metadata, _ = title_metadata.cached(db, title_metadata.cache_key(group.kind, group.normalized, group.year))
        if title_pages.is_indexable(summary, metadata):
            paths.append(group.path)
    return paths


async def warm_metadata(session_factory, client, batch: int = 8) -> int:
    """Fetch facts for titles that are likely to get traffic but aren't cached yet."""
    db = session_factory()
    fetched = 0

    def candidates_of():
        found = title_pages.reviewed_titles(db)
        for kind in title_pages.KINDS:
            found += title_pages.popular(db, kind, limit=60, min_members=2)
        return found

    def stale_group(candidate):
        group = title_pages.find(db, candidate["kind"], candidate["url"].rsplit("/", 1)[1])
        if group is None:
            return None, None
        _, fresh = title_metadata.cached(db, title_metadata.cache_key(group.kind, group.normalized, group.year))
        if fresh and group.kind in where_to_watch.KINDS:
            _, fresh = where_to_watch.cached(db, where_to_watch.cache_key(group.kind, group.normalized, group.year))
        if fresh:
            return None, None
        return group, title_pages.summarize(db, group, page_sections=False).get("creator")

    try:
        # Database reads run in the threadpool so this background task never stalls page requests.
        for candidate in await run_in_threadpool(candidates_of):
            if fetched >= batch:
                break
            group, creator = await run_in_threadpool(stale_group, candidate)
            if group is None:
                continue
            metadata = await title_metadata.get_or_fetch(db, client, group.kind, group.normalized, group.title, group.year,
                                                         creator, wait=20)
            await where_to_watch.get_or_fetch(db, client, group.kind, group.normalized, group.title, group.year, metadata, wait=20)
            fetched += 1
            await asyncio.sleep(2)  # Be gentle with Wikipedia and friends.
    finally:
        db.close()
    return fetched


def _backfill_credits(session_factory) -> None:
    """Credits for facts cached before the people and studio pages existed."""
    from .. import people_pages
    db = session_factory()
    try:
        people_pages.backfill(db)
    finally:
        db.close()


async def warm_loop(app) -> None:
    from ..database import SessionLocal
    await asyncio.sleep(240)
    while True:
        try:
            client = getattr(app.state, "external_api_client", None)
            if client is not None:
                await warm_metadata(SessionLocal, client)
            await run_in_threadpool(_backfill_credits, SessionLocal)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Title metadata warm-up failed: {error}")
        await asyncio.sleep(1200)
