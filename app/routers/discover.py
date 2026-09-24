"""Public editorial trails with authenticated, atomic library saves."""
from html import escape
import json
from datetime import date
from pathlib import Path
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from .. import models
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..discover_catalog import MONTHLY_EDITIONS, TRAILS
from ..discover_guides import GUIDES
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


def page(title, description, path, content, *, indexable=True, structured_data=None):
    html = (Path(__file__).parents[1] / "templates" / "discover.html").read_text(encoding="utf-8")
    robots = "index, follow, max-image-preview:large" if indexable else "noindex, follow"
    for key, value in {"TITLE": escape(title), "DESCRIPTION": escape(description, quote=True), "PATH": path, "ROBOTS": robots, "CONTENT": content}.items():
        html = html.replace("{{" + key + "}}", value)
    # Escape script delimiters even though the editorial catalog is maintained in code.
    structured = ''
    if structured_data:
        payload = json.dumps(structured_data, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
        structured = f'<script type="application/ld+json">{payload}</script>'
    html = html.replace('{{STRUCTURED_DATA}}', structured)
    response = strict_html_response(html)
    if not indexable:
        response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


@router.get("/discover")
def discover_index():
    cards = []
    for slug, trail in TRAILS.items():
        guide_label = '<span class="trail-guide-label">In-depth guide</span>' if slug in GUIDES else ''
        categories = " ".join(item["category"] for item in trail["items"])
        titles = " · ".join(item["title"] for item in trail["items"])
        creators = " ".join(str(value) for item in trail["items"] for value in item["meta"].values())
        search = " ".join((trail["name"], trail["tag"], trail["intro"], titles, creators))
        formats = " · ".join(CATEGORIES[item["category"]][1] for item in trail["items"])
        cards.append(
            f'<article class="trail" data-formats="{escape(categories, quote=True)}" data-search="{escape(search, quote=True)}">'
            f'<p class="eyebrow">{escape(trail["tag"])}</p>{guide_label}<h2><a href="/discover/{slug}">{escape(trail["name"])}</a></h2>'
            f'<p>{escape(trail["intro"])}</p><p class="trail-titles"><strong>Inside this trail</strong>{escape(titles)}</p>'
            f'<p class="muted">{escape(formats)}</p><a class="button" href="/discover/{slug}">Explore this trail →</a></article>'
        )
    options = ''.join(f'<option value="{category}">{label}</option>' for category, (_, label) in CATEGORIES.items())
    filters = (
        '<section id="trail-filters" class="trail-filters" aria-label="Find a trail" hidden>'
        '<div class="trail-filter-fields"><div><label for="trail-search">What are you curious about?</label>'
        '<input id="trail-search" type="search" maxlength="100" placeholder="Try a title, creator, or theme" aria-controls="trail-list"></div>'
        f'<div><label for="trail-format">Include a format</label><select id="trail-format" aria-controls="trail-list"><option value="">Any format</option>{options}</select></div>'
        '<button id="trail-reset" type="button" class="filter-reset">Clear filters</button></div>'
        '<p id="trail-results" class="muted" role="status" aria-live="polite" aria-atomic="true"></p></section>'
    )
    edition_slug, edition = next(iter(MONTHLY_EDITIONS.items()))
    edition_card = f'<section class="monthly-feature"><div><p class="eyebrow">{escape(edition["tag"])}</p><h2>{escape(edition["name"])}</h2><p>{escape(edition["intro"])}</p><p class="muted">{escape(edition["published"])} · Six media types · Six carefully chosen places to start</p></div><a class="button" href="/discover/monthly/{edition_slug}">Read this edition →</a></section>'
    return page("Discover", "Thoughtful trails across movies, TV, anime, games, music and books.", "/discover", '<header class="hero"><p class="eyebrow">SIX MEDIA TYPES. NEW CONNECTIONS.</p><h1>Follow your curiosity.</h1><p>Find your next watch, read, listen or play through a shared idea. Explore freely, then save the picks that feel like you.</p></header>' + edition_card + filters + '<p id="trail-empty" class="trail-empty" hidden>No trails match yet. Try a broader theme or choose Any format.</p><div id="trail-list" class="trails">' + ''.join(cards) + '</div><section class="editorial"><h2>How these trails work</h2><p>These are editorial suggestions, not rankings or user reviews. Each pick has a reason to be here, a caveat, and a source for learning more. Start with one; there is no need to finish a whole collection.</p><p>Saving requires an account. You choose which titles to add, and can review existing matches before confirming.</p></section>')


def detail_content(trail, back_path, back_label, api_path, published, essay=None):
    items = "".join(f'<article class="pick"><p class="eyebrow">{n:02d} / {CATEGORIES[i["category"]][1]}</p><h2>{escape(i["title"])}</h2><p>{escape(i["why"])}</p><p class="caveat">{escape(i["caveat"])}</p><a href="{escape(i["source"], quote=True)}" rel="noopener noreferrer" target="_blank">Source / learn more ↗</a></article>' for n, i in enumerate(trail["items"], 1))
    essay_section = ""
    if essay:
        essay_section = f'<section class="editorial edition-essay"><h2>{escape(essay["title"])}</h2><p>{escape(essay["body"])}</p></section>'
    signin = '/?next=' + quote('/discover/' + api_path + '#save-picks', safe='') + '#landing-auth'
    return f'<header class="hero"><a href="{back_path}">← {escape(back_label)}</a><p class="eyebrow">{escape(trail["tag"])}</p><h1>{escape(trail["name"])}</h1><p>{escape(trail["intro"])}</p><a class="save-jump" href="#save-picks">Save picks to your library ↓</a></header>{essay_section}<section class="editorial"><h2>Choose your starting point</h2><p>{escape(trail["guide"])}</p></section><div class="picks">{items}</div><section class="editorial"><h2>Take something with you</h2><p>{escape(trail["prompt"])}</p><p class="muted">Editorial suggestions · Published {escape(published)}. Source links are informational, not affiliate links. Availability varies by region.</p></section><section id="save-picks" class="save-panel" data-trail="{escape(api_path, quote=True)}"><h2>Make this collection yours</h2><p>Preview your library matches, then select the titles you want in a private collection. Existing ratings, reviews and progress are preserved.</p><button id="preview" type="button">Preview saving</button><a id="signin" href="{escape(signin, quote=True)}" hidden>Sign in or create an account to continue here →</a><form id="saveForm" hidden><fieldset id="choices"><legend>Titles to save</legend></fieldset><button id="save" type="submit">Save selected picks</button></form><p id="status" role="status" aria-live="polite"></p><noscript><p>Enable JavaScript to preview and save picks. You can read every recommendation without it.</p></noscript></section>'


def paragraphs(values):
    return ''.join(f'<p>{escape(value)}</p>' for value in values)


def guide_content(slug, trail, guide):
    """Render the curated guides without requiring scripts, accounts, or private data."""
    reviewed = date.fromisoformat(guide['reviewed']).strftime('%B %d, %Y')
    parts = [
        '<article class="trail-guide">',
        '<header class="hero hero--guide"><a href="/discover">← All trails</a>',
        f'<p class="eyebrow">{escape(trail["tag"])} · A DISCOVER GUIDE</p>',
        f'<h1>{escape(trail["name"])}</h1><p class="guide-deck">{escape(guide["summary"])}</p>',
        '<p class="guide-byline">By <a href="/about">OmniTrackr</a> · Updated ',
        f'<time datetime="{escape(guide["reviewed"], quote=True)}">{escape(reviewed)}</time></p>',
        '<nav class="guide-jump" aria-label="On this page">',
        '<a href="#compare-picks">Compare picks</a><a href="#connections">The connections</a>',
        '<a href="#picks">Explore each pick</a><a href="#guide-sources">Sources &amp; method</a>',
        '<a href="#save-picks">Save your picks</a></nav></header>',
        '<div class="guide-intro">', paragraphs(guide['lead']), '</div>',
        '<section id="compare-picks" class="guide-comparison" aria-labelledby="comparison-heading">',
        '<p class="eyebrow">A PLACE TO START</p><h2 id="comparison-heading">Which one fits your time and mood?</h2>',
        f'<p class="guide-section-intro">{escape(guide["comparison_intro"])}</p>',
        '<table class="guide-table"><caption>Compare the four starting points</caption>',
        '<thead><tr><th scope="col">Pick</th><th scope="col">Mood &amp; pace</th>',
        '<th scope="col">Commitment</th><th scope="col">Choose it when</th><th scope="col">Consider first</th></tr></thead><tbody>',
    ]
    items = {item['key']: item for item in trail['items']}
    for choice in guide['choices']:
        item = items[choice['key']]
        parts.append(f'<tr><th scope="row"><a href="#pick-{escape(item["key"], quote=True)}">{escape(item["title"])}</a><span>{escape(CATEGORIES[item["category"]][1])}</span></th>')
        for key, label in [('pace', 'Mood & pace'), ('commitment', 'Commitment'), ('best_for', 'Choose it when'), ('consider', 'Consider first')]:
            parts.append(f'<td data-label="{escape(label, quote=True)}">{escape(choice[key])}</td>')
        parts.append('</tr>')
    parts.append('</tbody></table></section><div id="connections" class="guide-connections">')
    for section in guide['sections']:
        heading_id = 'connection-' + section['id']
        parts.append(f'<section class="guide-essay" aria-labelledby="{escape(heading_id, quote=True)}"><h2 id="{escape(heading_id, quote=True)}">{escape(section["heading"])}</h2>{paragraphs(section["paragraphs"])}</section>')
    parts.append('</div><section id="picks" aria-labelledby="picks-heading"><p class="eyebrow">LOOK A LITTLE CLOSER</p><h2 id="picks-heading">Four ways into the idea</h2><div class="picks guide-picks">')
    source_by_key = {source['key']: source for source in guide['sources']}
    for index, item in enumerate(trail['items'], 1):
        key = item['key']
        parts.extend([
            f'<article id="pick-{escape(key, quote=True)}" class="pick"><p class="eyebrow">{index:02d} / {escape(CATEGORIES[item["category"]][1])}</p>',
            f'<h3>{escape(item["title"])}</h3><p>{escape(item["why"])}</p>',
            paragraphs(guide['item_notes'][key]),
            f'<p class="caveat">{escape(item["caveat"])}</p>',
            f'<a class="guide-source-link" href="#source-{escape(key, quote=True)}">Source: {escape(source_by_key[key]["label"])} ↓</a></article>',
        ])
    parts.extend([
        '</div></section><section class="editorial guide-reflection"><h2>Take something with you</h2>',
        f'<p>{escape(trail["prompt"])}</p><p>Keep a short note about what drew you in and whether it suited the time you had. That is more useful for your next choice than treating this list as a checklist.</p></section>',
        '<section id="related-trails" class="guide-related" aria-labelledby="related-heading"><p class="eyebrow">FOLLOW ANOTHER THREAD</p><h2 id="related-heading">Where to go next</h2><div class="guide-related-grid">',
    ])
    for related in guide['related']:
        target = TRAILS[related['slug']]
        parts.append(f'<article><h3><a href="/discover/{escape(related["slug"], quote=True)}">{escape(target["name"])}</a></h3><p>{escape(related["reason"])}</p></article>')
    parts.extend([
        '</div></section><section id="guide-sources" class="guide-sources" aria-labelledby="sources-heading">',
        '<h2 id="sources-heading">Sources &amp; editorial method</h2>',
        '<div id="editorial-method"><p>Prepared by OmniTrackr with AI assistance. Factual context was checked against the official sources below; comparisons, mood descriptions, and suggested starting points are editorial interpretations.</p>',
        '<p>Reading and game time varies by person; suggested stopping points are ways to begin, rather than promises about completion time. Source links are informational, not affiliate links. Availability varies by region.</p>',
        f'<p class="muted">First published September 8, 2026. Guide expanded and sources checked {escape(reviewed)}. <a href="/contact">Send a correction</a> · <a href="/content-quality">Content quality policy</a></p></div><ol>',
    ])
    for source in guide['sources']:
        parts.append(f'<li id="source-{escape(source["key"], quote=True)}"><a href="{escape(source["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{escape(source["label"])} ↗</a><p>{escape(source["supports"])}</p></li>')
    # The same markup and selectors used by the established preview/save script.
    signin = '/?next=' + quote('/discover/' + slug + '#save-picks', safe='') + '#landing-auth'
    parts.extend([
        '</ol></section>',
        f'<section id="save-picks" class="save-panel" data-trail="{escape(slug, quote=True)}"><h2>Make this collection yours</h2>',
        '<p>Preview your library matches, then select the titles you want in a private collection. Existing ratings, reviews and progress are preserved.</p>',
        '<button id="preview" type="button">Preview saving</button>',
        f'<a id="signin" href="{escape(signin, quote=True)}" hidden>Sign in or create an account to continue here →</a>',
        '<form id="saveForm" hidden><fieldset id="choices"><legend>Titles to save</legend></fieldset><button id="save" type="submit">Save selected picks</button></form>',
        '<p id="status" role="status" aria-live="polite"></p><noscript><p>Enable JavaScript to preview and save picks. You can read every recommendation without it.</p></noscript></section></article>',
    ])
    return ''.join(parts)


@router.get("/discover/monthly/{slug}")
def monthly_detail(slug: str):
    edition = monthly_for(slug)
    return page(edition["name"] + " | Discover", edition["intro"], "/discover/monthly/" + slug, detail_content(edition, "/discover", "Discover", "monthly/" + slug, edition["published"], {"title": edition["essay_title"], "body": edition["essay"]}))


@router.get("/discover/{slug}")
def discover_detail(slug: str):
    t = trail_for(slug)
    if slug in GUIDES:
        guide = GUIDES[slug]
        canonical = 'https://omnitrackr.xyz/discover/' + slug
        return page(
            t['name'] + ' | Discover', guide['summary'], '/discover/' + slug,
            guide_content(slug, t, guide),
            structured_data={
                '@context': 'https://schema.org', '@type': 'Article',
                'headline': t['name'], 'description': guide['summary'],
                'datePublished': '2026-09-08', 'dateModified': guide['reviewed'],
                'mainEntityOfPage': canonical, 'url': canonical,
                'author': {'@type': 'Organization', 'name': 'OmniTrackr', 'url': 'https://omnitrackr.xyz/about'},
                'publisher': {'@type': 'Organization', 'name': 'OmniTrackr', 'url': 'https://omnitrackr.xyz/'},
                'inLanguage': 'en-US',
            },
        )
    return page(
        t["name"] + " | Discover",
        t["intro"],
        "/discover/" + slug,
        detail_content(t, "/discover", "All trails", slug, "September 8, 2026"),
        indexable=False,
    )


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
