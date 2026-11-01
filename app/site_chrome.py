"""Shared header and footer for every public (signed-out) page.

Templates opt in with two markers:

    <!--SITE_NAV:guides-->   the key of the nav item to mark as current (or empty)
    <!--SITE_FOOTER-->

Keeping the markup in one place means a new public page, a renamed section,
or a new footer link is a one-line change instead of an edit to every template.
Styles live in /static/site.css.
"""
from __future__ import annotations

import re
from datetime import date
from html import escape

SITE_CSS_VERSION = "20261031-join-1"
SITE_JS_VERSION = "20261028-nav-1"
SITE_NAV_JS_VERSION = "20261031-join-1"
# Pages holding this marker (the demo) skip site-nav.js, which reads the stored
# sign-in hint and calls the title search API; their search button stays a link.
SANDBOX_MARKER = "<!--SITE_SANDBOX-->"
VISIT_JS_VERSION = "20261030-people-1"

# The header groups every public section into four menus. Each entry is
# (key, label, href, one-line description); a page passes the key of its own
# entry to mark it, and the menu holding it, as current. On phones and tablets
# the same groups fill the compact menu, so a new page is a one-line change.
NAV_MENUS = (
    ("explore", "Explore", (
        ("discover", "Discover", "/discover", "Trails that connect film, TV, games, books and more"),
        ("best-of", "Best of 2026", "/best-of", "The year's standouts, with why each one earned it"),
        ("release-radar", "Release Radar", "/release-radar", "Out this week and coming soon"),
        ("new-releases", "Release guides", "/new-releases", "The month's new releases worth your time"),
        ("titles", "Popular & trending", "/titles", "Most tracked, trending now and top rated"),
        ("browse", "Browse shelves", "/browse", "Manga, podcasts and audiobooks to start with"),
    )),
    ("play", "Play", (
        ("daily", "Daily puzzle", "/daily", "One new guessing game every day"),
        ("pick", "Pick for me", "/pick", "One pick for you, or a vote with friends"),
        ("taste-quiz", "Taste quiz", "/taste-quiz", "Find out what kind of fan you are"),
        ("tier-list", "Tier list maker", "/tier-list", "Rank anything and share the image"),
        ("challenges", "Monthly challenge", "/challenges", "A themed goal that resets each month"),
    )),
    ("guides", "Guides", (
        ("in-order", "Franchises in order", "/in-order", "Watch and play the big series the right way"),
        ("if-you-liked", "If you liked…", "/if-you-liked", "What to try next after a favorite"),
        ("guides", "All guides", "/guides", "How to track, import, review and more"),
        ("switch", "Switch trackers", "/switch", "Bring your lists over from another site"),
        ("faq", "FAQ", "/faq", "Quick answers about accounts and features"),
    )),
    ("community", "Community", (
        ("reviews", "Member reviews", "/reviews", "Thoughtful reviews written by members"),
        ("collections", "Collections", "/collections/explore", "Themed lists people put together"),
        ("lists", "Shared lists & clubs", "/lists", "Plan what to watch or read with friends"),
        ("supporters", "Supporters", "/supporters", "The people who keep the site running"),
    )),
)
# Flat (key, label, href) view of every header entry, in menu order.
NAV_ITEMS = tuple((key, label, href) for _, _, items in NAV_MENUS for key, label, href, _ in items)

# Pages that are one view of a bigger header entry. They pass their own key and
# the header marks the entry they belong to.
NAV_ALIASES = {"tonight": "pick", "new-this-week": "release-radar", "charts": "titles", "trending": "titles"}

# Pairs of pages that answer the same question in two ways. Each page in a pair
# shows a small switch at the top so the two read as one feature.
# group -> ((key, label, href, hint), ...)
VIEW_SWITCHES = {
    "pick": (
        ("pick", "Just me", "/pick", "One pick, no scrolling"),
        ("tonight", "With friends", "/tonight", "Everyone votes on a shortlist"),
    ),
    "releases": (
        ("release-radar", "Coming up", "/release-radar", "Dates for the months ahead"),
        ("new-this-week", "Out this week", "/new-this-week", "Monday to Sunday, with what members finished"),
    ),
    "titles": (
        ("titles", "Most tracked", "/titles", "On the most member lists"),
        ("trending", "Trending", "/trending", "What members picked up this week"),
        ("charts", "Top rated", "/titles/movie", "Ranked by member ratings"),
    ),
}

FOOTER_GROUPS = (
    ("Explore", (
        ("Discover", "/discover"),
        ("Best of 2026", "/best-of"),
        ("Release Radar", "/release-radar"),
        ("Release guides", "/new-releases"),
        ("New this week", "/new-this-week"),
        ("Popular titles", "/titles"),
        ("Trending this week", "/trending"),
        ("Member charts", "/titles/movie"),
        ("Franchises in order", "/in-order"),
        ("If you liked…", "/if-you-liked"),
    )),
    ("Play", (
        ("Daily puzzle", "/daily"),
        ("Pick for me", "/pick"),
        ("Group poll", "/tonight"),
        ("Taste quiz", "/taste-quiz"),
        ("Tier list maker", "/tier-list"),
        ("Binge calculator", "/binge-calculator"),
        ("Monthly challenge", "/challenges"),
    )),
    ("Community", (
        ("Member reviews", "/reviews"),
        ("Collections", "/collections/explore"),
        ("Shared lists & clubs", "/lists"),
        ("Supporters", "/supporters"),
        ("Interactive demo", "/demo"),
        ("Sample library", "/sample-library"),
    )),
    ("Learn", (
        ("Guides", "/guides"),
        ("Tracking hub", "/media-tracking"),
        ("Switch from another tracker", "/switch"),
        ("Import & backups", "/export-import-guide"),
        ("Review guide", "/review-guidelines"),
        ("Compare trackers", "/compare"),
        ("Ways to use OmniTrackr", "/use-cases"),
        ("FAQ", "/faq"),
    )),
    ("OmniTrackr", (
        ("About", "/about"),
        ("What's new", "/changelog"),
        ("Roadmap", "/roadmap"),
        ("Editorial standards", "/content-quality"),
        ("Site map", "/site-map"),
    )),
)
# The legal links also sit on their own line under the columns, where people look for them.
FOOTER_LEGAL = (("Privacy", "/privacy"), ("Terms", "/terms"), ("Ads & affiliates", "/advertising"), ("Contact", "/contact"))

# A short sign-up prompt above the footer for signed-out readers of the section
# hubs most visitors arrive on from search. Pages that already ask in their own
# words (any "/#signup" link of their own) are skipped. nav key -> (heading, text).
_RELEASES_JOIN = ("Hear about it on release day",
                  "Track a movie, show, anime or game from this list and OmniTrackr tells you the day it comes out, "
                  "along with new seasons and sequels of what you already follow. Free, and your library stays private.")
_PICKS_JOIN = ("Keep the ones that catch your eye",
               "Save picks to a free OmniTrackr library, then mark them finished and rate them as you go. "
               "Your list stays private unless you share it.")
JOIN_PROMPTS = {
    "release-radar": _RELEASES_JOIN,
    "new-this-week": _RELEASES_JOIN,
    "new-releases": _RELEASES_JOIN,
    "discover": _PICKS_JOIN,
    "best-of": _PICKS_JOIN,
    "in-order": ("Keep your place in the series",
                 "Add a franchise to a free OmniTrackr library and tick off each film, book or game as you finish it. "
                 "Your list stays private unless you share it."),
    "if-you-liked": _PICKS_JOIN,
    "guides": ("Try it with your own list",
               "Start a free library and bring your ratings over from Letterboxd, Goodreads, MyAnimeList and others, "
               "or add titles one at a time."),
}


def join_prompt(key: str) -> str:
    heading, text = JOIN_PROMPTS[key]
    return (
        '<section class="site-join" data-site-join data-guest-only aria-labelledby="site-join-heading">'
        f'<div><h2 id="site-join-heading">{escape(heading)}</h2><p>{escape(text)}</p></div>'
        '<div class="site-join__actions"><a class="site-btn site-btn--primary site-btn--md" href="/#signup">Create a free account</a>'
        '<a class="site-btn site-btn--ghost site-btn--md" href="/demo">Try the demo first</a></div>'
        '</section>'
    )


JOIN_MARKER = re.compile(r"<!--SITE_JOIN:([a-z-]+)-->")


def fill_join_prompt(html: str) -> str:
    """Swap the join marker for the prompt, unless the page already asks visitors to sign up.

    Runs on the finished page (html_finish), because several routers add their
    own content, including their own sign-up sections, after the header and
    footer are applied. Sign-up links in the header and footer don't count.
    """
    marker = JOIN_MARKER.search(html)
    if not marker:
        return html
    body_start = html.find("</header>")
    footer_start = html.find('<footer class="site-footer"')
    body = html[body_start if body_start != -1 else 0: footer_start if footer_start != -1 else len(html)]
    key = marker.group(1)
    prompt = join_prompt(key) if key in JOIN_PROMPTS and 'href="/#signup"' not in body else ""
    return JOIN_MARKER.sub("", html.replace(marker.group(0), prompt, 1))


NAV_MARKER = re.compile(r"<!--SITE_NAV:([a-z-]*)-->")
FOOTER_MARKER = "<!--SITE_FOOTER-->"

_SEARCH_ICON = ('<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" '
                'stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>')
_CHEVRON = ('<svg class="site-dd__chev" viewBox="0 0 12 12" width="10" height="10" fill="none" stroke="currentColor" '
            'stroke-width="1.8" aria-hidden="true"><path d="m2.5 4.5 3.5 3.5 3.5-3.5"/></svg>')


def _brand() -> str:
    return '<a class="site-brand" href="/"><img src="/vortex-still.webp" alt="" width="28" height="28">OmniTrackr</a>'


def _menu_items(items, active: str, *, with_blurb: bool) -> str:
    links = []
    section = NAV_ALIASES.get(active, active)
    for key, label, href, blurb in items:
        # A page that is one view of an entry marks it as the current section, not the current page.
        current = ' aria-current="page"' if key == active else ' aria-current="true"' if key == section else ""
        detail = f'<span>{escape(blurb)}</span>' if with_blurb else ""
        links.append(f'<a class="site-nav__link" href="{href}"{current}><strong>{escape(label)}</strong>{detail}</a>')
    return "".join(links)


def site_nav(active: str = "", *, login_action: bool = False, member: bool = False) -> str:
    """The sticky site header. `login_action` wires "Log in" to the homepage form script.

    Signed-in members get "My library" in place of the sign-up buttons: the
    server renders it hidden and site.js shows it when the browser holds a session.
    `member` is for pages only signed-in people can reach: it shows "My library" from the start.
    """
    menus = []
    sheet = []
    section = NAV_ALIASES.get(active, active)
    for key, title, items in NAV_MENUS:
        holds_current = any(item[0] == section for item in items)
        current_class = " is-current" if holds_current else ""
        menus.append(
            f'<details class="site-dd{current_class}" data-menu="{key}"><summary>{escape(title)}{_CHEVRON}</summary>'
            f'<div class="site-dd__panel">{_menu_items(items, active, with_blurb=True)}</div></details>'
        )
        sheet.append(f'<div class="site-menu__group"><h2>{escape(title)}</h2>{_menu_items(items, active, with_blurb=False)}</div>')
    login_attr = ' data-action="show-login-form"' if login_action else ""
    signup_attr = ' data-action="show-register-form"' if login_action else ""
    header_class = "site-header is-member" if member else "site-header"
    signup_buttons = "" if member else (
        f'<a class="site-nav__login" href="/#landing-auth"{login_attr}>Log in</a>'
        f'<a class="public-site-nav__cta site-btn site-btn--primary site-btn--sm" href="/#signup"{signup_attr}>Start tracking</a>')
    sheet_signup = "" if member else (
        f'<a class="site-menu__login" href="/#landing-auth"{login_attr}>Log in</a>'
        f'<a class="site-menu__join site-btn site-btn--primary" href="/#signup"{signup_attr}>Start tracking free</a>')
    library_hidden = "" if member else " hidden"
    return (
        f'<header class="{header_class}">'
        '<nav class="site-nav" aria-label="Public site navigation">'
        f'{_brand()}'
        f'<div class="site-nav__menus">{"".join(menus)}</div>'
        '<div class="site-nav__links">'
        f'<a class="site-search" href="/titles" data-site-search aria-label="Search titles">{_SEARCH_ICON}'
        '<span class="site-search__label">Search titles</span><kbd>/</kbd></a>'
        f'{signup_buttons}'
        f'<a class="site-nav__library site-btn site-btn--primary site-btn--sm" href="/"{library_hidden}>My library</a>'
        '<details class="site-menu"><summary aria-label="Open menu"><span></span><span></span><span></span></summary>'
        f'<div class="site-menu__panel">{"".join(sheet)}'
        '<div class="site-menu__account">'
        f'{sheet_signup}'
        f'<a class="site-menu__library site-btn site-btn--primary" href="/"{library_hidden}>Go to my library</a>'
        '</div></div></details>'
        '</div></nav></header>'
    )


def view_switch(group: str, active: str) -> str:
    """The two-way switch at the top of a paired page (see VIEW_SWITCHES)."""
    links = []
    for key, label, href, hint in VIEW_SWITCHES[group]:
        current = ' aria-current="page"' if key == active else ""
        links.append(f'<a class="site-switch__option" href="{href}"{current}>'
                     f'<strong>{escape(label)}</strong><span>{escape(hint)}</span></a>')
    return f'<nav class="site-switch" aria-label="Views">{"".join(links)}</nav>'


# The signed-in dashboard (index.html) shows the same sections: an Explore menu
# in its header on wider screens and a list in the phone "More" sheet.
APP_EXPLORE_MARKER = "<!--APP_EXPLORE-->"
APP_SHEET_EXPLORE_MARKER = "<!--APP_SHEET_EXPLORE-->"


def app_explore_menu() -> str:
    groups = "".join(
        f'<div class="app-explore__group"><p>{escape(title)}</p>'
        + "".join(f'<a href="{href}">{escape(label)}</a>' for _, label, href, _ in items)
        + "</div>"
        for _, title, items in NAV_MENUS
    )
    return ('<details class="app-explore"><summary aria-label="Explore OmniTrackr">'
            '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/>'
            '<path d="m15.5 8.5-2 5-5 2 2-5z"/></svg><span>Explore</span>'
            f'{_CHEVRON}</summary><div class="app-explore__panel">{groups}</div></details>')


def app_sheet_explore() -> str:
    return "".join(
        f'<div class="app-sheet__group"><h4>{escape(title)}</h4><div class="app-sheet__links">'
        + "".join(f'<a href="{href}">{escape(label)}</a>' for _, label, href, _ in items)
        + "</div></div>"
        for _, title, items in NAV_MENUS
    )


def apply_app_chrome(html: str) -> str:
    """Fill the dashboard's Explore menu and phone sheet from NAV_MENUS."""
    return (html.replace(APP_EXPLORE_MARKER, app_explore_menu(), 1)
                .replace(APP_SHEET_EXPLORE_MARKER, app_sheet_explore(), 1))


def site_footer() -> str:
    columns = "".join(
        f'<nav class="site-footer__col" aria-label="{escape(title)}"><h2>{escape(title)}</h2>'
        + "".join(f'<a href="{href}">{escape(label)}</a>' for label, href in links)
        + "</nav>"
        for title, links in FOOTER_GROUPS
    )
    legal = "".join(f'<a href="{href}">{escape(label)}</a>' for label, href in FOOTER_LEGAL)
    return (
        '<footer class="site-footer"><div class="site-wrap site-footer__grid">'
        f'<div class="site-footer__brand">{_brand()}'
        '<p>A free, independent media tracker for everything you watch, play, read, and hear.</p>'
        '<a class="site-footer__cta" href="/#signup">Start your library <span aria-hidden="true">→</span></a>'
        '<a class="site-footer__kofi" href="https://ko-fi.com/omnitrackr" target="_blank" rel="noopener noreferrer">Support on Ko-fi ↗</a>'
        f'</div>{columns}</div>'
        '<div class="site-wrap site-footer__base">'
        f'<p>© {date.today().year} OmniTrackr. An independent project run by one person.</p>'
        f'<nav aria-label="Legal">{legal}</nav>'
        '</div></footer>'
    )


def site_assets(*, sandbox: bool = False) -> str:
    extras = "" if sandbox else f'<script src="/static/site-nav.js?v={SITE_NAV_JS_VERSION}" defer></script>'
    return (f'<link rel="stylesheet" href="/static/site.css?v={SITE_CSS_VERSION}">'
            f'<script src="/static/site.js?v={SITE_JS_VERSION}" defer></script>{extras}'
            f'<script src="/static/visit.js?v={VISIT_JS_VERSION}" defer></script>')


def apply_site_chrome(html: str, *, login_action: bool = False, member: bool = False) -> str:
    """Replace the nav/footer markers; leaves pages without markers untouched."""
    if "<!--SITE_" not in html:
        return html
    nav = NAV_MARKER.search(html)
    key = nav.group(1) if nav else ""
    if key in JOIN_PROMPTS and not member and FOOTER_MARKER in html:
        # Filled in (or dropped) once the page is complete: see fill_join_prompt.
        html = html.replace(FOOTER_MARKER, f"<!--SITE_JOIN:{key}-->" + FOOTER_MARKER, 1)
    html = NAV_MARKER.sub(lambda m: site_nav(m.group(1), login_action=login_action, member=member), html, count=1)
    html = html.replace(FOOTER_MARKER, site_footer(), 1)
    # Match the tag itself: review text quoting the path must not stop the stylesheet loading.
    if 'href="/static/site.css' not in html and "</head>" in html:
        html = html.replace("</head>", site_assets(sandbox=SANDBOX_MARKER in html) + "\n</head>", 1)
    html = html.replace(SANDBOX_MARKER, "")
    return html


def message_page(title: str, heading: str, message: str, *, eyebrow: str = "",
                 actions: tuple[tuple[str, str], ...] = (("Go to the homepage", "/"),),
                 extra_html: str = "") -> str:
    """A small, fully styled page (not found, unavailable...) with the shared header and footer.

    Every argument is escaped except `extra_html`, which callers build from escaped
    parts; `actions` are (label, href) pairs rendered as buttons.
    """
    buttons = "".join(
        f'<a class="site-btn {"site-btn--primary" if index == 0 else "site-btn--ghost"}" href="{escape(href, quote=True)}">{escape(label)}</a>'
        for index, (label, href) in enumerate(actions)
    )
    kicker = f'<p class="site-eyebrow">{escape(eyebrow)}</p>' if eyebrow else ""
    page = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '  <meta charset="UTF-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '  <meta name="robots" content="noindex, follow">\n'
        f'  <title>{escape(title)} - OmniTrackr</title>\n'
        '  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">\n'
        '  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>\n'
        '  <link rel="preload" href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin>\n'
        '  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">\n'
        '</head>\n<body class="site site-message-page">\n  <!--SITE_NAV:-->\n'
        '  <main class="site-message site-wrap">\n'
        '    <div class="site-message__orb" aria-hidden="true"><img src="/vortex-still.webp" alt="" width="160" height="160"></div>\n'
        f'    {kicker}<h1>{escape(heading)}</h1>\n    <p>{escape(message)}</p>\n'
        f'    <div class="site-message__actions">{buttons}</div>\n'
        f'{extra_html}'
        '  </main>\n  <!--SITE_FOOTER-->\n</body>\n</html>'
    )
    return apply_site_chrome(page)


def editorial_picks(heading: str, intro: str, *, limit: int = 6) -> str:
    """Links to the authored Discover guides and trails, for empty directories.

    A directory that has nothing to list yet (no qualifying member reviews or
    collections) should still give a visitor something real to read instead of
    a placeholder. Completed guides come first, then the latest monthly edition
    and the shorter trails. Every value is escaped.
    """
    from .discover_catalog import TRAILS, published_editions
    from .discover_guides import GUIDES

    picks = [(f"/discover/{slug}", TRAILS[slug]["name"], guide["summary"])
             for slug, guide in GUIDES.items() if slug in TRAILS]
    for slug, edition in sorted(published_editions().items(), key=lambda pair: pair[1]["published_date"], reverse=True)[:1]:
        picks.append((f"/discover/monthly/{slug}", edition["name"], edition["intro"]))
    picks.extend((f"/discover/{slug}", trail["name"], trail["intro"])
                 for slug, trail in TRAILS.items() if slug not in GUIDES)
    cards = "".join(
        f'<li><a href="{escape(href, quote=True)}"><strong>{escape(name)}</strong>'
        f'<span>{escape(blurb)}</span></a></li>'
        for href, name, blurb in picks[:limit]
    )
    return (
        '<section class="site-picks" aria-labelledby="site-picks-heading">'
        f'<h2 id="site-picks-heading">{escape(heading)}</h2><p>{escape(intro)}</p>'
        f'<ul class="site-picks__list">{cards}</ul>'
        '<p class="site-picks__more"><a href="/discover">See every Discover trail →</a></p>'
        '</section>'
    )
