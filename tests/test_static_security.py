import re
from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "app.js"
MAIN_PY = Path(__file__).resolve().parents[1] / "app" / "main.py"
INDEX_HTML = Path(__file__).resolve().parents[1] / "app" / "templates" / "index.html"
AD_LOADER_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "ad-loader.js"
REVIEWS_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "reviews.js"
REVIEW_REPORT_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "review_report.js"
AUTH_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "auth.js"
ANALYTICS_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "analytics.js"


def template_name_to_public_path(template_name):
    if template_name == "reviews.html":
        return "/reviews"
    return "/" + template_name.removesuffix(".html").replace("_", "-")


def test_standalone_public_auth_has_its_own_api_base():
    """Login must not depend on the private dashboard bundle being present."""
    source = AUTH_JS.read_text(encoding="utf-8")

    assert "const AUTH_API_BASE" in source
    assert "`${AUTH_API_BASE}/auth/login`" in source
    assert "`${AUTH_API_BASE}/auth/register`" in source
    assert "`${API_BASE}/auth/" not in source

    public_template = (INDEX_HTML.parent / "public_landing.html").read_text(encoding="utf-8")
    public_auth = re.search(r'src="/auth\.js\?v=([^\"]+)"', public_template)
    assert public_auth, "The public shell needs the versioned authentication bundle"
    assert f'src="./auth.js?v={public_auth.group(1)}"' in INDEX_HTML.read_text(encoding="utf-8")
    assert "/auth/reset-password?" not in source
    assert "JSON.stringify({ token, new_password: newPassword })" in source


def test_review_modal_does_not_decode_attributes_with_inner_html():
    """Review modal should not reinterpret attribute text as HTML."""
    source = APP_JS.read_text(encoding="utf-8")
    review_modal_start = source.index("function openReviewModal")
    review_modal_end = source.index("function closeReviewModal")
    review_modal_source = source[review_modal_start:review_modal_end]

    assert "innerHTML" not in review_modal_source
    assert "replaceChildren(review)" in review_modal_source
    assert "textContent = reviewRaw" in review_modal_source


def test_music_and_books_privacy_controls_are_wired():
    """Music and books settings should save the same fields the API exposes."""
    source = APP_JS.read_text(encoding="utf-8")
    template = INDEX_HTML.read_text(encoding="utf-8")

    for control_id in ("musicPrivate", "booksPrivate", "musicVisible", "booksVisible"):
        assert f'id="{control_id}"' in template
        assert f"document.getElementById('{control_id}')" in source

    for field_name in ("music_private", "books_private", "music_visible", "books_visible"):
        assert field_name in source


def test_library_insights_frontend_is_wired():
    """Statistics dashboard should expose and request the library insights panel."""
    source = APP_JS.read_text(encoding="utf-8")
    template = INDEX_HTML.read_text(encoding="utf-8")

    assert 'data-toggle-category-accordion="library-insights"' in template
    assert 'id="libraryInsightsStatsData"' in template
    assert "\u00e2\u2013\u00b6" not in template
    assert "&#9654;" in template
    assert "'library-insights': 'insights'" in source
    assert "displayLibraryInsights(stats)" in source


def test_adsense_loader_respects_authenticated_app_shell():
    """Root app shell should not directly load AdSense for authenticated users."""
    template = INDEX_HTML.read_text(encoding="utf-8")
    loader = AD_LOADER_JS.read_text(encoding="utf-8")

    assert "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" not in template
    assert "google-adsense-account" in template
    assert "omnitrackr_user" in loader
    assert "omnitrackr_token" in loader
    assert "omnitrackr_session=" in loader
    assert "hasSessionCookie()" in loader
    assert "document.documentElement.classList.contains('authenticated')" in loader
    assert "document.head.appendChild(script)" in loader
    assert "scheduleAdScript()" in loader


def test_analytics_is_public_only_and_honors_browser_privacy_signals():
    """Acquisition measurement must stay out of the private dashboard."""
    dashboard = INDEX_HTML.read_text(encoding="utf-8")
    public_landing = (INDEX_HTML.parent / "public_landing.html").read_text(encoding="utf-8")
    loader = ANALYTICS_JS.read_text(encoding="utf-8")

    assert "analytics.js" not in dashboard
    assert 'src="/analytics.js"' in public_landing
    assert "googletagmanager.com/gtag/js" not in public_landing
    assert "data-public-shell" in loader
    assert "navigator.globalPrivacyControl === true" in loader
    assert "navigator.doNotTrack === '1'" in loader
    assert "window.doNotTrack === '1'" in loader
    assert "allow_google_signals: false" in loader
    assert "allow_ad_personalization_signals: false" in loader


def test_adsense_loader_has_client_side_public_path_allowlist():
    """Ad loader should defend against accidental inclusion on private or utility pages."""
    loader = AD_LOADER_JS.read_text(encoding="utf-8")

    assert "const AD_ELIGIBLE_PATHS = new Set" in loader
    assert "isAdEligiblePath()" in loader
    assert "!isAdEligiblePath()" in loader
    assert r"^\/reviews\/\d+$" in loader
    for path in (
        "/media-tracking",
        "/sample-library",
        "/review-guidelines",
        "/export-import-guide",
    ):
        assert f"'{path}'" in loader
    for path in (
        "/",
        "/privacy",
        "/advertising",
        "/content-quality",
        "/site-map",
        "/terms",
        "/contact",
        "/account",
        "/about",
        "/faq",
        "/media-tracker-checklist",
        "/reviews",
        "/demo",
    ):
        assert f"'{path}'" not in loader


def test_adsense_server_and_client_allowlists_stay_in_sync():
    """Server-side and client-side ad allowlists should not drift apart."""
    main_source = MAIN_PY.read_text(encoding="utf-8")
    loader = AD_LOADER_JS.read_text(encoding="utf-8")

    template_match = re.search(r"AD_ELIGIBLE_TEMPLATES = \{(?P<body>.*?)\n\}", main_source, re.S)
    path_match = re.search(r"AD_ELIGIBLE_PATHS = new Set\(\[(?P<body>.*?)\]\)", loader, re.S)

    assert template_match is not None
    assert path_match is not None

    server_templates = set(re.findall(r'"([^"]+\.html)"', template_match.group("body")))
    client_paths = set(re.findall(r"'([^']+)'", path_match.group("body")))
    server_paths = {template_name_to_public_path(template_name) for template_name in server_templates}

    assert server_paths == client_paths


def test_adsense_loader_honors_browser_privacy_signals():
    """Public ads should stay conservative when visitors request less tracking."""
    loader = AD_LOADER_JS.read_text(encoding="utf-8")

    assert "prefersLimitedTracking()" in loader
    assert "navigator.globalPrivacyControl === true" in loader
    assert "navigator.doNotTrack === '1'" in loader
    assert "window.doNotTrack === '1'" in loader
    assert "navigator.connection.saveData === true" in loader


def test_adsense_loader_waits_for_idle_and_skips_noindex_pages():
    """Public ad loading should stay non-intrusive and avoid noindex review surfaces."""
    loader = AD_LOADER_JS.read_text(encoding="utf-8")

    assert "function isNoindexPage()" in loader
    assert "meta[name=\"robots\"]" in loader
    assert r"\bnoindex\b" in loader
    assert "requestIdleCallback" in loader
    assert "window.addEventListener('load', runWhenIdle, { once: true })" in loader
    assert "window.setTimeout(appendAdScript, 1200)" in loader


def test_reviews_frontend_requests_substantial_public_reviews():
    """Browsing uses the server-gated feed instead of requesting unfiltered notes."""
    source = REVIEWS_JS.read_text(encoding="utf-8")

    assert "/api/public/review-feed?" in source
    assert "min_chars=" not in source


def test_reviews_frontend_only_links_standalone_review_details():
    """Directory-quality reviews should not become clickable links to 404 detail pages."""
    source = REVIEWS_JS.read_text(encoding="utf-8")

    assert "function isStandaloneReview(review)" in source
    assert "return review.search_ready === true" in source
    assert "card.classList.add('review-card--summary')" in source
    assert "if (isStandalone)" in source
    assert "link.href = reviewUrl" in source
    assert "clearReplacedReviewSchema()" in source
    assert "data.mainEntity.itemListElement = []" in source


def test_review_reporting_uses_safe_dom_and_encoded_route_values():
    """Report reasons and status must be rendered as text, never interpreted markup."""
    source = REVIEW_REPORT_JS.read_text(encoding="utf-8")

    assert ".innerHTML" not in source
    assert "textContent = text" in source
    assert "status.textContent" in source
    assert "encodeURIComponent(form.dataset.category)" in source
    assert "encodeURIComponent(form.dataset.reviewId)" in source
    assert "data-review-report" in source


def test_app_review_forms_prompt_for_substantial_public_reviews():
    """In-app review fields should help users write useful public reviews without blocking saves."""
    source = APP_JS.read_text(encoding="utf-8")
    template = INDEX_HTML.read_text(encoding="utf-8")

    assert template.count("data-review-quality-input") == 6
    assert template.count("data-review-counter-for=") == 6
    assert template.count("0/80 characters - add context for the community feed") == 6
    assert template.count('href="/review-guidelines"') >= 6
    assert 'class="review-quality-hint"' in source
    assert "const PUBLIC_REVIEW_MIN_CHARS = 80" in source
    assert "setupReviewQualityCounters()" in source
    assert "getReviewQualityMessage(textarea.value)" in source
    assert "Search-ready baseline met" in source
    assert "SEARCH_READY_REVIEW_MIN_CHARS = 240" in source
    assert "SEARCH_READY_REVIEW_MIN_WORDS = 35" in source
    assert source.count("${reviewQualityHintHtml('edit-") == 6


def test_library_launchpad_is_client_side_and_uses_existing_insights():
    """First-use guidance should be optional and must not mutate library records."""
    source = APP_JS.read_text(encoding="utf-8")
    template = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="libraryLaunchpad"' in template
    assert 'id="libraryLaunchpadCategories"' in template
    assert 'data-action="launchpad-add-item"' in template
    assert 'data-action="launchpad-open-insights"' in template
    assert 'data-action="launchpad-dismiss"' in template
    assert "const LAUNCHPAD_DISMISS_KEY" in source
    assert "function renderLibraryLaunchpad(insights)" in source
    assert "function openLaunchpadAddItem(category = 'movies')" in source
    assert "'launchpad-choose-category': () => openLaunchpadQuickCapture(target.dataset.launchpadCategory)" in source
    assert "button.dataset.launchpadCategory = category" in source
    assert "`${API_BASE}/statistics/insights/`" in source
    assert "localStorage.setItem(LAUNCHPAD_DISMISS_KEY, 'true')" in source
    assert "openLaunchpadAddItem" in source
    assert "openLaunchpadInsights" in source


def test_library_pulse_uses_safe_dom_rendering_and_existing_tabs():
    """Pulse cards should not interpolate library titles into HTML or create new records."""
    source = APP_JS.read_text(encoding="utf-8")
    template = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="libraryPulse"' in template
    assert 'id="libraryPulseContinue"' in template
    assert 'id="libraryPulseReflect"' in template
    assert "function renderLibraryPulseList" in source
    assert "`${API_BASE}/statistics/pulse/`" in source
    assert "title.textContent = item.title" in source
    assert "button.dataset.pulseTab = item.category" in source
    assert "'pulse-open-item': () => switchTab(target.dataset.pulseTab)" in source


def test_welcome_back_deck_reuses_safe_dom_and_replaces_overlapping_cards():
    source = APP_JS.read_text(encoding="utf-8")
    template = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="returnDeck"' in template
    assert "actions.replaceChildren()" in source
    assert "title.textContent = item.title" in source
    assert "returnDeckActive = true" in source
    assert "document.getElementById('todaysPick')?.setAttribute('hidden', '')" in source
    assert "document.getElementById('libraryPulse')?.setAttribute('hidden', '')" in source
    assert "sessionStorage.getItem('omnitrackr_return_prompt')" in source
    assert "function refreshDashboardDecisionCards()" in source
    assert "if (!returnDeckBootstrapComplete || returnDeckActive || returnDeckPending) return false" in source
    assert "if (shouldRefreshDecisionCards) refreshDashboardDecisionCards()" in source


def test_quick_capture_searches_every_core_type_without_writing_directly():
    """Quick capture should prefill proven forms and leave the final save to the user."""
    source = APP_JS.read_text(encoding="utf-8")
    template = INDEX_HTML.read_text(encoding="utf-8")
    quick_capture = source[source.index("// Universal quick capture"):source.index("function showImagePopup")]

    assert 'id="quickCaptureButton"' in template
    assert 'id="quickCaptureModal"' in template
    assert 'data-submit-action="search-quick-capture"' in template
    assert template.count('data-action="select-quick-capture-category"') == 7
    assert "const QUICK_CAPTURE_CATEGORY_ORDER = ['movies', 'tv-shows', 'anime', 'video-games', 'music', 'books']" in quick_capture
    for provider in ("omdb", "jikan", "rawg", "itunes", "openlibrary"):
        assert f"/api/proxy/{provider}" in quick_capture
    assert "function applyQuickCaptureResult" in quick_capture
    assert "prepareQuickCaptureDestination" in quick_capture
    assert "openLaunchpadAddItem(category)" in quick_capture
    assert "Replace the unsaved entry currently in this form?" in quick_capture
    assert "method: 'POST'" not in quick_capture
    assert "title.textContent = item.title" in quick_capture
    assert "quickCaptureController?.abort()" in quick_capture
