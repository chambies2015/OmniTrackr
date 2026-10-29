"""Opt-in public profiles: /u/<username>, its share card, and the owner's settings."""
from __future__ import annotations

import hashlib
import io
import json
import os
import threading
from collections import OrderedDict
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..integer_bounds import PositiveDatabaseId
from .. import funnel, models, profile_widgets, public_profiles, review_spoilers, supporters
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..site_chrome import apply_site_chrome

router = APIRouter(tags=["profiles"])
SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
CSS_VERSION = "20261028-members-1"
TITLE_CSS_VERSION = "20261009-take-1"


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _excerpt(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def _rating(value) -> str:
    if value is None:
        return ""
    return f"{value:g}" if isinstance(value, float) else str(value)


class ProfileSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    bio: Optional[str] = Field(None, max_length=2000)
    show_stats: Optional[bool] = None
    show_favorites: Optional[bool] = None
    show_reviews: Optional[bool] = None
    show_collections: Optional[bool] = None
    show_diary: Optional[bool] = None


@router.get("/api/profile/settings")
def profile_settings(response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return public_profiles.settings_payload(user, public_profiles.get_settings(db, user.id), db)


@router.put("/api/profile/settings")
def update_profile_settings(
    payload: ProfileSettingsUpdate,
    request: Request,
    response: Response,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "private, no-store"
    changes = payload.model_dump(exclude_unset=True)
    try:
        profile = public_profiles.save_settings(db, user, changes)
    except public_profiles.BioError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error))
    _CARD_CACHE.clear_user(user.id)
    profile_widgets.CACHE.clear_user(user.id)
    return public_profiles.settings_payload(user, profile, db)


class ShowcasePick(BaseModel):
    category: str = Field(..., max_length=16)
    id: PositiveDatabaseId


class ShowcaseUpdate(BaseModel):
    items: list[ShowcasePick] = Field(default_factory=list, max_length=public_profiles.SUPPORTER_SHOWCASE_LIMIT)


@router.get("/api/profile/showcase/search")
def showcase_search(response: Response, q: str = "", user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """Titles from the member's own library to pin to their profile."""
    response.headers["Cache-Control"] = "private, no-store"
    return {"results": public_profiles.showcase_search(db, user, q[:200])}


@router.put("/api/profile/showcase")
def update_showcase(payload: ShowcaseUpdate, response: Response, user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    try:
        items = public_profiles.save_showcase(db, user, [pick.model_dump() for pick in payload.items])
    except public_profiles.ShowcaseError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error))
    _CARD_CACHE.clear_user(user.id)
    profile_widgets.CACHE.clear_user(user.id)
    return {"showcase": items, "showcase_limit": public_profiles.showcase_limit(db, user)}


# ---------------------------------------------------------------- page

def _avatar_html(user: models.User) -> str:
    if user.profile_picture_data:
        return f'<img class="profile-hero__avatar" src="/profile-pictures/{user.id}" alt="" width="120" height="120">'
    initial = (user.username or "?")[:1].upper()
    return f'<div class="profile-hero__avatar profile-hero__avatar--empty" aria-hidden="true">{_e(initial)}</div>'


def _supporter_html(view) -> str:
    if not view.supporter:
        return ""
    since = view.supporter.get("since")
    founding = bool(view.supporter.get("founding"))
    who = "Founding supporter of OmniTrackr" if founding else "Supporting OmniTrackr"
    title = f"{who} on Ko-fi since {since:%B} {since.year}" if since else "Supports OmniTrackr on Ko-fi"
    label = supporters.level_label(founding, int(view.supporter.get("months") or 0))
    classes = "profile-supporter profile-supporter--founding" if founding else "profile-supporter"
    badge = (f'<a class="{classes}" href="/supporters" title="{_e(title)}">'
             f'<span aria-hidden="true">{"★" if founding else "♥"}</span> {_e(label)}</a>')
    tier = view.supporter.get("tier")
    if tier:
        badge += (f' <a class="profile-member" href="/supporters#tiers-heading" title="Monthly {_e(tier)} member on Ko-fi">'
                  f'{_e(tier)} member</a>')
    return badge


def _hero_class(view) -> str:
    accent = (view.supporter or {}).get("accent")
    classes = "profile-hero"
    if view.supporter:
        classes += " profile-hero--supporter"
    if accent:
        classes += f" profile-hero--accent-{accent}"
    if (view.supporter or {}).get("banner") in supporters.ALL_BANNERS:
        classes += " profile-hero--has-banner"
    return classes


def _banner_html(view) -> str:
    banner = (view.supporter or {}).get("banner")
    if banner not in supporters.ALL_BANNERS:
        return ""
    motion = " profile-banner--motion" if (view.supporter or {}).get("motion") else ""
    return f'<div class="profile-banner profile-banner--{banner}{motion}" aria-hidden="true"></div>'


def _showcase_html(view) -> str:
    if not view.showcase:
        return ""
    cards = ""
    for item in view.showcase:
        art = (f'<img src="{_e(item["image"])}" alt="" loading="lazy">' if item.get("image")
               else f'<span>{_e(item["title"][:1].upper())}</span>')
        year = f' · {item["year"]}' if item.get("year") else ""
        rating = (f' · <span class="profile-rating">{_e(_rating(item["rating"]))}/10</span>'
                  if item.get("rating") is not None else "")
        cards += (f'<a class="profile-showcase__item" href="{_e(item["url"])}"><span class="profile-showcase__art">{art}</span>'
                  f'<strong>{_e(item["title"])}</strong><small>{_e(item["label"])}{_e(year)}{rating}</small></a>')
    return (f'<section class="title-section profile-showcase" aria-labelledby="profile-showcase">'
            f'<h2 id="profile-showcase">Showcase</h2><div class="profile-showcase__grid">{cards}</div></section>')


def _owner_note_html(view, is_owner: bool) -> str:
    if not is_owner:
        return ""
    note = ('This is your public profile. Change what it shows and pin titles to your showcase from '
            '<a href="/#public-profile">Account → Public profile</a>. '
            f'<a href="{_e(view.path)}/widgets">Get widgets</a> to show it on your blog, forum or GitHub.')
    if not view.profile.show_diary:
        note += ' You can also show your diary of recent finishes and rewatches there.'
    if not view.supporting:
        note += (' Supporters can also add a banner, pick an accent color and pin six titles. '
                 '<a href="/supporters">See what supporting gets you</a>.')
    return f'<p class="profile-owner-note">{note}</p>'


def _stats_html(view) -> str:
    if not view.stats:
        return ""
    tiles = ""
    for row in view.stats:
        done = round(100 * row["finished"] / row["total"]) if row["total"] else 0
        tiles += (f'<div class="profile-stat profile-stat--{_e(row["category"])}"><strong>{_e(row["total"])}</strong>'
                  f'<span>{_e(row["label"])}</span>'
                  f'<span class="profile-stat__meter" title="{done}% {_e(row["verb"])}"><span style="--w:{done}%"></span></span>'
                  f'<small>{_e(row["finished"])} {_e(row["verb"])}</small>'
                  + (f'<small>avg <b class="profile-rating">{_e(row["average"])}/10</b></small>' if row["average"] is not None else "")
                  + "</div>")
    return (f'<section class="title-section" aria-labelledby="profile-stats"><h2 id="profile-stats">Library</h2>'
            f'<div class="profile-stats">{tiles}</div></section>')


def _badges_html(view) -> str:
    if not view.badges:
        return ""
    items = "".join(
        f'<li class="profile-badge" title="{_e(badge["label"])}">'
        f'<span class="badge-medal badge-medal--{_e(badge["tier_name"].lower())}" aria-hidden="true">'
        f'<span class="badge-medal__glyph">{_e(badge["emoji"])}</span></span>'
        f'<span class="profile-badge__copy"><strong>{_e(badge["name"])}</strong>'
        f'<small>{_e(badge["tier_name"])} · {_e(badge["label"])}</small></span></li>'
        for badge in view.badges
    )
    return (f'<section class="title-section" aria-labelledby="profile-badges"><h2 id="profile-badges">Badges</h2>'
            f'<ul class="profile-badges">{items}</ul></section>')


def _favorites_html(view) -> str:
    if not view.favorites:
        return ""
    cards = ""
    for item in view.favorites:
        art = (f'<img src="{_e(item["image"])}" alt="" loading="lazy">' if item.get("image")
               else f'<span>{_e(item["title"][:1].upper())}</span>')
        year = f' · {item["year"]}' if item.get("year") else ""
        cards += (f'<a class="title-related" href="{_e(item["url"])}"><span class="title-related__art">{art}</span>'
                  f'<strong>{_e(item["title"])}</strong><small>{_e(item["label"])}{_e(year)} · '
                  f'<span class="profile-rating">{_e(_rating(item["rating"]))}/10</span></small></a>')
    return (f'<section class="title-section" aria-labelledby="profile-favorites"><h2 id="profile-favorites">Favorites</h2>'
            f'<div class="title-related-grid">{cards}</div></section>')


def _diary_html(view) -> str:
    if not view.diary:
        return ""
    months, current = "", None
    rows = ""
    for entry in view.diary:
        heading = f"{entry['date']:%B %Y}"
        if heading != current:
            if current is not None:
                months += f'<h3 class="profile-diary__month">{_e(current)}</h3><ol class="profile-diary__list">{rows}</ol>'
            current, rows = heading, ""
        art = (f'<img src="{_e(entry["image"])}" alt="" loading="lazy">' if entry.get("image")
               else f'<span>{_e(entry["title"][:1].upper())}</span>')
        repeat = (f' · <span class="profile-diary__again">↻ {_e(entry["visit_label"])}</span>' if entry["repeat"] else "")
        rating = (f' · <span class="profile-rating">{_e(_rating(entry["rating"]))}/10</span>'
                  if entry.get("rating") is not None else "")
        rows += (f'<li class="profile-diary__row"><time class="profile-diary__day" datetime="{entry["date"].isoformat()}">'
                 f'<strong>{entry["date"].day}</strong><small>{entry["date"]:%a}</small></time>'
                 f'<a class="profile-diary__art" href="{_e(entry["url"])}" tabindex="-1" aria-hidden="true">{art}</a>'
                 f'<span class="profile-diary__copy"><a href="{_e(entry["url"])}">{_e(entry["title"])}</a>'
                 f'<small>{_e(entry["label"])}{repeat}{rating}</small></span></li>')
    months += f'<h3 class="profile-diary__month">{_e(current)}</h3><ol class="profile-diary__list">{rows}</ol>'
    return (f'<section class="title-section profile-diary" aria-labelledby="profile-diary"><h2 id="profile-diary">Diary</h2>'
            f'<p class="profile-diary__intro">What {_e(view.user.username)} finished and went back to lately.</p>{months}</section>')


def _reviews_html(view) -> str:
    if not view.reviews:
        return ""
    cards = ""
    for review in view.reviews:
        rating = f'<span class="title-review__rating">{_e(_rating(review["rating"]))}/10</span>' if review["rating"] is not None else ""
        cards += (f'<article class="title-review"><header><a class="profile-review__title" href="{_e(review["title_url"])}">'
                  f'{_e(review["title"])}</a><span class="site-chip">{_e(review["label"])}</span>{rating}</header>'
                  + review_spoilers.wrap(review, f'<p>{_e(_excerpt(review["review"], 360))}</p>'
                                  # Short reviews have no page of their own, so there is nothing to link to.
                                  + (f'<a href="{_e(review["url"])}">Read the full review <span aria-hidden="true">→</span></a>'
                                     if review["search_ready"] else "")) + '</article>')
    return (f'<section class="title-section" aria-labelledby="profile-reviews"><h2 id="profile-reviews">Reviews</h2>'
            f'<div class="title-reviews">{cards}</div></section>')


def _collections_html(view) -> str:
    if not view.collections:
        return ""
    cards = "".join(
        f'<a class="title-collection" href="{_e(c["url"])}"><strong>{_e(c["name"])}</strong>'
        f'<span>{_e(_excerpt(c["description"], 140) or str(c["items"]) + " titles")}</span></a>'
        for c in view.collections)
    return (f'<section class="title-section" aria-labelledby="profile-collections"><h2 id="profile-collections">Public collections</h2>'
            f'<div class="title-collections">{cards}</div></section>')


# Library categories in the taste-mix bar, in profile-page.css colors.
MIX_COLORS = ("movies", "tv-shows", "anime", "video-games", "music", "books", "manga", "podcasts")
SECTION_TABS = (("profile-showcase", "Showcase"), ("profile-stats", "Library"), ("profile-badges", "Badges"),
                ("profile-favorites", "Favorites"), ("profile-diary", "Diary"), ("profile-reviews", "Reviews"),
                ("profile-collections", "Collections"))


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _wall_html(view) -> str:
    """Posters from the member's showcase, favorites and diary behind the header (not with a supporter banner)."""
    if (view.supporter or {}).get("banner") in supporters.ALL_BANNERS:
        return ""
    images = []
    for item in [*view.showcase, *view.favorites, *view.diary]:
        image = item.get("image")
        if image and image not in images:
            images.append(image)
        if len(images) >= 10:
            break
    if len(images) < 3:
        return ""
    posters = "".join(f'<img src="{_e(image)}" alt="" decoding="async">' for image in images)
    return f'<div class="profile-wall" aria-hidden="true">{posters}</div>'


def _numbers_html(view) -> str:
    """The headline numbers under the name. Only from what the member chose to show."""
    tiles = []
    if view.stats:
        finished = sum(row["finished"] for row in view.stats)
        tiles.append((f"{view.total_titles:,}", "titles tracked"))
        tiles.append((f"{finished:,}", "finished"))
        if view.hours:
            tiles.append((f"{view.hours:,}", "est. hour" if view.hours == 1 else "est. hours"))
        rated = sum(row["rated"] for row in view.stats if row["average"] is not None)
        if rated:
            average = sum(row["average"] * row["rated"] for row in view.stats if row["average"] is not None) / rated
            tiles.append((f"{average:.1f}", "average rating"))
    if view.reviews:
        tiles.append((str(len(view.reviews)), "review" if len(view.reviews) == 1 else "reviews"))
    if view.badges:
        tiles.append((str(len(view.badges)), "badge" if len(view.badges) == 1 else "badges"))
    if not tiles:
        return ""
    cells = "".join(f'<li class="profile-number"><strong>{_e(value)}</strong><span>{_e(label)}</span></li>'
                    for value, label in tiles[:6])
    return f'<ul class="profile-numbers" aria-label="At a glance">{cells}</ul>'


def _tabs_html(body: str) -> str:
    present = [(anchor, label) for anchor, label in SECTION_TABS if f'id="{anchor}"' in body]
    if len(present) < 3:
        return ""
    links = "".join(f'<a href="#{anchor}">{label}</a>' for anchor, label in present)
    return (f'<nav class="title-tabs profile-tabs" aria-label="On this page">'
            f'<div class="site-wrap title-tabs__inner">{links}</div></nav>')


def _mix_html(view) -> str:
    if not view.stats or view.total_titles <= 0:
        return ""
    segments, legend = "", ""
    for row in sorted(view.stats, key=lambda r: -r["total"]):
        share = row["total"] * 100 / view.total_titles
        tone = row["category"] if row["category"] in MIX_COLORS else "other"
        segments += f'<span class="profile-mix__part profile-mix__part--{_e(tone)}" style="--w:{share:.2f}%"></span>'
        legend += (f'<li><i class="profile-mix__dot profile-mix__part--{_e(tone)}" aria-hidden="true"></i>'
                   f'{_e(row["label"])} <b>{round(share)}%</b></li>')
    return (f'<div class="profile-mix"><p class="profile-glance__label">Taste mix</p>'
            f'<div class="profile-mix__bar" aria-hidden="true">{segments}</div><ul class="profile-mix__legend">{legend}</ul></div>')


def _glance_html(view, *, signed_in: bool, since: str) -> str:
    name = view.user.username
    # (label, html): plain values are escaped here.
    facts = [("Member", _e(since.replace("Member since ", "Since ")))]
    if view.stats:
        top = max(view.stats, key=lambda r: r["total"])
        facts.append(("Biggest shelf", _e(f'{top["label"]} · {top["total"]:,}')))
    picks = view.showcase or view.favorites
    top_pick = next((item for item in picks if item.get("rating") is not None), None)
    if top_pick:
        facts.append(("Top rated", f'<a href="{_e(top_pick["url"])}">{_e(top_pick["title"])}</a> '
                                   f'<span class="profile-rating">{_e(_rating(top_pick["rating"]))}/10</span>'))
    if view.diary:
        latest = view.diary[0]
        facts.append(("Latest finish", f'<a href="{_e(latest["url"])}">{_e(latest["title"])}</a> '
                                       f'<small>{latest["date"]:%b} {latest["date"].day}</small>'))
    if view.friends_brought:
        facts.append(("Brought to OmniTrackr", _e(_plural(view.friends_brought, "friend"))))
    rows = "".join(f'<div><dt>{_e(label)}</dt><dd>{value}</dd></div>' for label, value in facts)
    join = ("" if signed_in else
            f'<div class="title-glance__join profile-glance__join"><strong>Keep a profile like {_e(name)}\'s</strong>'
            '<p>Track everything you watch, play, read and hear in one free library. Rate what you finish and share it with one link.</p>'
            '<a class="site-btn site-btn--primary site-btn--sm title-glance__cta" href="/#signup" data-profile-join>Start tracking free</a>'
            '<a class="profile-glance__quiz" href="/taste-quiz">Or take the one-minute taste quiz <span aria-hidden="true">→</span></a></div>')
    return (f'<aside class="title-glance profile-glance" aria-labelledby="profile-glance"><h2 id="profile-glance">About {_e(name)}</h2>'
            f'{_mix_html(view)}<dl>{rows}</dl>{join}</aside>')


def _actions_html(view, *, signed_in: bool, is_owner: bool, recap_url, recap_year) -> str:
    name = view.user.username
    buttons = []
    if not signed_in:
        buttons.append('<a class="site-btn site-btn--primary site-btn--sm" href="/#signup" data-profile-join>Make your own profile, free</a>')
    elif is_owner:
        buttons.append('<a class="site-btn site-btn--primary site-btn--sm" href="/#public-profile">Edit profile</a>')
    buttons.append(f'<button type="button" class="site-btn site-btn--ghost site-btn--sm" data-share '
                   f'data-share-title="{_e(name)} on OmniTrackr">Share profile</button>')
    if recap_url and recap_year:
        buttons.append(f'<a class="site-btn site-btn--primary site-btn--sm" href="{_e(recap_url)}#story">'
                       f'▶ {_e(name)}\'s {_e(recap_year)} in review</a>')
    return f'<p class="profile-hero__actions">{"".join(buttons)}</p>'


def _json_ld(view, canonical: str, description: str) -> str:
    person = {"@type": "Person", "name": view.user.username, "alternateName": "@" + view.user.username, "url": canonical,
              "description": description}
    if view.user.profile_picture_data:
        person["image"] = f"{SITE_URL}/profile-pictures/{view.user.id}"
    data = {"@context": "https://schema.org", "@type": "ProfilePage", "url": canonical, "mainEntity": person}
    if view.user.created_at:
        data["dateCreated"] = view.user.created_at.date().isoformat()
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")


def _bio_html(bio: Optional[str]) -> str:
    if not bio:
        return ""
    return "".join(f'<p class="profile-hero__bio">{_e(part)}</p>' for part in bio.split("\n") if part.strip())


def render(view, *, signed_in: bool, is_owner: bool, recap_url: Optional[str] = None, recap_year: Optional[int] = None) -> str:
    user, profile = view.user, view.profile
    canonical = SITE_URL + view.path
    name = user.username
    since = f"Member since {user.created_at:%B} {user.created_at.year}" if user.created_at else "OmniTrackr member"
    summary_bits = []
    if view.total_titles:
        summary_bits.append(f"{view.total_titles} title{'s' if view.total_titles != 1 else ''} tracked")
    if view.reviews:
        summary_bits.append(f"{len(view.reviews)} public review{'s' if len(view.reviews) != 1 else ''}")
    if view.collections:
        summary_bits.append(f"{len(view.collections)} collection{'s' if len(view.collections) != 1 else ''}")
    if view.friends_brought:
        summary_bits.append(f"Brought {view.friends_brought} friend{'s' if view.friends_brought != 1 else ''} to OmniTrackr")
    lead = profile.bio or ""
    meta_description = _excerpt(
        (f"{name} on OmniTrackr: " + (", ".join(summary_bits) if summary_bits else "movies, shows, games, music and books"))
        + (f". {lead}" if lead else "."), 158)
    robots = "index, follow" if view.indexable else "noindex, follow"
    card_url = f"{SITE_URL}{view.path}/card.png"
    body = "".join([_showcase_html(view), _stats_html(view), _badges_html(view), _favorites_html(view), _diary_html(view), _reviews_html(view), _collections_html(view)])
    tabs = _tabs_html(body)
    if not body:
        body = f'<p class="title-empty">{_e(name)} hasn\'t shared anything here yet.</p>'
    owner_note = _owner_note_html(view, is_owner)
    cta = ("" if signed_in else
           '<section class="profile-cta site-card"><div><p class="site-eyebrow">Free on OmniTrackr</p>'
           '<h2>Track everything you watch, play, read and hear</h2>'
           '<p>Rate what you finish, keep a diary and share a profile like this one.</p></div>'
           '<div class="profile-cta__actions"><a class="site-btn site-btn--primary" href="/#signup" data-profile-join>Start tracking free</a>'
           '<a class="site-btn site-btn--ghost" href="/about">See how it works</a></div></section>')
    joinbar = ("" if signed_in else
               f'<div class="profile-joinbar" data-profile-joinbar><span>Like {_e(name)}\'s taste? Start your own library.</span>'
               '<a class="site-btn site-btn--primary site-btn--sm" href="/#signup" data-profile-join>Join free</a></div>')
    # Titles and reviews are in the headline numbers; the chips carry the rest.
    chips = "".join(f'<span class="site-chip">{_e(bit)}</span>' for bit in summary_bits
                    if not bit.endswith(("tracked", "review", "reviews")))
    wall = _wall_html(view)
    hero_class = _hero_class(view) + (" profile-hero--wall" if wall else "")
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_e(name)} on OmniTrackr</title>
  <meta name="description" content="{_e(meta_description)}">
  <meta name="robots" content="{robots}">
  <link rel="canonical" href="{_e(canonical)}">
  <meta property="og:site_name" content="OmniTrackr">
  <meta property="og:title" content="{_e(name)} on OmniTrackr">
  <meta property="og:description" content="{_e(meta_description)}">
  <meta property="og:type" content="profile">
  <meta property="profile:username" content="{_e(name)}">
  <meta property="og:url" content="{_e(canonical)}">
  <meta property="og:image" content="{_e(card_url)}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="{_e(name)}'s OmniTrackr profile card">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{_e(name)} on OmniTrackr">
  <meta name="twitter:description" content="{_e(meta_description)}">
  <meta name="twitter:image" content="{_e(card_url)}">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">
  <link rel="stylesheet" href="/static/title-page.css?v={TITLE_CSS_VERSION}">
  <link rel="stylesheet" href="/static/profile-page.css?v={CSS_VERSION}">
  <link rel="stylesheet" href="/static/profile-banners.css?v={CSS_VERSION}">
  <link rel="stylesheet" href="/static/badges.css?v=20261017-badges-1">
  <script type="application/ld+json">{_json_ld(view, canonical, meta_description)}</script>
  <script src="/static/share.js?v=20261004-share-1" defer></script>
  <script src="/static/profile-page.js?v={CSS_VERSION}" defer></script>
</head>
<body class="site title-page profile-page{'' if signed_in else ' profile-page--guest'}">
  <!--SITE_NAV:-->
  <main>
    <section class="{_e(hero_class)}">
      {_banner_html(view)}
      {wall}
      <div class="site-wrap profile-hero__inner">
        {_avatar_html(user)}
        <div class="profile-hero__copy">
          <p class="site-eyebrow">Public profile</p>
          <h1>{_e(name)}</h1>
          {_supporter_html(view)}
          <p class="profile-hero__meta">{_e(since)}</p>
          {_bio_html(profile.bio)}
          {_numbers_html(view)}
          <div class="title-hero__chips">{chips}</div>
          {_actions_html(view, signed_in=signed_in, is_owner=is_owner, recap_url=recap_url, recap_year=recap_year)}
          {owner_note}
        </div>
      </div>
    </section>
    {tabs}
    <div class="site-wrap title-body title-body--glance profile-body">
      <div class="title-main">
        {body}
        {cta}
      </div>
      {_glance_html(view, signed_in=signed_in, since=since)}
      <p class="title-sources">Members choose what their profile shows. Report a review or collection from its own page.</p>
    </div>
    {joinbar}
  </main>
  <!--SITE_FOOTER-->
</body>
</html>"""
    return apply_site_chrome(page)


def _profile_response(request: Request, db: Session, user: Optional[models.User], current_path: str):
    profile = public_profiles.visible_profile(db, user)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    canonical = public_profiles.profile_path(user)
    if current_path.rstrip("/") != canonical:
        return RedirectResponse(canonical, status_code=301)
    view = public_profiles.build(db, user, profile)
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    is_owner = signed_in and _viewer_id(request, db) == user.id
    if not signed_in:
        funnel.record("profile_link_opened", request)
    recap_url, recap_year = _season_recap(db, user.id)
    response = strict_html_response(render(view, signed_in=signed_in, is_owner=is_owner,
                                           recap_url=recap_url, recap_year=recap_year))
    response.headers["Cache-Control"] = "private, no-store" if signed_in else "public, max-age=300"
    response.headers["Vary"] = "Cookie"
    if not view.indexable:
        response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


def _season_recap(db: Session, user_id: int) -> tuple[Optional[str], Optional[int]]:
    """In December and January, the member's shared Year in Review for the season, if they shared one."""
    from .. import year_in_review
    try:
        year = year_in_review.season_year()
        share = year_in_review.get_share(db, user_id, year) if year else None
    except Exception:
        db.rollback()
        return None, None
    return (year_in_review.share_path(share), year) if share else (None, None)


def _viewer_id(request: Request, db: Session) -> Optional[int]:
    """The signed-in viewer's account id from the session cookie, or None. Only used for the owner hint."""
    from .. import auth
    payload = auth.decode_access_token(request.cookies.get(AUTH_COOKIE_NAME) or "")
    uid = (payload or {}).get("uid")
    return uid if isinstance(uid, int) and not isinstance(uid, bool) else None


@router.get("/u/id/{user_id:database_id}", include_in_schema=False)
def profile_by_id(user_id: PositiveDatabaseId, request: Request, db: Session = Depends(get_db)):
    return _profile_response(request, db, public_profiles.find_user_by_id(db, user_id), request.url.path)


@router.get("/u/{handle}", include_in_schema=False)
def profile_page(handle: str, request: Request, db: Session = Depends(get_db)):
    return _profile_response(request, db, public_profiles.find_user(db, handle), request.url.path)


# ---------------------------------------------------------------- share card

class _CardCache:
    """Small in-memory LRU of rendered share cards (PNG bytes)."""

    def __init__(self, size: int = 128):
        self.size = size
        self._items: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            value = self._items.get(key)
            if value is not None:
                self._items.move_to_end(key)
            return value

    def put(self, key, value):
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self.size:
                self._items.popitem(last=False)

    def clear_user(self, user_id: int):
        with self._lock:
            for key in [k for k in self._items if k[0] == user_id]:
                del self._items[key]


_CARD_CACHE = _CardCache()


def _font(size: int, bold: bool = False):
    from PIL import ImageFont
    # A system DejaVu font when the server has one; otherwise Pillow's bundled font.
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover - very old Pillow
        return ImageFont.load_default()


def _fit(draw, text: str, font, width: int) -> str:
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text.rstrip() + "…"


# Accent colors for the share card, matching profile-page.css.
CARD_ACCENTS = {"violet": (139, 92, 246), "teal": (45, 212, 191), "amber": (245, 158, 11), "rose": (244, 114, 182),
                "sky": (56, 189, 248), "emerald": (52, 211, 153), "coral": (251, 113, 133), "gold": (234, 179, 8)}


def _card_avatar(user: models.User, ring_rgb):
    """(image, box, mask) for pasting the member's picture, or their initial, as a ringed circle on the card."""
    from PIL import Image, ImageDraw, ImageOps
    size, ring = 132, 4
    tile = None
    if user.profile_picture_data:
        try:
            with Image.open(io.BytesIO(user.profile_picture_data)) as picture:
                tile = ImageOps.fit(picture.convert("RGB"), (size, size))
        except Exception:
            tile = None
    if tile is None:
        tile = Image.new("RGB", (size, size), (38, 30, 84))
        draw = ImageDraw.Draw(tile)
        initial = (user.username or "?")[:1].upper()
        font = _font(64, bold=True)
        box = draw.textbbox((0, 0), initial, font=font)
        draw.text(((size - (box[2] - box[0])) / 2 - box[0], (size - (box[3] - box[1])) / 2 - box[1]), initial,
                  font=font, fill=(196, 181, 253))
    full = size + ring * 2
    disc = Image.new("RGB", (full, full), ring_rgb)
    inner = Image.new("L", (size, size), 0)
    ImageDraw.Draw(inner).ellipse((0, 0, size - 1, size - 1), fill=255)
    disc.paste(tile, (ring, ring), inner)
    mask = Image.new("L", (full, full), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, full - 1, full - 1), fill=255)
    return disc, (84, 140), mask


def render_card(view) -> bytes:
    from PIL import Image, ImageDraw
    width, height = 1200, 630
    supporter = view.supporter or {}
    glow_rgb = CARD_ACCENTS.get(supporter.get("accent")) or ((234, 179, 8) if supporter.get("founding") else (124, 58, 237))
    image = Image.new("RGB", (width, height), (11, 10, 24))
    draw = ImageDraw.Draw(image)
    # Soft violet glow in the corner, drawn as concentric translucent circles.
    glow = Image.new("RGB", (width, height), (11, 10, 24))
    glow_draw = ImageDraw.Draw(glow)
    for step in range(18, 0, -1):
        radius = step * 34
        mix = (1 - step / 18) * 0.55
        shade = (int(11 + (glow_rgb[0] - 11) * mix), int(10 + (glow_rgb[1] - 10) * mix), int(24 + (glow_rgb[2] - 24) * mix))
        glow_draw.ellipse((width - 160 - radius, -120 - radius, width - 160 + radius, -120 + radius), fill=shade)
    image = Image.blend(image, glow, 0.85)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, width - 40, height - 40), radius=28, outline=(60, 52, 110), width=2)

    brand = _font(30, bold=True)
    draw.text((84, 78), "OmniTrackr", font=brand, fill=(196, 181, 253))
    image.paste(*_card_avatar(view.user, glow_rgb))
    draw = ImageDraw.Draw(image)
    name_font = _font(76, bold=True)
    draw.text((250, 150), _fit(draw, view.user.username, name_font, width - 334), font=name_font, fill=(245, 243, 255))
    sub = _font(30)
    since = f"Member since {view.user.created_at:%B} {view.user.created_at.year}" if view.user.created_at else "OmniTrackr member"
    draw.text((252, 248), since, font=sub, fill=(167, 160, 199))
    if supporter:
        founding = bool(supporter.get("founding"))
        label = supporters.level_label(founding, int(supporter.get("months") or 0))
        pill_font = _font(24, bold=True)
        pill_rgb = (234, 179, 8) if founding else glow_rgb
        text_width = draw.textlength(label, font=pill_font)
        left = width - 84 - text_width - 40
        draw.rounded_rectangle((left, 74, width - 84, 118), radius=22, outline=pill_rgb, width=2,
                               fill=tuple(int(c * 0.22 + 15) for c in pill_rgb))
        draw.text((left + 20, 82), label, font=pill_font, fill=(245, 243, 255))

    y = 320
    if view.stats:
        x = 84
        number_font, label_font = _font(48, bold=True), _font(24)
        for row in view.stats[:6]:
            number = str(row["total"])
            label = row["label"]
            block = max(draw.textlength(number, font=number_font), draw.textlength(label, font=label_font)) + 48
            if x + block > width - 84:
                break
            draw.text((x, y), number, font=number_font, fill=(245, 243, 255))
            draw.text((x, y + 60), label, font=label_font, fill=(94, 234, 212))
            x += block
        y += 130
    picks = view.showcase or view.favorites
    favorite_titles = [item["title"] for item in picks[:4]]
    if favorite_titles:
        fav_font = _font(28)
        heading = "Showcase: " if view.showcase else "Favorites: "
        draw.text((84, y), _fit(draw, heading + " · ".join(favorite_titles), fav_font, width - 168), font=fav_font, fill=(214, 209, 240))
    elif view.profile.bio:
        bio_font = _font(28)
        draw.text((84, y), _fit(draw, " ".join(view.profile.bio.split()), bio_font, width - 168), font=bio_font, fill=(214, 209, 240))
    foot = _font(24)
    invite_font = _font(24, bold=True)
    invite = "Track yours free"
    invite_width = draw.textlength(invite, font=invite_font) + 48
    draw.rounded_rectangle((width - 84 - invite_width, height - 112, width - 84, height - 66), radius=23,
                           fill=(124, 58, 237))
    draw.text((width - 84 - invite_width + 24, height - 102), invite, font=invite_font, fill=(255, 255, 255))
    path_text = (SITE_URL.replace("https://", "").replace("http://", "") + view.path)
    draw.text((84, height - 100), _fit(draw, path_text, foot, width - 168 - invite_width - 24), font=foot, fill=(167, 160, 199))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _card_response(db: Session, user: Optional[models.User]):
    profile = public_profiles.visible_profile(db, user)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    view = public_profiles.build(db, user, profile)
    fingerprint = hashlib.sha256(repr((
        user.username, user.created_at, profile.bio,
        hashlib.sha256(user.profile_picture_data or b"").hexdigest(),
        [(r["label"], r["total"]) for r in view.stats], [f["title"] for f in view.favorites[:4]],
        [f["title"] for f in view.showcase[:4]], sorted((view.supporter or {}).items(), key=str),
    )).encode("utf-8")).hexdigest()[:16]
    key = (user.id, fingerprint)
    png = _CARD_CACHE.get(key)
    if png is None:
        try:
            png = render_card(view)
        except Exception:
            raise HTTPException(status_code=404, detail="Card unavailable")
        _CARD_CACHE.put(key, png)
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600", "ETag": f'"{fingerprint}"',
                             "X-Content-Type-Options": "nosniff"})


@router.get("/u/id/{user_id:database_id}/card.png", include_in_schema=False)
def profile_card_by_id(user_id: PositiveDatabaseId, request: Request, db: Session = Depends(get_db)):
    return _card_response(db, public_profiles.find_user_by_id(db, user_id))


@router.get("/u/{handle}/card.png", include_in_schema=False)
def profile_card(handle: str, request: Request, db: Session = Depends(get_db)):
    return _card_response(db, public_profiles.find_user(db, handle))
