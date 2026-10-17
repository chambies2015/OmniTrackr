"""The signed-in dashboard script: eager modules served as one bundle, plus lazy chunks."""
import re

from app import dashboard_assets
from app.auth import AUTH_COOKIE_NAME

STATIC = dashboard_assets.DASHBOARD_DIR.parent
PAGE_SCRIPTS = ("auth.js", "import-studio.js", "progress.js", "for-you.js", "title-links.js",
                "public-profile.js", "supporter.js", "year-in-review-entry.js", "guest-list.js")
LEXICAL = re.compile(r"^(?:let|const|var|class)\s+([A-Za-z_$][\w$]*)", re.MULTILINE)


def _lazy_files():
    return [name for files in dashboard_assets.LAZY_CHUNKS.values() for name in files]


def _eager_source():
    return "".join(dashboard_assets._read(name) for name in dashboard_assets.EAGER_MODULES)


def test_every_lazy_file_keeps_exactly_one_place_in_the_source():
    markers = dashboard_assets.LAZY_MARKER.findall(_eager_source())
    assert sorted(markers) == sorted(_lazy_files())
    assert len(set(markers)) == len(markers)
    source = dashboard_assets.full_source()
    assert "// @lazy-chunk" not in source
    for name in _lazy_files():
        assert source.count(dashboard_assets._read(f"lazy/{name}")) == 1, name


def test_lazy_chunks_keep_their_variables_to_themselves():
    """Code that runs before a chunk loads can only reach it through its functions."""
    outside = _eager_source() + "".join((STATIC / name).read_text(encoding="utf-8") for name in PAGE_SCRIPTS)
    for chunk, files in dashboard_assets.LAZY_CHUNKS.items():
        others = outside + "".join(
            dashboard_assets._read(f"lazy/{name}")
            for other, other_files in dashboard_assets.LAZY_CHUNKS.items() if other != chunk
            for name in other_files
        )
        for name in files:
            for variable in LEXICAL.findall(dashboard_assets._read(f"lazy/{name}")):
                assert not re.search(rf"(?<![\w.$]){re.escape(variable)}\b", others), (chunk, variable)


def test_lazy_functions_are_not_also_defined_in_the_bundle():
    eager = _eager_source()
    for files in dashboard_assets.LAZY_CHUNKS.values():
        for name in dashboard_assets.lazy_exports(files):
            assert not re.search(rf"^(?:async\s+)?function\s+{re.escape(name)}\s*\(|^(?:let|const|var)\s+{re.escape(name)}\b|^window\.{re.escape(name)}\s*=",
                                 eager, re.MULTILINE), name


def test_bundle_lists_every_chunk_before_the_modules_run():
    script, version = dashboard_assets.bundle()
    assert script.startswith(f'window.OmniDashboardChunks = {{"version":"{version}"')
    assert script.index("function placeholder(") < script.index("function libraryPageConfig(")
    assert '"exports":["exportData","importData"]' in script
    for name in _lazy_files():
        assert f'"{name}"' in script


def test_signed_in_page_loads_the_versioned_bundle(client):
    _, version = dashboard_assets.bundle()
    client.cookies.set(AUTH_COOKIE_NAME, "signed-in")
    page = client.get("/").text
    assert f'<script src="./app.js?v={version}"></script>' in page
    trigger = page[page.index('id="showFriendsSidebar"'):page.index("</button>", page.index('id="showFriendsSidebar"'))]
    assert " hidden>" not in trigger


def test_public_homepage_does_not_load_the_dashboard(client):
    page = client.get("/").text
    assert "app.js" not in page
    assert "dashboard/lazy" not in page


def test_bundle_is_cached_for_a_year_only_under_its_own_hash(client):
    script, version = dashboard_assets.bundle()
    current = client.get(f"/app.js?v={version}")
    assert current.status_code == 200
    assert current.headers["content-type"].startswith("application/javascript")
    assert current.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert current.text == script
    for stale in ("/app.js", "/app.js?v=20261005-finish-review-1"):
        response = client.get(stale)
        assert response.status_code == 200 and response.text == script
        assert response.headers["cache-control"] == "public, max-age=86400"


def test_lazy_chunks_are_served_as_versioned_static_files(client):
    _, version = dashboard_assets.bundle()
    for name in _lazy_files():
        response = client.get(f"/static/dashboard/lazy/{name}?v={version}")
        assert response.status_code == 200, name
        assert "immutable" in response.headers["cache-control"]
