"""Shared reading layout for the long-form public pages (guides, help, policies).

Every page listed in PAGES is a hand-written template with a header and a run of
sections. When one is served, ``enhance`` adds the parts every such page should
have, so the templates don't each repeat them:

* breadcrumbs (Home > Guides > Movie tracker) and matching BreadcrumbList data,
* a reading-time and "Updated" line under the header, drawn server-side so the
  header doesn't grow after the page is shown,
* ids for any h2 without one, and an "On this page" box on long pages that
  don't have one (the changelog gets a list of months instead),
* a "Keep reading" block: three related pages as cards, under the page's own
  related paragraph when it has one,
* a light/dark switch (the stored choice is applied in <head>, before paint),
* the page's own stylesheets inlined, so the first visit doesn't wait on them.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from html import escape, unescape

SITE_URL = "https://omnitrackr.xyz"
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
THEME_KEY = "omnitrackr_reader_theme"


@dataclass(frozen=True)
class ReaderPage:
    path: str
    name: str
    section: str  # "guides" or "about"; "tools" for OTHER_PAGES
    blurb: str
    related: tuple  # template names, OTHER_PAGES keys, or ReaderPage objects
    parent: tuple[str, str] | None = None  # (label, path) between the section and this page


SECTIONS = {"guides": ("Guides", "/guides"), "about": ("About", "/about")}

PAGES = {
    "guides.html": ReaderPage("/guides", "Guides", "guides",
        "Step-by-step help for starting a library, importing a list, saving your place and sharing.",
        ("media_tracking.html", "export_import_guide.html", "media_tracker_checklist.html")),
    "media_tracking.html": ReaderPage("/media-tracking", "Media tracking hub", "guides",
        "Every tracking guide in one place, grouped by what you track.",
        ("guides.html", "use_cases.html", "compare.html")),
    "movie_tracker.html": ReaderPage("/movie-tracker", "Movie tracker", "guides",
        "Watchlists, ratings and reviews for films, kept outside any streaming app.",
        ("tv_show_tracker.html", "review_guidelines.html", "reviews")),
    "tv_show_tracker.html": ReaderPage("/tv-show-tracker", "TV show tracker", "guides",
        "Seasons, episodes and the place you stopped, for every show you follow.",
        ("anime_tracker.html", "binge_calculator", "media_statistics.html")),
    "anime_tracker.html": ReaderPage("/anime-tracker", "Anime tracker", "guides",
        "Seasonal shows, long runs and stalled series, with episode progress.",
        ("manga_tracker.html", "tv_show_tracker.html", "binge_calculator")),
    "game_tracker.html": ReaderPage("/game-tracker", "Game tracker", "guides",
        "A backlog you can work through, with genres and played status.",
        ("media_statistics.html", "use_cases.html", "compare.html")),
    "book_tracker.html": ReaderPage("/book-tracker", "Book tracker", "guides",
        "Reading lists, authors and the page you stopped on.",
        ("manga_tracker.html", "export_import_guide.html", "review_guidelines.html")),
    "music_tracker.html": ReaderPage("/music-tracker", "Music tracker", "guides",
        "Albums and artists next to everything else you love.",
        ("podcast_tracker.html", "review_guidelines.html", "media_statistics.html")),
    "manga_tracker.html": ReaderPage("/manga-tracker", "Manga tracker", "guides",
        "Volumes, chapters and imports from MyAnimeList or AniList.",
        ("anime_tracker.html", "book_tracker.html", "switch.html")),
    "podcast_tracker.html": ReaderPage("/podcast-tracker", "Podcast tracker", "guides",
        "Shows you follow, the episode you stopped on, and limited series you finished.",
        ("music_tracker.html", "audiobook_tracker.html", "export_import_guide.html")),
    "audiobook_tracker.html": ReaderPage("/audiobook-tracker", "Audiobook tracker", "guides",
        "Narrators, runtimes, the chapter you reached, and your listening hours.",
        ("book_tracker.html", "podcast_tracker.html", "export_import_guide.html")),
    "use_cases.html": ReaderPage("/use-cases", "Use cases", "guides",
        "How people use one library for watchlists, backlogs, reviews and sharing.",
        ("media_tracker_checklist.html", "compare.html", "faq.html")),
    "compare.html": ReaderPage("/compare", "Tracker comparison", "guides",
        "OmniTrackr next to spreadsheets, IMDb, Letterboxd, Trakt and Goodreads.",
        ("switch.html", "export_import_guide.html", "demo")),
    "export_import_guide.html": ReaderPage("/export-import-guide", "Import and backup guide", "guides",
        "Bring a CSV in, check the conversion, and keep a JSON backup.",
        ("switch.html", "tracking_templates.html", "privacy.html")),
    "switch.html": ReaderPage("/switch", "Switching guide", "guides",
        "Where each service keeps its export, and what to check after importing.",
        ("export_import_guide.html", "compare.html", "demo")),
    "media_tracker_checklist.html": ReaderPage("/media-tracker-checklist", "Setup checklist", "guides",
        "A short plan for categories, ratings and privacy before your first week.",
        ("tracking_templates.html", "guides.html", "review_guidelines.html")),
    "tracking_templates.html": ReaderPage("/tracking-templates", "Tracking templates", "guides",
        "Rating scales, review prompts and backlog cleanup you can copy.",
        ("media_tracker_checklist.html", "export_import_guide.html", "review_guidelines.html")),
    "media_statistics.html": ReaderPage("/media-statistics", "Media statistics", "guides",
        "What completion, rating coverage and time spent say about your habits.",
        ("binge_calculator", "tracking_templates.html", "review_guidelines.html")),
    "review_guidelines.html": ReaderPage("/review-guidelines", "Review guidelines", "guides",
        "Prompts and examples for reviews other people will want to read.",
        ("content_quality.html", "media_statistics.html", "privacy.html")),
    "faq.html": ReaderPage("/faq", "FAQ", "guides",
        "Short answers about tracking, privacy, exports and ads.",
        ("guides.html", "privacy.html", "contact.html")),
    "about.html": ReaderPage("/about", "About", "about",
        "Who runs OmniTrackr, how the guides are checked and how the site is paid for.",
        ("content_quality.html", "advertising.html", "roadmap.html")),
    "content_quality.html": ReaderPage("/content-quality", "Editorial standards", "about",
        "How guides are written, fact-checked and corrected.",
        ("about.html", "advertising.html", "sample_library")),
    "advertising.html": ReaderPage("/advertising", "Ads and affiliates", "about",
        "Where ads can appear, where they never do, and how affiliate links are labelled.",
        ("privacy.html", "about.html", "content_quality.html")),
    "roadmap.html": ReaderPage("/roadmap", "Roadmap", "about",
        "What shipped recently and what is being considered next.",
        ("changelog.html", "about.html", "contact.html")),
    "changelog.html": ReaderPage("/changelog", "What's new", "about",
        "Every release, newest first.",
        ("roadmap.html", "guides.html", "about.html")),
    "contact.html": ReaderPage("/contact", "Contact", "about",
        "Support, bug reports and feature ideas.",
        ("faq.html", "about.html", "privacy.html")),
    "site_map.html": ReaderPage("/site-map", "Site map", "about",
        "Every public page, grouped by section.",
        ("guides.html", "media_tracking.html", "about.html")),
    "privacy.html": ReaderPage("/privacy", "Privacy policy", "about",
        "What is collected, why, and the controls you have.",
        ("terms.html", "advertising.html", "contact.html")),
    "terms.html": ReaderPage("/terms", "Terms", "about",
        "The rules for using OmniTrackr and posting public reviews.",
        ("privacy.html", "review_guidelines.html", "contact.html")),
}

# Pages outside the reader layout that related blocks can still point to.
OTHER_PAGES = {
    "demo": ReaderPage("/demo", "Try the demo", "tools",
        "A sample library to click through, no account needed.", ()),
    "sample_library": ReaderPage("/sample-library", "Sample library", "tools",
        "What a tracked library looks like, filled with made-up entries.", ()),
    "reviews": ReaderPage("/reviews", "Member reviews", "tools",
        "Reviews members chose to share, across every kind of media.", ()),
    "binge_calculator": ReaderPage("/binge-calculator", "Binge calculator", "tools",
        "How long a show, anime or book series takes, and the day you'd finish.", ()),
}
KINDS = {"guides": "Guide", "about": "About OmniTrackr", "tools": "Try it"}

# Pages shorter than this get no reading time; pages with fewer sections, no contents box.
MIN_WORDS_FOR_TIME = 300
MIN_SECTIONS_FOR_CONTENTS = 4
WORDS_PER_MINUTE = 230

INLINE_STYLES = ("fonts.css", "public-reader.css", "site.css")
_STYLE_LINK = re.compile(
    r'<link rel="stylesheet" href="/static/(' + "|".join(re.escape(n) for n in INLINE_STYLES) + r')(?:\?v=[\w.-]+)?">'
)
_style_cache: dict[str, tuple[float, str]] = {}

_BACK_LINK = re.compile(r'[ \t]*<a href="[^"]*" class="back-link">[^<]*</a>\n?')
_HEADER_END = re.compile(r'(<(header|div) class="(?:privacy|public|content)-header">.*?</\2>)', re.S)
_MAIN = re.compile(r'(<main id="reader-main"[^>]*>)(.*)(</main>)', re.S)
_H2 = re.compile(r"<h2(?P<attrs>[^>]*)>(?P<text>.*?)</h2>", re.S)
_RELATED = re.compile(r'\n?[ \t]*<section [^>]*aria-labelledby="related-heading"[^>]*>.*?</section>', re.S)
_LD_DATE = re.compile(r'"dateModified":\s*"(\d{4}-\d{2}-\d{2})"')
_CHANGELOG_DATE = re.compile(r"^([A-Z][a-z]+) (?:\d{1,2}, )?(\d{4}):")
_OPEN_TAG = re.compile(r"<[a-z][^>]*>")
# Headings inside these cards are card titles, not sections, so they stay out of the contents box.
_CARD = re.compile(r'class="[^"]*\b(?:faq-topic|guide-path|guide-card|hub-card|directory-card|policy-card|roadmap-card)\b')


def _text(fragment: str) -> str:
    fragment = re.sub(r"<(script|style)\b.*?</\1>", " ", fragment, flags=re.S)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _slug(text: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60].strip("-") or "section"
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    taken.add(slug)
    return slug


def _stylesheet(name: str) -> str:
    path = os.path.join(STATIC_DIR, name)
    mtime = os.path.getmtime(path)
    cached = _style_cache.get(name)
    if cached and cached[0] == mtime:
        return cached[1]
    with open(path, encoding="utf-8") as handle:
        css = handle.read()
    _style_cache[name] = (mtime, css)
    return css


def inline_styles(html: str) -> str:
    """Swap the reader stylesheets for <style> blocks (the CSP layer adds the nonce)."""
    return _STYLE_LINK.sub(lambda m: f'<style data-from="{m.group(1)}">\n{_stylesheet(m.group(1))}</style>', html)


def _crumbs(page: ReaderPage) -> list[tuple[str, str]]:
    trail = [("Home", "/")]
    label, href = SECTIONS[page.section]
    if href != page.path:
        trail.append((label, href))
    if page.parent:
        trail.append(page.parent)
    trail.append((page.name, page.path))
    return trail


def _crumb_nav(page: ReaderPage) -> str:
    trail = _crumbs(page)
    items = "".join(f'<li><a href="{href}">{escape(label)}</a></li>' for label, href in trail[:-1])
    items += f'<li><span aria-current="page">{escape(trail[-1][0])}</span></li>'
    toggle = ('<button type="button" class="reader-theme" data-reader-theme>'
              '<span class="reader-theme__icon" aria-hidden="true"></span>'
              '<span class="reader-theme__label">Theme</span></button>')
    return (f'<div class="reader-bar"><nav class="reader-crumbs" aria-label="Breadcrumb"><ol>{items}</ol></nav>'
            f'{toggle}</div>\n')


def _crumb_data(page: ReaderPage) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": label, "item": f"{SITE_URL}{href}"}
            for i, (label, href) in enumerate(_crumbs(page), start=1)
        ],
    }
    return f'  <script type="application/ld+json">{json.dumps(data)}</script>\n'


# The light/dark switch. It runs in <head>, so a stored choice is applied before the body is
# drawn and never flashes the other theme. Without a stored choice the page follows the
# device setting. Kept out of site.js, which the sandboxed demo also loads and which must
# not touch browser storage there.
THEME_SCRIPT = """(function () {
  var root = document.documentElement, key = '%s', light = window.matchMedia('(prefers-color-scheme: light)');
  try { var saved = localStorage.getItem(key); if (saved === 'light' || saved === 'dark') root.setAttribute('data-theme', saved); } catch (e) {}
  function current() { return root.getAttribute('data-theme') || (light.matches ? 'light' : 'dark'); }
  document.addEventListener('DOMContentLoaded', function () {
    var button = document.querySelector('[data-reader-theme]');
    if (!button) return;
    var label = button.querySelector('.reader-theme__label');
    function render() {
      var next = current() === 'light' ? 'dark' : 'light';
      button.setAttribute('data-next', next);
      label.textContent = next === 'light' ? 'Light' : 'Dark';
      button.setAttribute('aria-label', 'Switch to the ' + next + ' theme');
    }
    button.addEventListener('click', function () {
      var next = button.getAttribute('data-next');
      root.setAttribute('data-theme', next);
      try { localStorage.setItem(key, next); } catch (e) {}
      render();
    });
    if (light.addEventListener) light.addEventListener('change', render);
    render();
  });
})();""" % THEME_KEY


def _theme_boot() -> str:
    return f"  <script>{THEME_SCRIPT}</script>\n"


def _meta_line(body: str, header: str, updated: date | None, byline: bool) -> str:
    parts = ["By OmniTrackr"] if byline else []
    words = len(_text(body).split())
    if words >= MIN_WORDS_FOR_TIME:
        parts.append(f"{max(1, round(words / WORDS_PER_MINUTE))} min read")
    if updated and "Last Updated" not in header:
        parts.append(f'Updated <time datetime="{updated.isoformat()}">'
                     f'{updated.strftime("%B")} {updated.day}, {updated.year}</time>')
    if not parts:
        return ""
    return '<p class="reader-meta">' + " · ".join(parts) + "</p>"


def _contents(sections: list[tuple[str, str]], changelog: bool) -> str:
    if changelog:
        months: dict[str, str] = {}
        for anchor, text in sections:
            found = _CHANGELOG_DATE.match(text)
            if found:
                months.setdefault(f"{found.group(1)} {found.group(2)}", anchor)
        if len(months) < 2:
            return ""
        links = "".join(f'<a href="#{anchor}">{escape(label)}</a>' for label, anchor in months.items())
        return ('\n<details class="reader-contents reader-contents--months"><summary>Jump to a month</summary>'
                f'<nav aria-label="Months">{links}</nav></details>\n')
    if len(sections) < MIN_SECTIONS_FOR_CONTENTS:
        return ""
    links = "".join(f'<a href="#{anchor}">{escape(text)}</a>' for anchor, text in sections)
    return ('\n<details class="reader-contents"><summary>On this page</summary>'
            f'<nav aria-label="On this page">{links}</nav></details>\n')


def _related(page: ReaderPage, lead: str) -> str:
    cards = []
    for name in page.related:
        other = name if isinstance(name, ReaderPage) else PAGES.get(name) or OTHER_PAGES[name]
        kind = KINDS[other.section]
        cards.append(f'<a class="reader-related__card" href="{other.path}"><span class="reader-related__kind">{kind}</span>'
                     f'<strong>{escape(other.name)}</strong><span>{escape(other.blurb)}</span></a>')
    return ('\n      <section class="reader-related" aria-labelledby="related-heading">\n'
            '        <h2 id="related-heading">Keep reading</h2>\n'
            f'{lead}'
            f'        <div class="reader-related__grid">{"".join(cards)}</div>\n'
            '      </section>\n    ')


def enhance(html: str, template_name: str, page: ReaderPage | None = None) -> str:
    """Add the shared layout. ``page`` describes a page drawn from a shared template."""
    page = page or PAGES.get(template_name)
    if page is None:
        return html
    found = _MAIN.search(html)
    if not found:
        return html
    opening, body, closing = found.groups()

    # A page's own related paragraph stays as the lead-in to the cards: it often links
    # pages the cards don't.
    lead = ""
    related = _RELATED.search(body)
    if related:
        inner = related.group(0)
        inner = inner[inner.index("</h2>") + len("</h2>"):inner.rindex("</section>")].strip()
        lead = f'        <div class="reader-related__lead">{inner}</div>\n' if inner else ""
        body = body[:related.start()] + body[related.end():]
    body = body.rstrip() + _related(page, lead)

    taken = set(re.findall(r'\bid="([^"]+)"', html))
    sections: list[tuple[str, str]] = []

    def add_id(match: re.Match) -> str:
        attrs, inner = match.group("attrs"), match.group("text")
        text = _text(inner)
        existing = re.search(r'\bid="([^"]+)"', attrs)
        anchor = existing.group(1) if existing else _slug(text, taken)
        opened = _OPEN_TAG.findall(match.string[max(0, match.start() - 300):match.start()])
        in_card = bool(opened) and bool(_CARD.search(opened[-1]))
        if anchor != "related-heading" and not in_card:
            sections.append((anchor, text))
        if existing:
            return match.group(0)
        return f'<h2 id="{anchor}"{attrs}>{inner}</h2>'

    body = _H2.sub(add_id, body)
    # Hand-written contents boxes keep their own wording, but the related block is now "Keep reading".
    body = body.replace('<a href="#related-heading">Related pages</a>', '<a href="#related-heading">Keep reading</a>')

    updated_match = _LD_DATE.search(html)
    updated = date.fromisoformat(updated_match.group(1)) if updated_match else None
    if template_name == "changelog.html":
        # New entries are added far more often than the page's metadata is touched.
        dates = []
        for _, text in sections:
            try:
                dates.append(datetime.strptime(text.split(":", 1)[0], "%B %d, %Y").date())
            except ValueError:
                continue
        if dates:
            updated = max(dates)
    header_match = _HEADER_END.search(body)
    if header_match:
        header = header_match.group(1)
        meta = _meta_line(body[header_match.end():], header, updated, byline=page.section == "guides")
        inner_close = header.rfind("</")
        new_header = header[:inner_close].rstrip() + (f"\n        {meta}\n      " if meta else "\n      ") + header[inner_close:]
        has_contents = "reader-contents" in body or "reader-jump" in body or "guide-jump" in body
        contents = "" if has_contents else _contents(sections, template_name == "changelog.html")
        body = body[:header_match.start()] + new_header + contents + body[header_match.end():]

    if _BACK_LINK.search(body):
        body = _BACK_LINK.sub(lambda _: "      " + _crumb_nav(page), body, count=1)
    else:
        body = "\n      " + _crumb_nav(page) + body

    html = html[:found.start()] + opening + body + closing + html[found.end():]
    head_extra = _theme_boot()
    if '"BreadcrumbList"' not in html:
        head_extra += _crumb_data(page)
    html = html.replace("</head>", head_extra + "</head>", 1)
    # Marks the pages whose styles know both themes; other reader-layout pages stay dark.
    html = html.replace('<html lang="en">', '<html lang="en" data-reader>', 1)
    return inline_styles(html)
