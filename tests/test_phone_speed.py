"""Signed-in dashboard start-up on phones: one round of home-card requests, the
visit-day ping, the placeholder shapes, the connection bar and the service worker."""
import re
from pathlib import Path

from app import dashboard_assets

STATIC = Path("app/static")
INDEX = Path("app/templates/index.html")


def _eager_source():
    return "".join(dashboard_assets._read(name) for name in dashboard_assets.EAGER_MODULES)


def test_auth_helpers_are_hoisted_so_startup_code_can_call_them():
    """home.js runs its visit-day ping while the bundle is still being evaluated.

    A `const hasStoredAuth` in a later module threw there (temporal dead zone),
    so the dashboard never recorded a visit day and active members looked away.
    """
    source = _eager_source()
    for name in ("getAuthTokenValue", "hasStoredAuth", "authFetchOptions"):
        assert not re.search(rf"^(?:const|let|var)\s+{name}\b", source, re.MULTILINE), name
        declared = source.index(f"function {name}(")
        assert declared < source.index("const initialReturnDeckRequest = bootstrapReturnDeck();"), name


def test_first_library_page_does_not_refresh_every_home_card_again():
    home = dashboard_assets._read("home.js")
    wrapper = home[home.index("const loadMovieLibrary = loadMovies;"):home.index("const loadTVShowLibrary")]
    assert "if (initialMovieLibraryLoad) initialMovieLibraryLoad = false;" in wrapper
    bootstrap = home[home.index("async function bootstrapReturnDeck()"):home.index("function resolveReturnDeck")]
    assert "scheduleLibraryLaunchpadRefresh" not in bootstrap
    assert "loadDashboardDecisionCards()" in bootstrap


def test_connection_bar_ships_in_the_bundle_and_is_styled():
    assert "connection.js" in dashboard_assets.EAGER_MODULES
    script, _ = dashboard_assets.bundle()
    assert "window.addEventListener('offline', goneOffline)" in script
    css = (STATIC / "dashboard-2026.css").read_text(encoding="utf-8")
    assert ".connection-bar[hidden] { display: none; }" in css


def test_placeholder_shapes_only_show_while_a_signed_in_dashboard_settles():
    html = INDEX.read_text(encoding="utf-8")
    assert ".dashboard-skeleton{display:none}" in html
    assert "html.authenticated.dashboard-settling .dashboard-skeleton{opacity:1}" in html
    assert 'class="dashboard-skeleton-anchor" aria-hidden="true"' in html
    # Above the first card, so cards appearing never move the shapes.
    assert html.index("dashboard-skeleton-anchor\" aria-hidden") < html.index('<section id="friendRecs"')


def test_public_homepage_has_no_placeholder_shapes(client):
    assert "dashboard-skeleton-anchor" not in client.get("/").text


def test_phone_header_rules_apply_from_the_first_paint():
    css = (STATIC / "app-nav.css").read_text(encoding="utf-8")
    early = ":is(body.has-app-dock, html.authenticated body.app-shell:not(.app-dock-off))"
    assert f"{early} .header .quick-capture-trigger" in css
    assert f"{early} .tabs .library-nav__group--tools" in css
    assert "classList.toggle('app-dock-off', !shown)" in (STATIC / "app-nav.js").read_text(encoding="utf-8")


def test_worker_keeps_push_and_its_static_cache_name():
    source = (STATIC / "sw.js").read_text(encoding="utf-8")
    # Renaming the cache would make every member download every file again.
    assert "const STATIC_CACHE = 'omnitrackr-static-20261010-push-1';" in source
    assert "navigationPreload.enable()" in source and "event.preloadResponse" in source
    assert "self.addEventListener('push'" in source and "self.addEventListener('notificationclick'" in source
    assert "url.pathname.startsWith('/static/fonts/')" in source
    assert "VERSIONED_ROOT_FILES = new Set(['/app.js', '/auth.js'])" in source


def test_worker_route_still_serves_and_revalidates(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
