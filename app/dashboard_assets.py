"""Dashboard script bundle.

The signed-in dashboard script lives in app/static/dashboard/ as a few modules
(core, library, account, social, home, custom-tabs) plus lazy chunks under
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

DASHBOARD_DIR = Path(__file__).resolve().parent / "static" / "dashboard"
LAZY_BASE_URL = "/static/dashboard/lazy/"

EAGER_MODULES = (
    "core.js",
    "library.js",
    "account.js",
    "social.js",
    "home.js",
    "custom-tabs.js",
)

# Chunk name -> lazy files, loaded together and executed in this order.
LAZY_CHUNKS = {
    "quick-capture": ("quick-capture.js",),
    "metadata-search": (
        "metadata-movie.js",
        "metadata-tv-anime-games.js",
        "metadata-music.js",
        "metadata-books.js",
    ),
    "postcards": ("postcards.js",),
    "export-import": ("export-import.js",),
    "insights": ("statistics.js", "tasteprint.js"),
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
