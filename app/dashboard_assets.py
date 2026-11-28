"""Dashboard script bundle.

The signed-in dashboard script lives in app/static/dashboard/ as a few modules
(notices, a11y, core, library, account, social, home, custom-tabs, connection) plus lazy chunks under
dashboard/lazy/. Rarely used features (statistics, friend profiles, collections,
the custom tab manager and so on) are left out of the first download and
fetched when first used, or quietly once the page is idle.

The eager modules are served as one script so the page still makes a single
request for them, and so top-level code keeps seeing every function declared
anywhere in the bundle, exactly as it did when this was one app.js file. Each
lazy segment's place in its module is kept as a `// @lazy-chunk lazy/<file>`
line, which also lets tests rebuild the full source in its original order.

The bundle and chunk URLs carry a content hash, so browsers can cache them
for a year and still pick up every deploy.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from . import minify

DASHBOARD_DIR = Path(__file__).resolve().parent / "static" / "dashboard"
LAZY_BASE_URL = "/static/dashboard/lazy/"

EAGER_MODULES = (
    "notices.js",
    "a11y.js",
    "core.js",
    "library.js",
    "account.js",
    "social.js",
    "home.js",
    "custom-tabs.js",
    "connection.js",
)

# Chunk name -> lazy files, loaded together and executed in this order.
LAZY_CHUNKS = {
    "quick-capture": ("quick-capture.js",),
    "metadata-search": (
        "metadata-movie.js",
        "metadata-tv-anime-games.js",
        "metadata-music.js",
        "metadata-books.js",
        "metadata-manga.js",
        "metadata-podcasts.js",
        "metadata-audiobooks.js",
    ),
    "postcards": ("postcards.js",),
    "export-import": ("export-import.js",),
    "insights": ("statistics.js", "tasteprint.js", "time-spent.js"),
    "completion": ("completion.js",),
    "friend-profile": ("friend-profile.js",),
    "activity-journal": ("activity-journal.js",),
    "collections": ("collections.js", "collection-studio.js"),
    "custom-tab-manager": ("custom-tab-manager.js", "custom-tab-editor.js"),
}

LAZY_MARKER = re.compile(r"^// @lazy-chunk lazy/([\w.-]+)\n", re.MULTILINE)
_TOP_LEVEL_FUNCTION = re.compile(
    r"^(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*\(|^window\.([A-Za-z_$][\w$]*)\s*=",
    re.MULTILINE,
)


def _read(relative: str) -> str:
    return (DASHBOARD_DIR / relative).read_text(encoding="utf-8")


def lazy_exports(files: tuple[str, ...]) -> list[str]:
    """Global functions a chunk defines; each gets a placeholder that loads it."""
    names: list[str] = []
    for name in files:
        for match in _TOP_LEVEL_FUNCTION.finditer(_read(f"lazy/{name}")):
            found = match.group(1) or match.group(2)
            if found not in names:
                names.append(found)
    return names


def full_source() -> str:
    """The dashboard source in its original single-file order (used by tests)."""
    modules = "".join(_read(name) for name in EAGER_MODULES)
    return LAZY_MARKER.sub(lambda match: _read(f"lazy/{match.group(1)}"), modules)


@lru_cache(maxsize=1)
def bundle() -> tuple[str, str]:
    """Return (javascript, version) for the eager dashboard bundle."""
    lazy_files = [name for files in LAZY_CHUNKS.values() for name in files]
    digest = hashlib.sha256()
    for relative in ("lazy-loader.js", *EAGER_MODULES, *(f"lazy/{name}" for name in lazy_files)):
        digest.update(relative.encode("utf-8") + b"\0" + _read(relative).encode("utf-8") + b"\0")
    # Served minified (app/minify.py): switching that off, or changing the minifier, changes the URL.
    digest.update(minify.version_tag().encode("utf-8"))
    version = digest.hexdigest()[:16]
    config = {
        "version": version,
        "base": LAZY_BASE_URL,
        "chunks": {
            chunk: {"files": list(files), "exports": lazy_exports(files)}
            for chunk, files in LAZY_CHUNKS.items()
        },
    }
    parts = [
        f"window.OmniDashboardChunks = {json.dumps(config, separators=(',', ':'))};\n",
        _read("lazy-loader.js"),
        *(_read(name) for name in EAGER_MODULES),
    ]
    return "".join(parts), version


# ---------------------------------------------------------------- stylesheets
#
# The signed-in dashboard links 37 stylesheets in app/templates/index.html. Every
# one of them blocks the first paint, so a phone on a cold cache waited for 37
# round trips (about 170 KB, each file gzipped on its own) before drawing anything.
# Signed-in pages get one bundled stylesheet instead: the same files, joined in the
# template's order so the cascade is unchanged (about 100 KB gzipped as one file).
# The template stays the list of record: adding or reordering a <link> there is all
# it takes, and guests never see the bundle.

TEMPLATE = Path(__file__).resolve().parent / "templates" / "index.html"
STATIC_DIR = Path(__file__).resolve().parent / "static"
STYLESHEET_BUNDLE_PATH = "/dashboard.css"
_STYLESHEET_LINK = re.compile(r'^[ \t]*<link rel="stylesheet" href="([^"]+)">[ \t]*\n', re.MULTILINE)
_CSS_URL = re.compile(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""")


def _served_path(href: str) -> str:
    """The URL path a template href is served at ("./styles.css?v=1" -> "/styles.css")."""
    path = href.split("?", 1)[0].split("#", 1)[0]
    return "/" + path[2:] if path.startswith("./") else path


def _stylesheet_file(href: str) -> Path:
    path = _served_path(href)
    if path == "/styles.css":
        return STATIC_DIR / "styles.css"
    if path.startswith("/static/"):
        candidate = (STATIC_DIR / path[len("/static/"):]).resolve()
        if candidate.is_file() and STATIC_DIR in candidate.parents:
            return candidate
    raise ValueError(f"Not a dashboard stylesheet: {href}")


def _absolute_urls(css: str, served_at: str) -> str:
    """Relative url()s resolved against the file's own address, so they still work from the bundle."""
    from urllib.parse import urljoin

    def absolute(match: re.Match) -> str:
        quote, ref = match.group(1), match.group(2).strip()
        if ref.startswith(("/", "data:", "http:", "https:", "#")):
            return match.group(0)
        return f"url({quote}{urljoin(served_at, ref)}{quote})"

    return _CSS_URL.sub(absolute, css)


def stylesheet_links(html: str) -> list[re.Match]:
    """The template's run of stylesheet links: consecutive lines, in order."""
    found: list[re.Match] = []
    for match in _STYLESHEET_LINK.finditer(html):
        if found and match.start() != found[-1].end():
            break  # Only the first unbroken run; anything after it stays as written.
        found.append(match)
    return found


@lru_cache(maxsize=1)
def stylesheet_bundle() -> tuple[str, str, tuple[str, ...]]:
    """Return (css, version, hrefs) for the dashboard's stylesheets as one file."""
    hrefs = tuple(match.group(1) for match in stylesheet_links(TEMPLATE.read_text(encoding="utf-8")))
    parts = []
    for href in hrefs:
        css = _stylesheet_file(href).read_text(encoding="utf-8")
        parts.append(f"/* {_served_path(href)} */\n{_absolute_urls(css, _served_path(href))}\n")
    css = "".join(parts)
    version = hashlib.sha256((css + minify.version_tag()).encode("utf-8")).hexdigest()[:16]  # See bundle().
    return css, version, hrefs


def bundle_stylesheets(html: str) -> str:
    """The dashboard page with its stylesheet links swapped for the one bundled link.

    Leaves the page as it is if its links are not the ones the bundle was built from,
    so a template edit can never drop a stylesheet.
    """
    links = stylesheet_links(html)
    try:
        _, version, hrefs = stylesheet_bundle()
    except (OSError, ValueError):
        return html
    if not links or tuple(match.group(1) for match in links) != hrefs:
        return html
    indent = re.match(r"[ \t]*", links[0].group(0)).group(0)
    bundled = f'{indent}<link rel="stylesheet" href="{STYLESHEET_BUNDLE_PATH}?v={version}">\n'
    html = html[:links[0].start()] + bundled + html[links[-1].end():]
    # The preload hint for styles.css would now fetch a file the page no longer uses.
    styles = next((href for href in hrefs if _served_path(href) == "/styles.css"), None)
    if styles:
        html = re.sub(rf'^[ \t]*<link rel="preload" href="{re.escape(styles)}" as="style">[ \t]*\n', "", html,
                      count=1, flags=re.MULTILINE)
    return html


def page_stylesheets(html: str) -> list[str]:
    """The template stylesheets a served page loads, looking inside the bundle (used by tests)."""
    hrefs = re.findall(r'<link rel="stylesheet" href="([^"]+)">', html)
    _, version, bundled = stylesheet_bundle()
    expanded: list[str] = []
    for href in hrefs:
        expanded.extend(bundled if href == f"{STYLESHEET_BUNDLE_PATH}?v={version}" else [href])
    return expanded
