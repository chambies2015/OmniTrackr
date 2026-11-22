"""Public editorial trails with authenticated, atomic library saves."""
from html import escape
import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from .. import models
from ..csp import strict_html_response
from ..site_chrome import apply_site_chrome
from ..dependencies import get_current_user, get_db
from .. import explore_art
from ..discover_catalog import CATEGORY_KIND, TRAILS, guest_fields, published_editions
from ..discover_guides import GUIDES
from .collections import CATEGORIES

router = APIRouter()


COUNT_WORDS = {4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine"}


def _count_word(count: int) -> str:
    return COUNT_WORDS.get(count, str(count))


def trail_for(slug):
    if slug not in TRAILS:
        raise HTTPException(404, "Trail not found")
    return TRAILS[slug]


def monthly_for(slug):
    editions = published_editions()
    if slug not in editions:
        raise HTTPException(404, "Monthly edition not found")
    return editions[slug]


# Sections that share this layout but have their own item in the site header.
NAV_SECTIONS = (("/in-order", "in-order"), ("/if-you-liked", "if-you-liked"), ("/daily", "daily"), ("/lists", "lists"),
                ("/pick", "pick"), ("/tonight", "tonight"), ("/taste-quiz", "taste-quiz"), ("/tier-list", "tier-list"), ("/challenges", "challenges"), ("/new-year-challenge", "challenges"),
                ("/best-of", "best-of"), ("/essentials", "essentials"), ("/new-releases", "new-releases"), ("/new-this-week", "new-this-week"), ("/halloween", ""), ("/holidays", ""), ("/valentines-day", ""), ("/binge-calculator", ""), ("/awards", "awards"), ("/start", ""),
                ("/ranked", ""))


DEFAULT_SHARE_IMAGE = ('<meta property="og:image" content="https://omnitrackr.xyz/omnitrackr_vortex.png">'
                       '<meta name="twitter:card" content="summary">')


TEMPLATE_KEYS = re.compile(r"\{\{(TITLE|DESCRIPTION|PATH|ROBOTS|CONTENT|STRUCTURED_DATA)\}\}")


def page(title, description, path, content, *, indexable=True, structured_data=None, head='', member=False,
         share_image=None, body_class=''):
    template = (Path(__file__).parents[1] / "templates" / "discover.html").read_text(encoding="utf-8")
    if body_class:
        # Discover's own pages share covers, format colours and the save dock with trending and the shelves.
        template = template.replace('<body class="dark-mode discover-page site">',
                                    f'<body class="dark-mode discover-page site explore {escape(body_class, quote=True)}">', 1)
        head = explore_art.STYLESHEET + head
    nav = next((key for prefix, key in NAV_SECTIONS if path == prefix or path.startswith(prefix + "/")), "discover")
    # Pages only signed-in members see point the header at their library, not at signing up.
    html = apply_site_chrome(template.replace("<!--SITE_NAV:discover-->", f"<!--SITE_NAV:{nav}-->", 1), member=member)
    robots = "index, follow, max-image-preview:large" if indexable else "noindex, follow"
    if share_image:
        # A 1200x630 card of the page's own (a full https URL) in place of the site logo.
        image = escape(share_image, quote=True)
        html = html.replace(DEFAULT_SHARE_IMAGE, (
            f'<meta property="og:image" content="{image}"><meta property="og:image:width" content="1200">'
            '<meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image">'
            f'<meta name="twitter:image" content="{image}">'), 1)
    # Escape script delimiters even though the editorial catalog is maintained in code.
    structured = ''
    if structured_data:
        payload = json.dumps(structured_data, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
        structured = f'<script type="application/ld+json">{payload}</script>'
    values = {"TITLE": escape(title), "DESCRIPTION": escape(description, quote=True), "PATH": path, "ROBOTS": robots,
              "CONTENT": content, "STRUCTURED_DATA": structured + head}
    # One pass over the template, so a member's own text that happens to read "{{CONTENT}}" (a list or
    # title name on a shared page) stays text instead of pulling the page into itself.
    html = TEMPLATE_KEYS.sub(lambda match: values[match.group(1)], html)
    response = strict_html_response(html)
    if not indexable:
        response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


DISCOVER_DESCRIPTION = (
    "Trails that link movies, TV, anime, games, music and books through one shared idea, "
    "with why each pick fits, a fair caveat and a source. Free to read."
)


def _covers(db, items) -> dict:
    """(category, title) -> cached poster for Discover picks; picks without one get a drawn cover."""
    wanted = {}
    for item in items:
        kind = CATEGORY_KIND.get(item["category"])
        if kind:
            wanted[(item["category"], item["title"])] = (kind, item["title"], item.get("meta", {}).get("year"))
    if db is None or not wanted:
        return {}
    try:
        found = explore_art.cached_posters(db, wanted.values())
    except Exception:  # Art is decoration: a cache problem must never take the page down.
        return {}
    return {key: found[value] for key, value in wanted.items() if value in found}


def _pick_cover(item, covers, **options) -> str:
    kind = CATEGORY_KIND.get(item["category"], "")
    return explore_art.cover(item["title"], kind, covers.get((item["category"], item["title"])), **options)


def _trail_card(slug, trail, covers) -> str:
    guide_label = '<span class="trail-guide-label">In-depth guide</span>' if slug in GUIDES else ''
    categories = " ".join(item["category"] for item in trail["items"])
    titles = " · ".join(item["title"] for item in trail["items"])
    creators = " ".join(str(value) for item in trail["items"] for value in item["meta"].values())
    search = " ".join((trail["name"], trail["tag"], trail["intro"], titles, creators))
    href = f'/discover/{escape(slug, quote=True)}'
    fan = "".join(_pick_cover(item, covers, width=100) for item in trail["items"])
    picks = "".join(f'<li data-kind="{CATEGORY_KIND.get(item["category"], "")}"><span class="x-kind" data-kind="{CATEGORY_KIND.get(item["category"], "")}">'
                    f'{escape(CATEGORIES[item["category"]][1])}</span>{escape(item["title"])}</li>' for item in trail["items"])
    return (f'<article class="trail" data-formats="{escape(categories, quote=True)}" data-search="{escape(search, quote=True)}">'
            f'<a class="trail__fan" href="{href}" tabindex="-1" aria-hidden="true">{fan}</a>'
            f'<div class="trail__body"><div class="trail__top"><p class="eyebrow">{escape(trail["tag"])}</p>{guide_label}</div>'
            f'<h3><a href="{href}">{escape(trail["name"])}</a></h3><p class="trail__intro">{escape(trail["intro"])}</p>'
            f'<ul class="trail__picks" aria-label="Inside this trail">{picks}</ul>'
            f'<a class="trail__go" href="{href}">Explore this trail <span aria-hidden="true">→</span></a></div></article>')


@router.get("/discover")
def discover_index(db: Session = Depends(get_db)):
    editions = published_editions()
    edition_slug, edition = next(reversed(editions.items()))
    covers = _covers(db, [item for trail in TRAILS.values() for item in trail["items"]] + list(edition["items"]))
    cards = [_trail_card(slug, trail, covers) for slug, trail in TRAILS.items()]
    used = {item["category"] for trail in TRAILS.values() for item in trail["items"]}
    options = ''.join(f'<option value="{category}">{label}</option>' for category, (_, label) in CATEGORIES.items())
    chips = '<button type="button" class="dx-chip" data-format="" aria-pressed="true">Any format</button>' + ''.join(
        f'<button type="button" class="dx-chip" data-format="{category}" data-kind="{CATEGORY_KIND[category]}" aria-pressed="false">{escape(label)}</button>'
        for category, (_, label) in CATEGORIES.items() if category in used)
    filters = (
        '<section id="trail-filters" class="trail-filters" aria-label="Find a trail" hidden>'
        '<div class="trail-filter-fields"><div class="dx-search"><label for="trail-search" class="dx-sr">What are you curious about?</label>'
        '<input id="trail-search" type="search" maxlength="100" placeholder="Search by title, creator or theme" aria-controls="trail-list"></div>'
        f'<div class="dx-chips" role="group" aria-label="Include a format">{chips}</div>'
        f'<div class="dx-format"><label for="trail-format">Include a format</label><select id="trail-format" aria-controls="trail-list"><option value="">Any format</option>{options}</select></div>'
        '<button id="trail-reset" type="button" class="filter-reset">Clear filters</button></div>'
        '<p id="trail-results" class="muted" role="status" aria-live="polite" aria-atomic="true"></p></section>'
    )
    edition_href = f'/discover/monthly/{escape(edition_slug, quote=True)}'
    edition_picks = "".join(
        f'<li><a href="{edition_href}#picks">{_pick_cover(item, covers)}'
        f'<span class="dx-edition__label"><span class="x-kind" data-kind="{CATEGORY_KIND.get(item["category"], "")}">{escape(CATEGORIES[item["category"]][1])}</span>'
        f'<b>{escape(item["title"])}</b></span></a></li>' for item in edition["items"])
    edition_card = (
        f'<section class="monthly-feature dx-edition" aria-labelledby="edition-heading"><div class="dx-edition__copy">'
        f'<p class="eyebrow">{escape(edition["tag"])}</p><h2 id="edition-heading">{escape(edition["name"])}</h2><p>{escape(edition["intro"])}</p>'
        f'<p class="muted">{escape(edition["published"])} · {_count_word(len(edition["items"]))} media types · One place to start in each</p>'
        f'<a class="button" href="{edition_href}">Read this edition →</a></div>'
        f'<ol class="dx-edition__picks" aria-label="In this edition">{edition_picks}</ol></section>')
    archive_items = ''.join(
        f'<li><a href="/discover/monthly/{escape(slug, quote=True)}">{escape(item["name"])}</a>'
        f'<span>{escape(item["intro"])}</span></li>'
        for slug, item in reversed(list(editions.items()))
        if slug != edition_slug
    )
    tiles = []
    from .. import seasonal
    season_slug = seasonal.current()
    if season_slug:
        season = seasonal.season(season_slug)
        tiles.append(
            f'<article class="dx-tile" data-tone="season"><p class="eyebrow">SEASONAL · {escape(season["name"].upper())}</p>'
            f'<h3>{escape(season["headline"])}</h3><p>{escape(season["deck"])}</p>'
            f'<a class="dx-tile__go" href="{escape(season["path"], quote=True)}">See the {escape(season["name"])} picks →</a></article>')
    from .. import challenges
    challenge_months = challenges.public_months()
    if challenge_months and challenge_months[0] == challenges.month_key():
        month = challenge_months[0]
        challenge = challenges.CHALLENGES[month]
        tiles.append(
            f'<article class="dx-tile" data-tone="challenge"><p class="eyebrow">MONTHLY CHALLENGE · {escape(challenges.month_label(month).upper())}</p>'
            f'<h3>{escape(challenge["name"])}</h3><p>{escape(challenge["tagline"])}</p>'
            f'<a class="dx-tile__go" href="/challenges/{challenges.slug_for(month)}">See this month\'s challenge →</a></article>')
    from ..if_you_liked_guides import GUIDES as LIKED_GUIDES
    liked_links = "".join(
        f'<li><a href="/if-you-liked/{escape(slug, quote=True)}">{escape(guide["anchor"]["title"])}</a></li>'
        for slug, guide in LIKED_GUIDES.items()
    )
    tiles.append(
        '<article class="dx-tile dx-tile--wide" data-tone="liked"><p class="eyebrow">IF YOU LIKED</p>'
        '<h3>Just finished something you loved?</h3>'
        f'<p>Guides to what to try next, across formats:</p><ul class="dx-tile__links">{liked_links}</ul>'
        '<a class="dx-tile__go" href="/if-you-liked">See every guide →</a></article>')
    more = ('<section class="dx-more" aria-labelledby="more-heading"><h2 id="more-heading" class="dx-heading">More ways in</h2>'
            f'<div class="dx-tiles">{"".join(tiles)}</div></section>')
    archive = (
        '<section class="editorial monthly-archive"><h2>Past monthly editions</h2>'
        f'<ul>{archive_items}</ul></section>' if archive_items else ''
    )
    trail_links = [
        {"@type": "ListItem", "position": position, "name": trail["name"], "url": f"https://omnitrackr.xyz/discover/{slug}"}
        for position, (slug, trail) in enumerate(TRAILS.items(), start=1)
    ]
    structured = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": "Discover: what to watch, play, read or hear next", "url": "https://omnitrackr.xyz/discover",
        "description": DISCOVER_DESCRIPTION, "inLanguage": "en-US",
        "isPartOf": {"@type": "WebSite", "name": "OmniTrackr", "url": "https://omnitrackr.xyz/"},
        "mainEntity": {"@type": "ItemList", "itemListElement": trail_links},
    }
    # The hero wall: picks that already have art first, so the first screen is mostly real covers.
    wall_items = sorted((item for trail in TRAILS.values() for item in trail["items"]),
                        key=lambda item: (item["category"], item["title"]) not in covers)[:9]
    wall = "".join(_pick_cover(item, covers, eager=index < 3) for index, item in enumerate(wall_items))
    hero = ('<header class="hero dx-hero"><div class="dx-hero__copy"><p class="eyebrow">SIX MEDIA TYPES. NEW CONNECTIONS.</p>'
            '<h1>Follow your curiosity.</h1><p>Find your next watch, read, listen or play through a shared idea. '
            'Explore freely, then save the picks that feel like you.</p>'
            f'<div class="dx-hero__actions"><a class="button" href="#trails">Browse {len(TRAILS)} trails</a>'
            f'<a class="dx-hero__link" href="{edition_href}">Read the {escape(edition["published"])} edition →</a></div></div>'
            f'<div class="dx-hero__wall" aria-hidden="true">{wall}</div></header>')
    trails = (f'<section id="trails" class="dx-trails" aria-labelledby="trails-heading"><div class="dx-trails__head">'
              f'<h2 id="trails-heading" class="dx-heading">Trails to follow</h2>'
              '<p>Each trail links four picks in four formats through one idea.</p></div>'
              + filters + '<p id="trail-empty" class="trail-empty" hidden>No trails match yet. Try a broader theme or choose Any format.</p>'
              '<div id="trail-list" class="trails">' + ''.join(cards) + '</div></section>')
    how = ('<section class="editorial"><h2>How these trails work</h2><p>These are editorial suggestions, not rankings or user reviews. '
           'Each pick has a reason to be here, a caveat, and a source for learning more. Start with one; there is no need to finish a whole collection.</p>'
           '<p>Saving one pick needs no account: it waits in your browser until you sign up. Saving a whole trail as a collection needs an account. '
           'You choose which titles to add, and can review existing matches before confirming.</p></section>')
    return page("Discover: what to watch, play, read or hear next", DISCOVER_DESCRIPTION, "/discover",
                hero + edition_card + trails + more + archive + how, structured_data=structured, body_class="discover-hub")


def _notes_section(notes) -> str:
    if not notes:
        return ""
    return (f'<section id="edition-notes" class="editorial edition-notes" aria-labelledby="edition-notes-heading">'
            f'<h2 id="edition-notes-heading">{escape(notes["heading"])}</h2>'
            + "".join(f'<p>{escape(text)}</p>' for text in notes["paragraphs"]) + _notes_links(notes.get("links"))
            + '</section>')


def _notes_links(links) -> str:
    """Pages an edition points to instead of repeating them (November 2027 onward): internal paths only."""
    rows = "".join(f'<li><a href="{escape(href, quote=True)}">{escape(label)}</a></li>' for label, href in links or ()
                   if isinstance(href, str) and href.startswith("/") and not href.startswith("//"))
    return f'<ul class="edition-links">{rows}</ul>' if rows else ""


def _long_date(value: str) -> str:
    parsed = date.fromisoformat(value)
    return f"{parsed:%B} {parsed.day}, {parsed.year}"


def _byline(trail, published) -> str:
    """'By OmniTrackr' plus the last-checked date, or the publish date when a trail was never rechecked."""
    if trail.get("reviewed"):
        stamp = (f'Updated <time datetime="{escape(trail["reviewed"], quote=True)}">'
                 f'{escape(_long_date(trail["reviewed"]))}</time>')
    elif trail.get("published_date"):
        stamp = (f'Published <time datetime="{escape(trail["published_date"], quote=True)}">'
                 f'{escape(_long_date(trail["published_date"]))}</time>')
    else:
        stamp = f'Published {escape(published)}'
    return f'<p class="guide-byline">By <a href="/about">OmniTrackr</a> · {stamp}</p>'


GUEST_LIST_JS = "/static/guest-list.js?v=20261122-shelf-1"
GUEST_HEAD = f'<script src="{GUEST_LIST_JS}" defer></script>'


def _guest_save(item) -> str:
    """A visitor's one-tap save for a pick (browser-only list, guest-list.js); hidden for members."""
    fields = guest_fields(item)
    if fields is None:
        return ""
    return (f'<button type="button" class="pick-save x-save" data-guest-only data-guest-save aria-pressed="false" '
            f'data-guest-kind="{escape(fields["kind"], quote=True)}" data-guest-slug="{escape(fields["slug"], quote=True)}" '
            f'data-guest-title="{escape(fields["title"], quote=True)}">Save to my list</button>')


# Rises from the bottom of the screen once a visitor has saved a pick (guest-list.js shows and fills it).
GUEST_BAR = explore_art.dock("Keep my list")
GUEST_PANEL_NOTE = ('<p class="save-panel__guest" data-guest-only>No account yet? Press <strong>Save to my list</strong> on any pick above. '
                    'Your list waits in this browser and moves into your library when you sign up.</p>')


def _other_version(item) -> str:
    """The pick's version in another format, for editions that name one (July 2027 onward), the best-known
    work by the same maker, for editions that name that instead (August 2027), or where the pick has been
    taught, for editions about set texts (September 2027), or the bargain at the heart of the story, for
    editions about wishes granted at a price (October 2027), who tells the story, for editions about
    storytellers (November 2027), or the time machine, for editions about time travel (December 2027)."""
    teller = item.get("teller")
    if teller and teller.get("note"):
        return f'<p class="pick-other"><strong>Who\'s telling it:</strong> {escape(teller["note"])}</p>'
    machine = item.get("machine")
    if machine and machine.get("note"):
        return f'<p class="pick-other"><strong>The time machine:</strong> {escape(machine["note"])}</p>'
    bargain = item.get("bargain")
    if bargain and bargain.get("note"):
        return f'<p class="pick-other"><strong>The bargain:</strong> {escape(bargain["note"])}</p>'
    classroom = item.get("classroom")
    if classroom and classroom.get("note"):
        return f'<p class="pick-other"><strong>In the classroom:</strong> {escape(classroom["note"])}</p>'
    shadow = item.get("shadow")
    if shadow and shadow.get("title") and shadow.get("note"):
        return (f'<p class="pick-other"><strong>In the shadow of {escape(shadow["title"])}:</strong> '
                f'{escape(shadow["note"])}</p>')
    other = item.get("other")
    if not other or other.get("category") not in CATEGORIES:
        return ""
    label = CATEGORIES[other["category"]][1]
    label = label if label == "TV show" else label.lower()
    return f'<p class="pick-other"><strong>Pair it with the {escape(label)}:</strong> {escape(other["note"])}</p>'


def detail_content(trail, back_path, back_label, api_path, published, essay=None, covers=None):
    covers = covers or {}
    items = "".join(f'<article class="pick dx-pick" data-kind="{CATEGORY_KIND.get(i["category"], "")}">{_pick_cover(i, covers)}<p class="eyebrow">{n:02d} / {CATEGORIES[i["category"]][1]}</p><h2>{escape(i["title"])}</h2><p>{escape(i["why"])}</p><p class="caveat">{escape(i["caveat"])}</p>{_other_version(i)}<div class="pick-actions">{_guest_save(i)}<a href="{escape(i["source"], quote=True)}" rel="noopener noreferrer" target="_blank">Source / learn more ↗</a></div></article>' for n, i in enumerate(trail["items"], 1))
    essay_section = ""
    if essay:
        essay_section = f'<section id="essay" class="editorial edition-essay"><h2>{escape(essay["title"])}</h2><p>{escape(essay["body"])}</p></section>'
    jump = "".join(f'<a href="#{target}">{label}</a>' for target, label in (
        ("essay", escape(essay["title"]) if essay else ""), ("start-here", "Where to start"), ("picks", "The picks"),
        ("edition-notes", escape(trail["notes"]["heading"]) if trail.get("notes") else ""),
        ("take-away", "Take something with you"), ("save-picks", "Save your picks")) if label)
    signin = '/?next=' + quote('/discover/' + api_path + '#save-picks', safe='') + '#landing-auth'
    checked = (f' · Updated <time datetime="{escape(trail["reviewed"], quote=True)}">{escape(_long_date(trail["reviewed"]))}</time>'
               if trail.get("reviewed") else "")
    return f'<article class="trail-guide trail-edition"><header class="hero hero--guide"><a href="{back_path}">← {escape(back_label)}</a><p class="eyebrow">{escape(trail["tag"])}</p><h1>{escape(trail["name"])}</h1><p class="guide-deck">{escape(trail["intro"])}</p>{_byline(trail, published)}<nav class="guide-jump" aria-label="On this page">{jump}</nav></header>{essay_section}<section id="start-here" class="editorial"><h2>Choose your starting point</h2><p>{escape(trail["guide"])}</p></section><div id="picks" class="picks">{items}</div>{GUEST_BAR}{_notes_section(trail.get("notes"))}<section id="take-away" class="editorial"><h2>Take something with you</h2><p>{escape(trail["prompt"])}</p><p class="muted">Editorial suggestions, prepared by OmniTrackr and reviewed by the site owner · Published {escape(published)}{checked}. Source links are informational, not affiliate links. Availability varies by region. <a href="/contact">Send a correction</a> · <a href="/content-quality">Editorial standards</a></p></section><section id="save-picks" class="save-panel" data-trail="{escape(api_path, quote=True)}"><h2>Make this collection yours</h2><p>Preview your library matches, then select the titles you want in a private collection. Existing ratings, reviews and progress are preserved.</p>{GUEST_PANEL_NOTE}<button id="preview" type="button">Preview saving</button><a id="signin" rel="nofollow" href="{escape(signin, quote=True)}" hidden>Sign in or create an account to continue here →</a><form id="saveForm" hidden><fieldset id="choices"><legend>Titles to save</legend></fieldset><button id="save" type="submit">Save selected picks</button></form><p id="status" role="status" aria-live="polite"></p><noscript><p>Enable JavaScript to preview and save picks. You can read every recommendation without it.</p></noscript></section></article>'


def paragraphs(values):
    return ''.join(f'<p>{escape(value)}</p>' for value in values)


def guide_content(slug, trail, guide, covers=None):
    """Render the curated guides without requiring scripts, accounts, or private data."""
    covers = covers or {}
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
            f'<article id="pick-{escape(key, quote=True)}" class="pick dx-pick" data-kind="{CATEGORY_KIND.get(item["category"], "")}">'
            f'{_pick_cover(item, covers)}<p class="eyebrow">{index:02d} / {escape(CATEGORIES[item["category"]][1])}</p>',
            f'<h3>{escape(item["title"])}</h3><p>{escape(item["why"])}</p>',
            paragraphs(guide['item_notes'][key]),
            f'<p class="caveat">{escape(item["caveat"])}</p>',
            f'<div class="pick-actions">{_guest_save(item)}<a class="guide-source-link" href="#source-{escape(key, quote=True)}">Source: {escape(source_by_key[key]["label"])} ↓</a></div></article>',
        ])
    parts.extend([
        '</div>', GUEST_BAR, '</section><section class="editorial guide-reflection"><h2>Take something with you</h2>',
        f'<p>{escape(trail["prompt"])}</p><p>Keep a short note about what drew you in and whether it suited the time you had. You do not need to finish the whole list; the note will help more next time you pick.</p></section>',
        '<section id="related-trails" class="guide-related" aria-labelledby="related-heading"><p class="eyebrow">FOLLOW ANOTHER THREAD</p><h2 id="related-heading">Where to go next</h2><div class="guide-related-grid">',
    ])
    for related in guide['related']:
        target = TRAILS[related['slug']]
        parts.append(f'<article><h3><a href="/discover/{escape(related["slug"], quote=True)}">{escape(target["name"])}</a></h3><p>{escape(related["reason"])}</p></article>')
    parts.extend([
        '</div></section><section id="guide-sources" class="guide-sources" aria-labelledby="sources-heading">',
        '<h2 id="sources-heading">Sources &amp; editorial method</h2>',
        '<div id="editorial-method"><p>Prepared by OmniTrackr and reviewed by the site owner before publishing. Factual context was checked against the official sources below; comparisons, mood descriptions, and suggested starting points are editorial interpretations.</p>',
        '<p>Reading and game time varies by person; suggested stopping points are places to begin and say nothing about how long a title takes to finish. Source links are informational, not affiliate links. Availability varies by region.</p>',
        f'<p class="muted">First published September 8, 2026. Guide expanded and sources checked {escape(reviewed)}. <a href="/contact">Send a correction</a> · <a href="/content-quality">Editorial standards</a></p></div><ol>',
    ])
    for source in guide['sources']:
        parts.append(f'<li id="source-{escape(source["key"], quote=True)}"><a href="{escape(source["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{escape(source["label"])} ↗</a><p>{escape(source["supports"])}</p></li>')
    # The same markup and selectors used by the established preview/save script.
    signin = '/?next=' + quote('/discover/' + slug + '#save-picks', safe='') + '#landing-auth'
    parts.extend([
        '</ol></section>',
        f'<section id="save-picks" class="save-panel" data-trail="{escape(slug, quote=True)}"><h2>Make this collection yours</h2>',
        '<p>Preview your library matches, then select the titles you want in a private collection. Existing ratings, reviews and progress are preserved.</p>',
        GUEST_PANEL_NOTE,
        '<button id="preview" type="button">Preview saving</button>',
        f'<a id="signin" rel="nofollow" href="{escape(signin, quote=True)}" hidden>Sign in or create an account to continue here →</a>',
        '<form id="saveForm" hidden><fieldset id="choices"><legend>Titles to save</legend></fieldset><button id="save" type="submit">Save selected picks</button></form>',
        '<p id="status" role="status" aria-live="polite"></p><noscript><p>Enable JavaScript to preview and save picks. You can read every recommendation without it.</p></noscript></section></article>',
    ])
    return ''.join(parts)


@router.get("/discover/monthly/{slug}")
def monthly_detail(slug: str, db: Session = Depends(get_db)):
    edition = monthly_for(slug)
    canonical = "https://omnitrackr.xyz/discover/monthly/" + slug
    return page(
        edition["name"] + " | Discover",
        edition["intro"],
        "/discover/monthly/" + slug,
        detail_content(edition, "/discover", "Discover", "monthly/" + slug, edition["published"], {"title": edition["essay_title"], "body": edition["essay"]},
                       covers=_covers(db, edition["items"])),
        head=GUEST_HEAD, body_class="discover-trail",
        structured_data={
            "@context": "https://schema.org", "@type": "Article",
            "headline": edition["name"], "description": edition["intro"],
            "datePublished": edition["published_date"],
            "dateModified": edition.get("reviewed", edition["published_date"]),
            "mainEntityOfPage": canonical, "url": canonical,
            "author": {"@type": "Organization", "name": "OmniTrackr", "url": "https://omnitrackr.xyz/about"},
            "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": "https://omnitrackr.xyz/"},
            "inLanguage": "en-US",
        },
    )


@router.get("/discover/{slug}")
def discover_detail(slug: str, db: Session = Depends(get_db)):
    t = trail_for(slug)
    covers = _covers(db, t["items"])
    if slug in GUIDES:
        guide = GUIDES[slug]
        canonical = 'https://omnitrackr.xyz/discover/' + slug
        return page(
            guide.get('search_title') or t['name'] + ' | Discover', guide['summary'], '/discover/' + slug,
            guide_content(slug, t, guide, covers),
            head=GUEST_HEAD, body_class="discover-trail",
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
        detail_content(t, "/discover", "All trails", slug, "September 8, 2026", covers=covers),
        indexable=False,
        head=GUEST_HEAD, body_class="discover-trail",
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
    # An edition can cover all nine formats (January 2027 is the first that does).
    keys: list[str] = Field(min_length=1, max_length=9)


@router.post("/api/discover/{slug}/save")
def save(slug: str, selection: SaveSelection, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'private, no-store'
    return save_for(trail_for(slug), selection, user, db, "Discover")


@router.post("/api/discover/monthly/{slug}/save")
def monthly_save(slug: str, selection: SaveSelection, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'private, no-store'
    return save_for(monthly_for(slug), selection, user, db, "Monthly Edition")


def _library_fields(item) -> dict:
    """A pick's meta as library columns. Games keep a release date, not a year, so a game pick's year
    becomes January 1 of that year, the same as Pick for me saves it."""
    fields = dict(item["meta"])
    if item["category"] == "video-games" and "year" in fields:
        year = fields.pop("year")
        fields["release_date"] = datetime(year, 1, 1) if year else None
    return fields


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
                media = CATEGORIES[item["category"]][0](user_id=user.id, title=item["title"], **_library_fields(item))
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
