import re
from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "app.js"
MAIN_PY = Path(__file__).resolve().parents[1] / "app" / "main.py"
INDEX_HTML = Path(__file__).resolve().parents[1] / "app" / "templates" / "index.html"
AD_LOADER_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "ad-loader.js"
REVIEWS_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "reviews.js"


def template_name_to_public_path(template_name):
    if template_name == "reviews.html":
        return "/reviews"
    return "/" + template_name.removesuffix(".html").replace("_", "-")


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


def test_adsense_loader_has_client_side_public_path_allowlist():
    """Ad loader should defend against accidental inclusion on private or utility pages."""
    loader = AD_LOADER_JS.read_text(encoding="utf-8")

    assert "const AD_ELIGIBLE_PATHS = new Set" in loader
    assert "isAdEligiblePath()" in loader
    assert "!isAdEligiblePath()" in loader
    assert r"^\/reviews\/\d+$" in loader
    for path in (
        "/about",
        "/reviews",
        "/media-tracking",
        "/sample-library",
        "/review-guidelines",
        "/media-tracker-checklist",
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
    """The public reviews page should not replace curated SSR content with short notes."""
    source = REVIEWS_JS.read_text(encoding="utf-8")

    assert "min_chars=80" in source


def test_reviews_frontend_only_links_standalone_review_details():
    """Directory-quality reviews should not become clickable links to 404 detail pages."""
    source = REVIEWS_JS.read_text(encoding="utf-8")

    assert "const PUBLIC_REVIEW_DETAIL_MIN_CHARS = 240" in source
    assert "function isStandaloneReview(review)" in source
    assert "card.classList.add('review-card--summary')" in source
    assert "if (isStandalone)" in source
    assert "item.url = reviewUrl" in source
    assert "listItem.url = reviewUrl" in source


def test_app_review_forms_prompt_for_substantial_public_reviews():
    """In-app review fields should help users write useful public reviews without blocking saves."""
    source = APP_JS.read_text(encoding="utf-8")
    template = INDEX_HTML.read_text(encoding="utf-8")

    assert template.count("data-review-quality-input") == 6
    assert template.count("data-review-counter-for=") == 6
    assert template.count("0/80 characters - add more context for public reviews") == 6
    assert template.count('href="/review-guidelines"') >= 6
    assert 'class="review-quality-hint"' in source
    assert "const PUBLIC_REVIEW_MIN_CHARS = 80" in source
    assert "setupReviewQualityCounters()" in source
    assert "getReviewQualityMessage(length)" in source
    assert "public-ready context" in source
    assert source.count("${reviewQualityHintHtml('edit-") == 6
