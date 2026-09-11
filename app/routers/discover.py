"""Public editorial trails with authenticated, atomic library saves."""
from html import escape
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from .. import models
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..discover_catalog import MONTHLY_EDITIONS, TRAILS
from .collections import CATEGORIES

router = APIRouter()


def trail_for(slug):
    if slug not in TRAILS:
        raise HTTPException(404, "Trail not found")
    return TRAILS[slug]


def monthly_for(slug):
    if slug not in MONTHLY_EDITIONS:
        raise HTTPException(404, "Monthly edition not found")
    return MONTHLY_EDITIONS[slug]


def page(title, description, path, content):
    html = (Path(__file__).parents[1] / "templates" / "discover.html").read_text(encoding="utf-8")
    for key, value in {"TITLE": escape(title), "DESCRIPTION": escape(description, quote=True), "PATH": path, "CONTENT": content}.items():
        html = html.replace("{{" + key + "}}", value)
    return strict_html_response(html)


@router.get("/discover")
def discover_index():
    cards = "".join(f'<article class="trail"><p class="eyebrow">{t["tag"]}</p><h2><a href="/discover/{slug}">{escape(t["name"])}</a></h2><p>{escape(t["intro"])}</p><p class="muted">' + " · ".join(CATEGORIES[i["category"]][1] for i in t["items"]) + f'</p><a class="button" href="/discover/{slug}">Explore this trail →</a></article>' for slug, t in TRAILS.items())
    edition_slug, edition = next(iter(MONTHLY_EDITIONS.items()))
    edition_card = f'<section class="monthly-feature"><div><p class="eyebrow">{escape(edition["tag"])}</p><h2>{escape(edition["name"])}</h2><p>{escape(edition["intro"])}</p><p class="muted">{escape(edition["published"])} · Six media types · Six carefully chosen places to start</p></div><a class="button" href="/discover/monthly/{edition_slug}">Read this edition →</a></section>'
    return page("Discover", "Thoughtful trails across movies, TV, anime, games, music and books.", "/discover", '<header class="hero"><p class="eyebrow">SIX MEDIA TYPES. NEW CONNECTIONS.</p><h1>Follow your curiosity.</h1><p>Find your next watch, read, listen or play through a shared idea. Explore freely, then save the picks that feel like you.</p></header>' + edition_card + '<div class="trails">' + cards + '</div><section class="editorial"><h2>How these trails work</h2><p>These are editorial suggestions, not rankings or user reviews. Each pick has a reason to be here, a caveat, and a source for learning more. Start with one; there is no need to finish a whole collection.</p><p>Saving requires an account. You choose which titles to add, and can review existing matches before confirming.</p></section>')


def detail_content(trail, back_path, back_label, api_path, published, essay=None):
    items = "".join(f'<article class="pick"><p class="eyebrow">{n:02d} / {CATEGORIES[i["category"]][1]}</p><h2>{escape(i["title"])}</h2><p>{escape(i["why"])}</p><p class="caveat">{escape(i["caveat"])}</p><a href="{escape(i["source"], quote=True)}" rel="noopener noreferrer" target="_blank">Source / learn more ↗</a></article>' for n, i in enumerate(trail["items"], 1))
    essay_section = ""
    if essay:
        essay_section = f'<section class="editorial edition-essay"><h2>{escape(essay["title"])}</h2><p>{escape(essay["body"])}</p></section>'
    return f'<header class="hero"><a href="{back_path}">← {escape(back_label)}</a><p class="eyebrow">{escape(trail["tag"])}</p><h1>{escape(trail["name"])}</h1><p>{escape(trail["intro"])}</p></header>{essay_section}<section class="editorial"><h2>Choose your starting point</h2><p>{escape(trail["guide"])}</p></section><div class="picks">{items}</div><section class="editorial"><h2>Take something with you</h2><p>{escape(trail["prompt"])}</p><p class="muted">Editorial suggestions · Published {escape(published)}. Source links are informational, not affiliate links. Availability varies by region.</p></section><section class="save-panel" data-trail="{escape(api_path, quote=True)}"><h2>Make this collection yours</h2><p>Preview your library matches, then select the titles you want in a private collection. Existing ratings, reviews and progress are preserved.</p><button id="preview" type="button">Preview saving</button><a id="signin" href="/#landing-auth" hidden>Sign in, then return here to preview →</a><form id="saveForm" hidden><div id="choices"></div><button id="save" type="submit">Save selected picks</button></form><p id="status" role="status"></p></section>'


@router.get("/discover/monthly/{slug}")
def monthly_detail(slug: str):
    edition = monthly_for(slug)
    return page(edition["name"] + " | Discover", edition["intro"], "/discover/monthly/" + slug, detail_content(edition, "/discover", "Discover", "monthly/" + slug, edition["published"], {"title": edition["essay_title"], "body": edition["essay"]}))


@router.get("/discover/{slug}")
def discover_detail(slug: str):
    t = trail_for(slug)
    return page(t["name"] + " | Discover", t["intro"], "/discover/" + slug, detail_content(t, "/discover", "All trails", slug, "September 8, 2026"))


def match(db, user_id, item):
    model = CATEGORIES[item["category"]][0]
    # Conservative title matching reuses an existing record without ever editing it.
    return db.query(model).filter(model.user_id == user_id, func.lower(func.trim(model.title)) == item["title"].lower()).order_by(model.id).first()


@router.get("/api/discover/{slug}/preview")
def preview(slug: str, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'private, no-store'
    return preview_for(trail_for(slug), user, db)


@router.get("/api/discover/monthly/{slug}/preview")
def monthly_preview(slug: str, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'private, no-store'
    return preview_for(monthly_for(slug), user, db)


def preview_for(trail, user, db):
    return {"items": [{"key": i["key"], "title": i["title"], "category": CATEGORIES[i["category"]][1], "existing": match(db, user.id, i) is not None} for i in trail["items"]]}


class SaveSelection(BaseModel):
    keys: list[str] = Field(min_length=1, max_length=6)


@router.post("/api/discover/{slug}/save")
def save(slug: str, selection: SaveSelection, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'private, no-store'
    return save_for(trail_for(slug), selection, user, db, "Discover")


@router.post("/api/discover/monthly/{slug}/save")
def monthly_save(slug: str, selection: SaveSelection, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'private, no-store'
    return save_for(monthly_for(slug), selection, user, db, "Monthly Edition")


def save_for(trail, selection, user, db, collection_prefix):
    keys = set(selection.keys)
    if not keys.issubset({i["key"] for i in trail["items"]}):
        raise HTTPException(422, "Unknown pick")
    # Serialize saves for this user on PostgreSQL, including repeated clicks/retries.
    db.query(models.User).filter(models.User.id == user.id).with_for_update().first()
    name = collection_prefix + ": " + trail["name"]
    collection = db.query(models.Collection).filter_by(user_id=user.id, name=name).order_by(models.Collection.id).first()
    created = reused = 0
    try:
        if collection is None:
            collection = models.Collection(user_id=user.id, name=name, description=trail["prompt"])
            db.add(collection)
            db.flush()
        position = max((i.position for i in collection.items), default=-1) + 1
        for item in trail["items"]:
            if item["key"] not in keys:
                continue
            media = match(db, user.id, item)
            if media is None:
                media = CATEGORIES[item["category"]][0](user_id=user.id, title=item["title"], **item["meta"])
                db.add(media)
                db.flush()
                created += 1
            else:
                reused += 1
            exists = db.query(models.CollectionItem).filter_by(collection_id=collection.id, category=item["category"], item_id=media.id).first()
            if exists is None:
                db.add(models.CollectionItem(collection_id=collection.id, category=item["category"], item_id=media.id, position=position))
                position += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"created": created, "reused": reused, "collection_id": collection.id}
