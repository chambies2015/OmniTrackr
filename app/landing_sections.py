"""Guest homepage sections below the hero (Nov 2026): importing, the free tools and their live demo.

Everything here is built from data the app already has (switch_guides, binge_guides,
in_order_guides), so the homepage stays in step when a service or guide is added.
Nothing reads the database. public_root_html() swaps each block in for its marker
and leaves the marker's place empty if a block fails.
"""
from __future__ import annotations

from html import escape

# The 13 services the Import Studio reads, in the order people tend to arrive from.
# Kitsu has no guide page of its own: its export is the MyAnimeList XML format.
IMPORT_SERVICES = (
    ("letterboxd", "Letterboxd", "Films, ratings, diary"),
    ("goodreads", "Goodreads", "Books and shelves"),
    ("myanimelist", "MyAnimeList", "Anime and manga"),
    ("imdb", "IMDb", "Ratings and watchlist"),
    ("storygraph", "The StoryGraph", "Books and ratings"),
    ("anilist", "AniList", "Fetched by username"),
    ("trakt", "Trakt", "Movies and shows"),
    ("steam", "Steam", "Games and hours played"),
    ("spotify", "Spotify", "Albums and podcasts"),
    ("myanimelist#kitsu", "Kitsu", "Anime and manga"),
    ("podcast-apps", "Podcast apps", "OPML subscriptions"),
    ("rate-your-music", "Rate Your Music", "Album ratings"),
    ("libib", "Libib", "Books, films, music, games"),
)

# Series offered in the homepage's binge calculator demo (all have hand-checked guides).
BINGE_DEMO = ("breaking-bad", "the-office", "game-of-thrones", "stranger-things", "friends",
              "attack-on-titan", "one-piece", "naruto-and-shippuden")
BINGE_PACES = (1, 2, 4)
BINGE_DEFAULT_PACE = 2

# Franchise guides shown as chips on the in-order card.
IN_ORDER_CHIPS = ("marvel-cinematic-universe", "star-wars", "harry-potter", "zelda", "dragon-ball", "james-bond")


def import_section() -> str:
    from .switch_guides import GUIDES
    tiles = []
    for slug, name, note in IMPORT_SERVICES:
        base = slug.split("#", 1)[0]
        if base not in GUIDES:
            continue
        tiles.append(
            f'<li><a class="lp-import__svc" href="/switch/{escape(base, quote=True)}" data-home-tool="switch">'
            f'<span class="lp-import__mono" aria-hidden="true">{escape(name[0])}</span>'
            f'<span class="lp-import__name">{escape(name)}</span><span class="lp-import__what">{escape(note)}</span></a></li>'
        )
    count = len(tiles)
    return (
        '<section class="lp-section lp-import" id="import" aria-labelledby="lp-import-title"><div class="lp-wrap lp-import__grid">'
        '<div class="lp-import__copy">'
        '<p class="lp-eyebrow">Already tracking somewhere else?</p>'
        f'<h2 id="lp-import-title">Bring your history from {count} apps and sites</h2>'
        '<p>Years of ratings shouldn’t stay behind because you want films, books and games in one place. '
        'Upload the export file a service gives you and OmniTrackr reads it as it comes.</p>'
        '<ol class="lp-import__steps">'
        '<li><strong>Download your export.</strong> Each service’s page below shows where the button is.</li>'
        '<li><strong>Drop the file in.</strong> Ratings, finish dates and reviews come along where the file has them.</li>'
        '<li><strong>Check the preview.</strong> Nothing is added until you say so, and your own entries are never overwritten.</li>'
        '</ol>'
        '<div class="lp-import__actions">'
        '<a class="lp-btn lp-btn--primary" href="/?start=import#signup" rel="nofollow" data-home-import>Sign up and import</a>'
        '<a class="lp-link-arrow" href="/switch">How switching works <svg class="lp-icon" aria-hidden="true"><use href="#i-arrow"/></svg></a>'
        '</div></div>'
        f'<ul class="lp-import__list" aria-label="Services you can import from">{"".join(tiles)}</ul>'
        '</div></section>'
    )


def _hours(minutes: float) -> str:
    whole = int(round(minutes))
    hours, mins = divmod(whole, 60)
    return f"{hours:,} hours" + (f" {mins} min" if mins and hours < 100 else "")


def binge_demo_html() -> str:
    from . import binge_calculator
    options = []
    first = None
    for slug in BINGE_DEMO:
        entry = binge_calculator.guide(slug)
        if not entry:
            continue
        totals = binge_calculator.totals(entry)
        if not totals["minutes"] or not totals["episodes"]:
            continue
        item = {"slug": slug, "name": binge_calculator.card_name(entry), "minutes": int(round(totals["minutes"])),
                "episodes": int(totals["episodes"])}
        first = first or item
        options.append(
            f'<option value="{escape(slug, quote=True)}" data-minutes="{item["minutes"]}" data-episodes="{item["episodes"]}"'
            f'{" selected" if item is first else ""}>{escape(item["name"])}</option>'
        )
    if not first:
        return ""
    days = binge_calculator.days_at(first["minutes"], BINGE_DEFAULT_PACE)
    paces = "".join(
        f'<button type="button" class="lp-binge__pace" data-hours="{h}" aria-pressed="{"true" if h == BINGE_DEFAULT_PACE else "false"}">'
        f'{h} {"hour" if h == 1 else "hours"}</button>' for h in BINGE_PACES)
    return (
        '<article class="lp-tool lp-tool--binge" data-binge-demo>'
        '<p class="lp-tool__kicker">Binge calculator</p>'
        '<h3 class="lp-tool__title">How long will it take?</h3>'
        '<div class="lp-binge">'
        '<label class="lp-binge__label" for="lpBingeShow">Series</label>'
        f'<select id="lpBingeShow" class="lp-binge__select">{"".join(options)}</select>'
        '<p class="lp-binge__label" id="lpBingePaceLabel">Watching a day</p>'
        f'<div class="lp-binge__paces" role="group" aria-labelledby="lpBingePaceLabel">{paces}</div>'
        '<div class="lp-binge__result" aria-live="polite">'
        f'<p class="lp-binge__big"><strong data-binge-days>{days}</strong> <span data-binge-days-word>{"day" if days == 1 else "days"}</span></p>'
        f'<p class="lp-binge__detail" data-binge-detail>{first["episodes"]} episodes, about {_hours(first["minutes"])} in all.</p>'
        '<p class="lp-binge__finish" data-binge-finish hidden></p>'
        '</div></div>'
        f'<a class="lp-tool__link" href="/binge-calculator/{escape(first["slug"], quote=True)}" data-binge-link data-home-tool="binge">'
        f'See the season-by-season guide <svg class="lp-icon" aria-hidden="true"><use href="#i-arrow"/></svg></a>'
        '</article>'
    )


def tools_section(season_tile: str = "") -> str:
    from . import in_order
    from .in_order_guides import GUIDES as ORDER_GUIDES
    chips = []
    for slug in IN_ORDER_CHIPS:
        entry = ORDER_GUIDES.get(slug)
        if entry:
            chips.append(f'<li><a href="{escape(in_order.path(slug), quote=True)}" data-home-tool="in-order">{escape(entry["name"])}</a></li>')
    from .binge_guides import GUIDES as BINGE_GUIDES
    binge_count = len(BINGE_GUIDES)
    poll = (
        '<article class="lp-tool lp-tool--poll">'
        '<p class="lp-tool__kicker">Group poll</p>'
        '<h3 class="lp-tool__title">Settle movie night in one link</h3>'
        '<div class="lp-poll" aria-hidden="true">'
        '<p class="lp-poll__q">Friday, what are we watching?</p>'
        '<p class="lp-poll__row is-lead"><span>Dune: Part Two</span><b>4</b><i class="lp-poll__bar lp-poll__bar--4"></i></p>'
        '<p class="lp-poll__row"><span>Past Lives</span><b>2</b><i class="lp-poll__bar lp-poll__bar--2"></i></p>'
        '<p class="lp-poll__row"><span>Spirited Away</span><b>1</b><i class="lp-poll__bar lp-poll__bar--1"></i></p>'
        '</div>'
        '<p class="lp-tool__text">Pick a few titles, send the link to the group chat, and friends vote without making an account. '
        'The winner comes with where to watch it.</p>'
        '<a class="lp-tool__link" href="/tonight" data-home-tool="poll">Start a poll <svg class="lp-icon" aria-hidden="true"><use href="#i-arrow"/></svg></a>'
        '</article>'
    )
    order = (
        '<article class="lp-tool lp-tool--order">'
        '<p class="lp-tool__kicker">Franchises in order</p>'
        f'<h3 class="lp-tool__title">{len(ORDER_GUIDES)} series, in the order that makes sense</h3>'
        '<p class="lp-tool__text">Release order, story order and the shortcuts, with what each entry adds and what you can skip.</p>'
        f'<ul class="lp-chips">{"".join(chips)}</ul>'
        '<a class="lp-tool__link" href="/in-order" data-home-tool="in-order">All the guides <svg class="lp-icon" aria-hidden="true"><use href="#i-arrow"/></svg></a>'
        '</article>'
    )
    try:
        from . import top_nine
        nine = top_nine.tools_tile_html()
    except Exception:
        nine = ""
    small = (
        f'{nine}'
        '<li><a class="lp-try" href="/daily" data-home-tool="daily"><span class="lp-try__kicker">Daily game</span><strong>Guess the title</strong><span>A new puzzle every day, six guesses</span></a></li>'
        '<li><a class="lp-try" href="/tier-list" data-home-tool="tier-list"><span class="lp-try__kicker">Tool</span><strong>Tier list maker</strong><span>Rank anything and save the image</span></a></li>'
        '<li><a class="lp-try" href="/taste-quiz" data-home-tool="quiz"><span class="lp-try__kicker">One minute</span><strong>Taste quiz</strong><span>Answer a few and get picks across formats</span></a></li>'
        '<li><a class="lp-try" href="/pick" data-home-tool="pick"><span class="lp-try__kicker">Tool</span><strong>Pick for me</strong><span>Can’t decide? One suggestion at a time</span></a></li>'
        '<li><a class="lp-try" href="/if-you-liked" data-home-tool="liked"><span class="lp-try__kicker">Guides</span><strong>If you liked…</strong><span>What to try after the thing you just finished</span></a></li>'
        f'{season_tile}'
    )
    return (
        '<section class="lp-section lp-tools" id="free-tools" aria-labelledby="lp-tools-title"><div class="lp-wrap">'
        '<div class="lp-section-head lp-section-head--row"><div>'
        '<p class="lp-eyebrow">Free, no account needed</p>'
        '<h2 id="lp-tools-title">Tools people come back for</h2>'
        f'<p class="lp-tools__lead">Try them here. When you want to keep what you find, it saves to your library.</p></div>'
        '<a class="lp-link-arrow" href="/discover">Browse every guide <svg class="lp-icon" aria-hidden="true"><use href="#i-arrow"/></svg></a></div>'
        f'<div class="lp-tools__grid">{binge_demo_html()}{poll}{order}</div>'
        f'<ul class="lp-try-grid lp-tools__more">{small}</ul>'
        f'<p class="lp-tools__note">The binge calculator has {binge_count} hand-checked guides, from Breaking Bad to The Wheel of Time. '
        '<a href="/binge-calculator" data-home-tool="binge">Work out any series</a>. '
        'Or follow a Discover trail: <a href="/discover/one-evening-well-spent">an evening to yourself</a>, '
        '<a href="/discover/finding-your-feet">a fresh start</a> or <a href="/discover/beautifully-strange-worlds">somewhere strange</a>.</p>'
        '</div></section>'
    )
