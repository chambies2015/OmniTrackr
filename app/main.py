"""
Entry point for the OmniTrackr API.
Provides CRUD endpoints for managing movies and TV shows.
"""
import asyncio
import hashlib
import os
import re
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.middleware.gzip import GZipMiddleware
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session, undefer

from .integer_bounds import PositiveDatabaseId, SQL_INTEGER_MAX
from . import crud, schemas, models, dashboard_assets, error_pages
from .database import Base, SessionLocal, engine
from .site_chrome import apply_app_chrome, apply_site_chrome
from .reader_pages import enhance as enhance_reader_page
from .csp import nonce_html_response, strict_html_response
from .auth import AUTH_COOKIE_NAME
from .migrations import run_migrations
from .middleware import SecurityHeadersMiddleware, BotFilterMiddleware, CSRFProtectionMiddleware, RequestBodyLimitMiddleware, UploadAuthenticationMiddleware
from .site_traffic import RECORDER as TRAFFIC_RECORDER, SiteTrafficMiddleware
from . import digest as digest_emails
from . import funnel, start_flow
from .dependencies import get_db, get_current_user, get_optional_current_user
from .routers import (
    auth,
    account,
    friends,
    notifications,
    movies,
    tv_shows,
    anime,
    video_games,
    music,
    books,
    manga,
    podcasts,
    audiobooks,
    statistics,
    export_import,
    proxy,
    seo,
    static,
    custom_tabs,
    reviews,
    next_up,
    completion_moments,
    activity,
    progress,
    collections,
    discover,
    release_radar,
    import_studio,
    recommendations,
    site_stats,
    for_you,
    titles,
    profiles,
    pwa,
    supporters,
    year_in_review,
)

Base.metadata.create_all(bind=engine)

run_migrations()

@asynccontextmanager
async def lifespan(application: FastAPI):
    """Own pooled network resources and lightweight startup maintenance."""
    from . import editorial_collections, release_radar as radar_data
    radar_data.bind_event_loop(asyncio.get_running_loop())
    application.state.external_api_client = httpx.AsyncClient(
        timeout=httpx.Timeout(12.0, connect=5.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        follow_redirects=False,
    )
    try:
        db = SessionLocal()
        try:
            expired_count = crud.expire_friend_requests(db)
            if expired_count > 0:
                print(f"Expired {expired_count} old friend requests on startup")
        finally:
            db.close()
    except Exception as e:
        print(f"Error expiring friend requests on startup: {e}")
    try:
        db = SessionLocal()
        try:
            refreshed = editorial_collections.refresh_copy(db)
            if refreshed:
                print(f"Updated wording on {len(refreshed)} editor collections on startup")
        finally:
            db.close()
    except Exception as e:
        print(f"Error updating editor collection wording on startup: {e}")

    digest_task = None
    title_task = None
    announcement_task = None
    if digest_emails.enabled_for_process():
        digest_task = asyncio.create_task(digest_emails.digest_loop(application))
    from . import announcements
    if announcements.enabled_for_process():
        announcement_task = asyncio.create_task(announcements.announcement_loop(application))
    from . import comeback
    comeback_task = None
    if comeback.enabled_for_process():
        comeback_task = asyncio.create_task(comeback.comeback_loop(application))
    from . import welcome_emails
    welcome_task = None
    if welcome_emails.enabled_for_process():
        welcome_task = asyncio.create_task(welcome_emails.welcome_loop(application))
    from . import web_push
    push_task = None
    if web_push.dispatch_enabled():
        push_task = asyncio.create_task(web_push.push_loop(application))
    from . import episode_calendar
    episode_task = None
    if episode_calendar.enabled_for_process():
        episode_task = asyncio.create_task(episode_calendar.sweep_loop(application))
    roundup_task = None
    if os.getenv("TESTING", "").lower() != "true":
        title_task = asyncio.create_task(titles.warm_loop(application))
        from .routers import weekly_roundup as weekly_roundup_router
        roundup_task = asyncio.create_task(weekly_roundup_router.roundup_loop(application))
    try:
        yield
    finally:
        for task in (digest_task, title_task, announcement_task, comeback_task, welcome_task, push_task, roundup_task,
                     episode_task):
            if task is not None:
                task.cancel()
        await application.state.external_api_client.aclose()
        try:
            TRAFFIC_RECORDER.flush()  # Keep the last minute of page-view counts.
        except Exception:
            pass


app = FastAPI(
    title="OmniTrackr API",
    description="Manage your movies, TV shows, anime, video games, music, books, manga, podcasts, and audiobooks",
    version="0.1.0",
    lifespan=lifespan,
)

def client_address(request: Request) -> str:
    """The visitor's address for rate limits.

    On Render every request reaches the app from an internal load balancer, so
    limits keyed on the socket address were shared by all visitors (for example
    five sign-ups a minute for the whole site). Render sits behind Cloudflare,
    which sets True-Client-IP / CF-Connecting-IP to the real visitor and
    overwrites any value a client sends. Those headers are trusted only when
    running on Render (RENDER=true, set by Render itself).
    """
    if os.getenv("RENDER", "").lower() == "true":
        for header in ("true-client-ip", "cf-connecting-ip"):
            value = (request.headers.get(header) or "").strip()
            if value:
                return value[:64]
    return get_remote_address(request)


if os.getenv("TESTING", "").lower() == "true":
    limiter = Limiter(key_func=lambda: "test", enabled=False)
else:
    limiter = Limiter(key_func=client_address)
app.state.limiter = limiter
error_pages.install(app)


def bind_rate_limited_endpoint(route, endpoint) -> None:
    """Replace both the visible endpoint and FastAPI's captured request callable."""
    route.endpoint = endpoint
    if hasattr(route, "dependant"):
        route.dependant.call = endpoint


app.add_middleware(RequestBodyLimitMiddleware)
app.add_middleware(UploadAuthenticationMiddleware)
app.add_middleware(CSRFProtectionMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BotFilterMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SiteTrafficMiddleware)

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

# Trust pages (privacy, terms, contact, editorial standards) stay indexable so search and ad
# reviewers see the same site identity a visitor does; they are still left out
# of the sitemap. The source-checked comparison is original reference content.
INDEXABLE_PUBLIC_TEMPLATES = {
    "about.html",
    "compare.html",
    "contact.html",
    "content_quality.html",
    "demo.html",
    "export_import_guide.html",
    "faq.html",
    "guides.html",
    "media_tracking.html",
    "review_guidelines.html",
    "sample_library.html",
    "switch.html",
    "privacy.html",
    "reviews.html",
    "terms.html",
    # The category tracker guides and use cases answer the searches people actually
    # type ("anime tracker", "game backlog tracker"). Indexed since October 2026,
    # but still outside AD_ELIGIBLE_TEMPLATES, so ad inventory is unchanged.
    "movie_tracker.html",
    "tv_show_tracker.html",
    "anime_tracker.html",
    "game_tracker.html",
    "book_tracker.html",
    "manga_tracker.html",
    "podcast_tracker.html",
    "audiobook_tracker.html",
    "music_tracker.html",
    "use_cases.html",
}

# Ads are limited to the small set of pages that provide a complete experience
# without an account.  Directory, policy, release-note, and overlapping guide
# pages remain useful and linked, but are not treated as advertising inventory.
AD_ELIGIBLE_TEMPLATES = {
    "export_import_guide.html",
    "media_tracking.html",
    "review_guidelines.html",
    "sample_library.html",
}

NOFOLLOW_PUBLIC_TEMPLATES = {"recommendation_postcard.html"}


def inject_adsense_account_meta(html: str) -> str:
    publisher_id = os.getenv("ADSENSE_PUBLISHER_ID", "pub-7271682066779719")
    account = publisher_id if publisher_id.startswith("ca-") else f"ca-{publisher_id}"
    if "google-adsense-account" in html or "</head>" not in html:
        return html
    meta = f'  <meta name="google-adsense-account" content="{account}">\n'
    return html.replace("</head>", f"{meta}</head>", 1)


def inject_public_ad_loader(html: str, template_name: str, request: Request | None = None) -> str:
    if template_name not in AD_ELIGIBLE_TEMPLATES:
        return html
    if request and request.cookies.get(AUTH_COOKIE_NAME):
        return html
    if "/static/ad-loader.js" in html or "</head>" not in html:
        return html
    loader = '  <script src="/static/ad-loader.js" defer></script>\n'
    return html.replace("</head>", f"{loader}</head>", 1)


def apply_public_search_policy(html: str, template_name: str) -> tuple[str, bool]:
    """Keep useful supporting pages accessible without diluting search inventory."""
    indexable = template_name in INDEXABLE_PUBLIC_TEMPLATES
    if indexable:
        return html, True

    directive = "noindex, nofollow" if template_name in NOFOLLOW_PUBLIC_TEMPLATES else "noindex, follow"
    noindex_meta = f'<meta name="robots" content="{directive}">'
    robots_pattern = r'<meta\s+name=["\']robots["\']\s+content=["\'][^"\']*["\']\s*/?>'
    if re.search(robots_pattern, html, flags=re.IGNORECASE):
        html = re.sub(robots_pattern, noindex_meta, html, count=1, flags=re.IGNORECASE)
    elif "</head>" in html:
        html = html.replace("</head>", f"  {noindex_meta}\n</head>", 1)
    return html, False


def strict_template_response(template_name: str, request: Request | None = None, replacements: dict | None = None):
    html_file = os.path.join(os.path.dirname(__file__), "templates", template_name)
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as file:
            source = file.read()
            for marker, value in (replacements or {}).items():
                source = source.replace(marker, value)
            html, indexable = apply_public_search_policy(
                enhance_reader_page(apply_site_chrome(source), template_name), template_name)
            html = inject_adsense_account_meta(html)
            response = strict_html_response(inject_public_ad_loader(html, template_name, request))
            response.headers["Vary"] = "Cookie"
            if not indexable:
                response.headers["X-Robots-Tag"] = (
                    "noindex, nofollow" if template_name in NOFOLLOW_PUBLIC_TEMPLATES else "noindex, follow"
                )
            return response
    return None


GOOGLE_G_SVG = (
    '<svg class="auth-google__logo" viewBox="0 0 18 18" width="18" height="18" aria-hidden="true" focusable="false">'
    '<path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z"/>'
    '<path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z"/>'
    '<path fill="#FBBC05" d="M3.97 10.72A5.4 5.4 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.95H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.05l3.01-2.33z"/>'
    '<path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z"/>'
    '</svg>'
)


def google_signin_html(label: str, signup: bool = False) -> str:
    """The "Sign up / Log in with Google" button shown above the email forms."""
    marker = " data-google-signup" if signup else ""
    return (
        f'<a class="auth-google" href="/auth/google/start" rel="nofollow" data-google-signin{marker}>{GOOGLE_G_SVG}'
        f'<span>{label}</span></a><p class="auth-or"><span>or use your email</span></p>'
    )


def hero_signup_html(google: bool) -> str:
    """The quieter sign-up row under the homepage search.

    Searching for a title and saving it is the hero's main action (the save bar then
    offers sign-up); this row is for visitors who already know they want an account.
    The email button opens the sign-up form in a pop-up (public-landing.js).
    """
    if not google:
        return (
            '<p class="lp-hero__alt">Already sure? '
            '<button type="button" class="lp-linkbtn" data-action="show-register-form" data-hero-signup>Create a free library</button>'
            ' or <a href="/demo">try the demo</a> first.</p>'
        )
    return (
        '<div class="lp-hero__alt"><span class="lp-hero__alt-label">Already sure?</span>'
        f'<a class="lp-btn lp-btn--google lp-btn--compact" href="/auth/google/start" rel="nofollow" data-google-signin data-google-signup data-hero-signup>{GOOGLE_G_SVG}'
        '<span>Continue with Google</span></a>'
        '<button type="button" class="lp-btn lp-btn--ghost lp-btn--compact" data-action="show-register-form" data-hero-signup>Sign up with email</button>'
        '<a class="lp-hero__alt-demo" href="/demo">or try the demo</a></div>'
    )


def savebar_signup_html(google: bool) -> str:
    """Sign-up buttons on the bar that appears once a guest has saved a title."""
    email = ('<button type="button" class="lp-btn lp-btn--primary lp-btn--small" data-action="show-register-form">'
             f'{"Use email" if google else "Keep my list, free"}</button>')
    if not google:
        return email
    return (f'<a class="lp-btn lp-btn--google lp-btn--small" href="/auth/google/start" rel="nofollow" data-google-signin data-google-signup>{GOOGLE_G_SVG}'
            '<span><span class="lp-savebar__wide">Continue with </span>Google</span></a>' + email)


def season_link_html() -> str:
    """The seasonal hub tile in the homepage's no-account row: the running season, else the next one."""
    from datetime import datetime
    from . import seasonal
    from .seasonal_guides import SEASONS
    today = datetime.utcnow().date()
    slug = seasonal.current(today)
    if slug is None:
        def next_start(entry):
            start, _ = seasonal._bounds(entry, today.year)
            return start if start >= today else seasonal._bounds(entry, today.year + 1)[0]
        slug = min(SEASONS, key=lambda key: next_start(SEASONS[key]))
    entry = SEASONS[slug]
    return (f'<li><a class="lp-try" href="{entry["path"]}"><span class="lp-try__kicker">Seasonal</span>'
            f'<strong>{entry["name"]} picks</strong><span>Films, shows, games and books for the season</span></a></li>')


def _warm_homepage_sections() -> None:
    """Rebuild the homepage's cached database sections when they are due, off the event loop.

    Each rebuild reads every public review and the most popular titles (seconds on a
    large library). Run inline, it stalled every other request while it ran.
    """
    from . import guest_picks, landing_proof
    for section in (guest_picks.homepage_section, landing_proof.homepage_section, landing_proof.hero_section):
        try:
            section()
        except Exception:
            pass  # public_root_html() leaves the section out, as before.


def public_root_html(html: str, request: Request | None = None) -> str:
    """Return the standalone public landing experience without the private app shell.

    The dashboard and its empty tables used to be sent to every anonymous visitor and
    hidden only with CSS. A dedicated public template is clearer for visitors and
    crawlers, while signed-in visitors still receive the complete dashboard unchanged.
    The previous extraction path remains as a safe fallback for incomplete deployments.
    """
    public_template = os.path.join(os.path.dirname(__file__), "templates", "public_landing.html")
    if os.path.exists(public_template):
        with open(public_template, "r", encoding="utf-8") as file:
            page = file.read()
        if "<!--RELEASE_RADAR_STRIP-->" in page:
            strip = ""
            try:
                client = getattr(request.app.state, "external_api_client", None) if request else None
                strip = release_radar.home_strip_html(client)
            except Exception:
                strip = ""  # The homepage never depends on third-party release data.
            page = page.replace("<!--RELEASE_RADAR_STRIP-->", strip, 1)
        if "<!--GUEST_PICKS-->" in page:
            try:
                from . import guest_picks
                picks_html = guest_picks.homepage_section()
            except Exception:
                picks_html = ""  # The homepage never depends on this section.
            page = page.replace("<!--GUEST_PICKS-->", picks_html, 1)
        if "<!--LATEST_GUIDES-->" in page:
            try:
                from . import editorial_index
                guides_html = editorial_index.homepage_section()
            except Exception:
                guides_html = ""  # The homepage never depends on this section.
            page = page.replace("<!--LATEST_GUIDES-->", guides_html, 1)
        if "<!--COMMUNITY_PROOF-->" in page:
            try:
                from . import landing_proof
                proof_html = landing_proof.homepage_section()
            except Exception:
                proof_html = ""  # The homepage never depends on this section.
            page = page.replace("<!--COMMUNITY_PROOF-->", proof_html, 1)
        if "<!--HERO_PROOF-->" in page:
            try:
                from . import landing_proof
                hero_proof = landing_proof.hero_section()
            except Exception:
                hero_proof = ""  # The homepage never depends on this line.
            page = page.replace("<!--HERO_PROOF-->", hero_proof, 1)
        if "<!--SEASON_LINK-->" in page:
            page = page.replace("<!--SEASON_LINK-->", season_link_html(), 1)
        from . import google_signin
        google = google_signin.configured()
        for form, label in (("login", "Log in with Google"), ("register", "Sign up with Google")):
            page = page.replace(f"<!--GOOGLE_SIGNIN:{form}-->", google_signin_html(label, form == "register") if google else "", 1)
        page = page.replace("<!--HERO_SIGNUP-->", hero_signup_html(google), 1)
        page = page.replace("<!--SAVEBAR_SIGNUP-->", savebar_signup_html(google), 1)
        if "<!--HERO_QUICK_PICKS-->" in page:
            try:
                from . import guest_picks
                quick = guest_picks.hero_quick_picks()
            except Exception:
                quick = ""  # The homepage never depends on this row.
            page = page.replace("<!--HERO_QUICK_PICKS-->", quick, 1)
        return apply_site_chrome(page, login_action=True)

    landing_marker = "  <!-- Landing Page -->"
    scripts_marker = '  <script src="./credentials.js"></script>'
    body_match = re.search(r"<body[^>]*>", html, flags=re.IGNORECASE)
    landing_start = html.find(landing_marker)
    scripts_start = html.rfind(scripts_marker)

    # Keep the original page usable if a future template edit moves a marker.
    if not body_match or landing_start == -1 or scripts_start == -1 or landing_start >= scripts_start:
        return html

    public_head = html[:body_match.end()]
    public_head = public_head.replace(
        '<html lang="en">',
        '<html lang="en" data-public-shell="true">',
        1,
    )
    public_head = public_head.replace('  <script src="./preauth.js?v=20261010-audit-preauth-1"></script>\n', "", 1)
    public_tail = html[scripts_start:].replace(
        '  <script src="./app.js"></script>',
        '  <script src="/static/public-landing.js" defer></script>',
        1,
    )
    return f"{public_head}\n{html[landing_start:scripts_start]}{public_tail}"
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_str:
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]
else:
    allowed_origins = ["*"]

if ENVIRONMENT == "production" and "*" in allowed_origins:
    raise ValueError("CORS allow_origins cannot be '*' in production. Set ALLOWED_ORIGINS environment variable.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Profile pictures live in the database; /profile-pictures/ keeps them clear of the /static/ mount.
@app.get("/profile-pictures/{user_id}")
def serve_profile_picture(
    user_id: PositiveDatabaseId,
    request: Request,
    viewer: models.User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Serve profile pictures from database."""
    user = db.query(models.User).options(undefer(models.User.profile_picture_data)).filter(models.User.id == user_id).first()
    if not user or not user.is_active or not user.profile_picture_data:
        raise HTTPException(status_code=404, detail="Profile picture not found")
    own_or_friend = viewer is not None and (viewer.id == user.id or crud.are_friends(db, viewer.id, user.id))
    public = db.query(models.PublicProfile.id).filter_by(user_id=user.id, enabled=True).first() is not None
    if not own_or_friend and not public:
        raise HTTPException(status_code=404, detail="Profile picture not found")
    
    mime_type = user.profile_picture_mime_type or "image/jpeg"
    # Friends lists show the same pictures on every visit. The browser keeps its copy and
    # asks each time (no-cache), so a new picture or lost access still shows at once,
    # but an unchanged picture costs a 304 instead of the whole image.
    etag = '"' + hashlib.blake2b(user.profile_picture_data, digest_size=16).hexdigest() + '"'
    headers = {"ETag": etag, "Cache-Control": "private, no-cache", "Vary": "Cookie"}
    if etag in [tag.strip() for tag in request.headers.get("if-none-match", "").split(",")]:
        return Response(status_code=304, headers=headers)
    return Response(content=user.profile_picture_data, media_type=mime_type, headers=headers)


@app.get("/custom-tab-posters/{item_id}")
def serve_custom_tab_poster(
    item_id: PositiveDatabaseId,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serve a custom-tab poster only to the owner of that private tab."""
    item = (
        db.query(models.CustomTabItem)
        .options(undefer(models.CustomTabItem.poster_data))
        .join(models.CustomTab, models.CustomTabItem.tab_id == models.CustomTab.id)
        .filter(
            models.CustomTabItem.id == item_id,
            models.CustomTab.user_id == current_user.id,
        )
        .first()
    )
    if not item or not item.poster_data:
        raise HTTPException(status_code=404, detail="Poster not found")
    
    mime_type = item.poster_mime_type or "image/jpeg"
    return Response(content=item.poster_data, media_type=mime_type)


# Old filename-based picture URLs redirect to the database route. Registered
# before the static mount so it takes precedence.
@app.get("/static/profile_pictures/{filename}")
async def serve_profile_picture_old(filename: str):
    """Backward compatibility endpoint for old profile picture URLs."""
    match = re.match(r'^([0-9]{1,10})_', filename)
    if match:
        user_id = int(match.group(1))
        if 1 <= user_id <= SQL_INTEGER_MAX:
            return RedirectResponse(url=f"/profile-pictures/{user_id}", status_code=301)
    raise HTTPException(status_code=404, detail="Profile picture not found")


static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Apply rate limiting to auth endpoints before including the router. FastAPI
# copies APIRoute objects during include_router(), so changing the source router
# afterward would leave the application's registered handlers unprotected.
for route in auth.router.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods') and hasattr(route, 'endpoint'):
        if route.path == "/auth/register" and 'POST' in route.methods:
            bind_rate_limited_endpoint(route, limiter.limit("5/minute")(route.endpoint))
        elif route.path == "/auth/login" and 'POST' in route.methods:
            bind_rate_limited_endpoint(route, limiter.limit("5/minute")(route.endpoint))
        elif route.path == "/auth/request-password-reset" and 'POST' in route.methods:
            bind_rate_limited_endpoint(route, limiter.limit("3/hour")(route.endpoint))
        elif route.path == "/auth/reset-password" and 'POST' in route.methods:
            bind_rate_limited_endpoint(route, limiter.limit("10/minute")(route.endpoint))
        elif route.path == "/auth/resend-verification" and 'POST' in route.methods:
            bind_rate_limited_endpoint(route, limiter.limit("3/hour")(route.endpoint))
        elif route.path == "/auth/reactivate" and 'POST' in route.methods:
            bind_rate_limited_endpoint(route, limiter.limit("5/minute")(route.endpoint))
        elif route.path == "/auth/login/two-factor" and 'POST' in route.methods:
            bind_rate_limited_endpoint(route, limiter.limit("10/minute")(route.endpoint))
        elif route.path == "/auth/passkey/options" and 'POST' in route.methods:
            bind_rate_limited_endpoint(route, limiter.limit("20/minute")(route.endpoint))
        elif route.path == "/auth/passkey/login" and 'POST' in route.methods:
            bind_rate_limited_endpoint(route, limiter.limit("10/minute")(route.endpoint))
        elif route.path in ("/auth/google/start", "/auth/google/callback") and 'GET' in route.methods:
            bind_rate_limited_endpoint(route, limiter.limit("20/minute")(route.endpoint))

app.include_router(auth.router)

# Include account router and apply rate limiting to profile picture upload
from .routers.account import upload_profile_picture
rate_limited_profile_picture = limiter.limit("10/minute")(upload_profile_picture)
for route in account.router.routes:
    if hasattr(route, 'path') and route.path == "/account/profile-picture" and hasattr(route, 'methods') and 'POST' in route.methods:
        bind_rate_limited_endpoint(route, rate_limited_profile_picture)
    # Each of these checks the current password, so a stolen session can't use them to guess it.
    elif getattr(route, "path", None) in ("/account/username", "/account/email", "/account/password", "/account/deactivate"):
        bind_rate_limited_endpoint(route, limiter.limit("10/minute")(route.endpoint))

app.include_router(account.router)
# Two-factor settings check a password or code, so they get the same guessing limit.
from .routers import two_factor as two_factor_router
for route in two_factor_router.router.routes:
    if "POST" in getattr(route, "methods", set()):
        bind_rate_limited_endpoint(route, limiter.limit("10/minute")(route.endpoint))
app.include_router(two_factor_router.router)
# Passkey settings check the password (or take a credential the browser made), so the same limit applies.
from .routers import passkeys as passkeys_router
for route in passkeys_router.router.routes:
    if "POST" in getattr(route, "methods", set()):
        bind_rate_limited_endpoint(route, limiter.limit("10/minute")(route.endpoint))
app.include_router(passkeys_router.router)
# Each request notifies (and can push to) the receiver, so a script can't send one to every member.
for route in friends.router.routes:
    if getattr(route, "path", None) == "/friends/request" and "POST" in getattr(route, "methods", set()):
        bind_rate_limited_endpoint(route, limiter.limit("60/hour")(route.endpoint))
app.include_router(friends.router)
app.include_router(notifications.router)
from .routers import library
app.include_router(library.router)
app.include_router(movies.router)
app.include_router(tv_shows.router)
app.include_router(anime.router)
app.include_router(video_games.router)
app.include_router(music.router)
app.include_router(books.router)
app.include_router(manga.router)
app.include_router(podcasts.router)
app.include_router(audiobooks.router)
rate_limited_return_deck = limiter.limit("30/minute")(statistics.get_return_deck)
rate_limited_return_engagement = limiter.limit("10/minute")(statistics.record_return_deck_engagement)
for route in statistics.router.routes:
    if not hasattr(route, "path") or not hasattr(route, "methods"):
        continue
    if route.path == "/statistics/return-deck/" and "GET" in route.methods:
        bind_rate_limited_endpoint(route, rate_limited_return_deck)
    elif route.path == "/statistics/return-deck/engagement" and "POST" in route.methods:
        bind_rate_limited_endpoint(route, rate_limited_return_engagement)
app.include_router(statistics.router)
app.include_router(next_up.router)
app.include_router(completion_moments.router)
app.include_router(activity.router)
for route in progress.router.routes:
    if getattr(route, "path", None) == "/progress/{category}/{item_id}/episodes":
        bind_rate_limited_endpoint(route, limiter.limit("30/minute")(route.endpoint))
app.include_router(progress.router)
for route in import_studio.router.routes:
    if getattr(route, "path", None) in ("/import-studio/preview/", "/import-studio/apply/"):
        bind_rate_limited_endpoint(route, limiter.limit("30/minute")(route.endpoint))
    # Each call spends the site's Steam Web API quota (three requests to Steam).
    elif getattr(route, "path", None) == "/import-studio/steam/library/":
        bind_rate_limited_endpoint(route, limiter.limit("6/minute")(route.endpoint))
app.include_router(import_studio.router)
from .routers.recommendations import submit_public_recommendation
rate_limited_recommendation = limiter.limit("5/hour")(submit_public_recommendation)
for route in recommendations.router.routes:
    if (
        hasattr(route, "path")
        and route.path == "/recommendations/public/{token}"
        and hasattr(route, "methods")
        and "POST" in route.methods
    ):
        bind_rate_limited_endpoint(route, rate_limited_recommendation)
app.include_router(recommendations.router)
rate_limited_collection_view = limiter.limit("60/minute")(collections.public_collection)
rate_limited_collection_helpful = limiter.limit("20/hour")(collections.mark_collection_helpful)
rate_limited_collection_report = limiter.limit("2/hour")(collections.report_collection)
for route in collections.router.routes:
    if not hasattr(route, "path") or not hasattr(route, "methods"):
        continue
    if route.path == "/collections/public/{collection_id}" and "GET" in route.methods:
        bind_rate_limited_endpoint(route, rate_limited_collection_view)
    elif route.path == "/collections/public/{collection_id}/helpful" and "POST" in route.methods:
        bind_rate_limited_endpoint(route, rate_limited_collection_helpful)
    elif route.path == "/collections/public/{collection_id}/report" and "POST" in route.methods:
        bind_rate_limited_endpoint(route, rate_limited_collection_report)
app.include_router(collections.router)
app.include_router(discover.router)
app.include_router(release_radar.router)
for route in export_import.router.routes:
    if getattr(route, "path", None) in ("/import/", "/import/file/"):
        bind_rate_limited_endpoint(route, limiter.limit("10/hour")(route.endpoint))
    elif getattr(route, "path", None) == "/export/{fmt}/":
        bind_rate_limited_endpoint(route, limiter.limit("60/hour")(route.endpoint))
app.include_router(export_import.router)
for route in custom_tabs.router.routes:
    if getattr(route, "path", None) == "/custom-tabs/{tab_id}/items/{item_id}/poster":
        bind_rate_limited_endpoint(route, limiter.limit("30/minute")(route.endpoint))
app.include_router(custom_tabs.router)

# Rate-limit the metadata proxy endpoints before including the router.
from .routers.proxy import proxy_omdb_api, proxy_rawg_api, proxy_jikan_api, proxy_itunes_api, proxy_openlibrary_api, proxy_jikan_manga_api, proxy_itunes_podcast_api, proxy_itunes_audiobook_api

rate_limited_omdb = limiter.limit("60/minute")(proxy_omdb_api)
rate_limited_rawg = limiter.limit("60/minute")(proxy_rawg_api)
rate_limited_jikan = limiter.limit("60/minute")(proxy_jikan_api)
rate_limited_itunes = limiter.limit("60/minute")(proxy_itunes_api)
rate_limited_openlibrary = limiter.limit("60/minute")(proxy_openlibrary_api)
rate_limited_jikan_manga = limiter.limit("60/minute")(proxy_jikan_manga_api)
rate_limited_itunes_podcast = limiter.limit("60/minute")(proxy_itunes_podcast_api)
rate_limited_itunes_audiobook = limiter.limit("60/minute")(proxy_itunes_audiobook_api)

for route in proxy.router.routes:
    if hasattr(route, 'path') and route.path == "/api/proxy/omdb":
        bind_rate_limited_endpoint(route, rate_limited_omdb)
    elif hasattr(route, 'path') and route.path == "/api/proxy/rawg":
        bind_rate_limited_endpoint(route, rate_limited_rawg)
    elif hasattr(route, 'path') and route.path == "/api/proxy/jikan":
        bind_rate_limited_endpoint(route, rate_limited_jikan)
    elif hasattr(route, 'path') and route.path == "/api/proxy/itunes":
        bind_rate_limited_endpoint(route, rate_limited_itunes)
    elif hasattr(route, 'path') and route.path == "/api/proxy/openlibrary":
        bind_rate_limited_endpoint(route, rate_limited_openlibrary)
    elif hasattr(route, 'path') and route.path == "/api/proxy/jikan-manga":
        bind_rate_limited_endpoint(route, rate_limited_jikan_manga)
    elif hasattr(route, 'path') and route.path == "/api/proxy/itunes-podcasts":
        bind_rate_limited_endpoint(route, rate_limited_itunes_podcast)
    elif hasattr(route, 'path') and route.path == "/api/proxy/itunes-audiobooks":
        bind_rate_limited_endpoint(route, rate_limited_itunes_audiobook)

app.include_router(proxy.router)

app.include_router(seo.router)
app.include_router(static.router)
rate_limited_review_report = limiter.limit("2/hour")(reviews.report_public_review)
rate_limited_review_helpful = limiter.limit("30/hour")(reviews.mark_review_helpful)
for route in reviews.router.routes:
    if (getattr(route, "path", None) == "/api/public/reviews/{category}/{review_id}/helpful"
            and "POST" in getattr(route, "methods", set())):
        bind_rate_limited_endpoint(route, rate_limited_review_helpful)
for route in reviews.router.routes:
    if (
        hasattr(route, "path")
        and route.path == "/api/public/reviews/{category}/{review_id}/report"
        and hasattr(route, "methods")
        and "POST" in route.methods
    ):
        bind_rate_limited_endpoint(route, rate_limited_review_report)
app.include_router(reviews.router)
rate_limited_funnel_event = limiter.limit("30/minute")(site_stats.record_funnel_event)
rate_limited_page_visit = limiter.limit("60/minute")(site_stats.record_page_visit)
for route in site_stats.router.routes:
    if getattr(route, "path", None) == "/api/funnel":
        bind_rate_limited_endpoint(route, rate_limited_funnel_event)
    elif getattr(route, "path", None) == "/api/visit":
        bind_rate_limited_endpoint(route, rate_limited_page_visit)
app.include_router(site_stats.router)
app.include_router(for_you.router)
rate_limited_guest_import = limiter.limit("10/minute")(titles.import_guest_list)
rate_limited_title_review = limiter.limit("20/minute")(titles.save_title_review)
rate_limited_take_ask = limiter.limit("20/minute")(titles.ask_for_takes)
rate_limited_title_search = limiter.limit("60/minute")(titles.search_titles)
rate_limited_where_to_watch = limiter.limit("30/minute")(titles.where_to_watch_lookup)
for route in titles.router.routes:
    if getattr(route, "path", None) == "/api/guest-list/import":
        bind_rate_limited_endpoint(route, rate_limited_guest_import)
    elif getattr(route, "path", None) == "/api/titles/{kind}/{slug}/review":
        bind_rate_limited_endpoint(route, rate_limited_title_review)
    elif getattr(route, "path", None) == "/api/titles/{kind}/{slug}/ask":
        bind_rate_limited_endpoint(route, rate_limited_take_ask)
    elif getattr(route, "path", None) == "/api/titles/search":
        bind_rate_limited_endpoint(route, rate_limited_title_search)
    elif getattr(route, "path", None) == "/api/where-to-watch":
        bind_rate_limited_endpoint(route, rate_limited_where_to_watch)
from .routers import title_discussions
rate_limited_discussion_start = limiter.limit("10/hour")(title_discussions.start_thread)
rate_limited_discussion_reply = limiter.limit("30/minute")(title_discussions.add_reply)
rate_limited_discussion_edit = limiter.limit("30/minute")(title_discussions.edit_post)
rate_limited_discussion_report = limiter.limit("20/hour")(title_discussions.report_post)
for route in title_discussions.router.routes:
    path, methods = getattr(route, "path", None), getattr(route, "methods", set())
    if path == "/api/titles/{kind}/{slug}/discussions" and "POST" in methods:
        bind_rate_limited_endpoint(route, rate_limited_discussion_start)
    elif path == "/api/discussions/{thread_id}/replies":
        bind_rate_limited_endpoint(route, rate_limited_discussion_reply)
    elif path == "/api/discussions/{thread_id}" and "PATCH" in methods:
        bind_rate_limited_endpoint(route, rate_limited_discussion_edit)
    elif path == "/api/discussions/{thread_id}/report":
        bind_rate_limited_endpoint(route, rate_limited_discussion_report)
# Before titles.router: its /titles/{kind}/{slug} route must not shadow the board pages.
app.include_router(title_discussions.router)
app.include_router(titles.router)
from .routers import trending as trending_router
app.include_router(trending_router.router)
from .routers import people as people_router
app.include_router(people_router.router)

rate_limited_profile_card = limiter.limit("30/minute")(profiles.profile_card)
rate_limited_profile_card_by_id = limiter.limit("30/minute")(profiles.profile_card_by_id)
rate_limited_profile_settings = limiter.limit("20/minute")(profiles.update_profile_settings)
for route in profiles.router.routes:
    if not hasattr(route, "path") or not hasattr(route, "methods"):
        continue
    if route.path == "/u/{handle}/card.png":
        bind_rate_limited_endpoint(route, rate_limited_profile_card)
    elif route.path == "/u/id/{user_id:database_id}/card.png":
        bind_rate_limited_endpoint(route, rate_limited_profile_card_by_id)
    elif route.path == "/api/profile/settings" and "PUT" in route.methods:
        bind_rate_limited_endpoint(route, rate_limited_profile_settings)
app.include_router(profiles.router)

from .routers import profile_widgets as profile_widgets_router
# Widgets are embedded on other sites and fetched through their image proxies, so allow more.
rate_limited_widget = limiter.limit("120/minute")(profile_widgets_router.widget)
rate_limited_widget_by_id = limiter.limit("120/minute")(profile_widgets_router.widget_by_id)
for route in profile_widgets_router.router.routes:
    if getattr(route, "path", None) == "/u/{handle}/widget/{kind}.png":
        bind_rate_limited_endpoint(route, rate_limited_widget)
    elif getattr(route, "path", None) == "/u/id/{user_id:database_id}/widget/{kind}.png":
        bind_rate_limited_endpoint(route, rate_limited_widget_by_id)
app.include_router(profile_widgets_router.router)
app.include_router(pwa.router)
rate_limited_kofi_webhook = limiter.limit("60/minute")(supporters.kofi_webhook)
for route in supporters.router.routes:
    if getattr(route, "path", None) == "/api/kofi/webhook" and "POST" in getattr(route, "methods", set()):
        bind_rate_limited_endpoint(route, rate_limited_kofi_webhook)
    # Each claim can send an email to an address the member typed.
    elif getattr(route, "path", None) == "/api/supporter/claim" and "POST" in getattr(route, "methods", set()):
        bind_rate_limited_endpoint(route, limiter.limit("6/hour")(route.endpoint))
app.include_router(supporters.router)

rate_limited_recap_card = limiter.limit("30/minute")(year_in_review.shared_card)
rate_limited_own_recap_card = limiter.limit("30/minute")(year_in_review.own_card)
rate_limited_recap_share = limiter.limit("20/minute")(year_in_review.share_recap)
rate_limited_recap_story = limiter.limit("30/minute")(year_in_review.shared_story)
rate_limited_own_recap_story = limiter.limit("30/minute")(year_in_review.own_story)
for route in year_in_review.router.routes:
    path, methods = getattr(route, "path", None), getattr(route, "methods", set())
    if path == "/recap/{token}/card.png":
        bind_rate_limited_endpoint(route, rate_limited_recap_card)
    elif path == "/api/year-in-review/{year}/card.png":
        bind_rate_limited_endpoint(route, rate_limited_own_recap_card)
    elif path == "/recap/{token}/story.png":
        bind_rate_limited_endpoint(route, rate_limited_recap_story)
    elif path == "/api/year-in-review/{year}/story.png":
        bind_rate_limited_endpoint(route, rate_limited_own_recap_story)
    elif path == "/api/year-in-review/{year}/share" and "PUT" in methods:
        bind_rate_limited_endpoint(route, rate_limited_recap_share)
app.include_router(year_in_review.router)

from .routers import invites
rate_limited_invite_link = limiter.limit("20/minute")(invites.invite_link)
rate_limited_invite_accept = limiter.limit("20/minute")(invites.accept_invite)
rate_limited_join_page = limiter.limit("60/minute")(invites.join_page)
for route in invites.router.routes:
    path = getattr(route, "path", None)
    if path == "/api/friends/invite-link":
        bind_rate_limited_endpoint(route, rate_limited_invite_link)
    elif path == "/api/friends/invite/{token}/accept":
        bind_rate_limited_endpoint(route, rate_limited_invite_accept)
    elif path == "/join/{token}":
        bind_rate_limited_endpoint(route, rate_limited_join_page)
app.include_router(invites.router)

from .routers import goals as goals_router
rate_limited_goal_save = limiter.limit("30/minute")(goals_router.save_goal)
rate_limited_goal_delete = limiter.limit("30/minute")(goals_router.delete_goal)
rate_limited_goal_share = limiter.limit("20/minute")(goals_router.share_goal)
rate_limited_goal_page = limiter.limit("60/minute")(goals_router.shared_goal_page)
rate_limited_goal_card = limiter.limit("30/minute")(goals_router.shared_goal_card)
for route in goals_router.router.routes:
    path, methods = getattr(route, "path", None), getattr(route, "methods", set())
    if path == "/api/goals/{year}/{category}" and "PUT" in methods:
        bind_rate_limited_endpoint(route, rate_limited_goal_save)
    elif path == "/api/goals/{year}/{category}" and "DELETE" in methods:
        bind_rate_limited_endpoint(route, rate_limited_goal_delete)
    elif path == "/api/goals/{year}/{category}/share" and "PUT" in methods:
        bind_rate_limited_endpoint(route, rate_limited_goal_share)
    elif path == "/goal/{token}":
        bind_rate_limited_endpoint(route, rate_limited_goal_page)
    elif path == "/goal/{token}/card.png":
        bind_rate_limited_endpoint(route, rate_limited_goal_card)
app.include_router(goals_router.router)

from .routers import challenges as challenges_router
rate_limited_challenge_join = limiter.limit("30/minute")(challenges_router.join_challenge)
rate_limited_challenge_leave = limiter.limit("30/minute")(challenges_router.leave_challenge)
rate_limited_challenge_share = limiter.limit("20/minute")(challenges_router.share_challenge)
rate_limited_challenge_page = limiter.limit("60/minute")(challenges_router.shared_challenge_page)
rate_limited_challenge_card = limiter.limit("30/minute")(challenges_router.shared_challenge_card)
for route in challenges_router.router.routes:
    path, methods = getattr(route, "path", None), getattr(route, "methods", set())
    if path == "/api/challenge/join" and "POST" in methods:
        bind_rate_limited_endpoint(route, rate_limited_challenge_join)
    elif path == "/api/challenge/join" and "DELETE" in methods:
        bind_rate_limited_endpoint(route, rate_limited_challenge_leave)
    elif path == "/api/challenge/share" and "PUT" in methods:
        bind_rate_limited_endpoint(route, rate_limited_challenge_share)
    elif path == "/challenge/{token}":
        bind_rate_limited_endpoint(route, rate_limited_challenge_page)
    elif path == "/challenge/{token}/card.png":
        bind_rate_limited_endpoint(route, rate_limited_challenge_card)
app.include_router(challenges_router.router)

from .routers import badges as badges_router
rate_limited_badges_list = limiter.limit("120/minute")(badges_router.list_badges)
rate_limited_badges_seen = limiter.limit("30/minute")(badges_router.badges_seen)
for route in badges_router.router.routes:
    path, methods = getattr(route, "path", None), getattr(route, "methods", set())
    if path == "/api/badges" and "GET" in methods:
        bind_rate_limited_endpoint(route, rate_limited_badges_list)
    elif path == "/api/badges/seen" and "POST" in methods:
        bind_rate_limited_endpoint(route, rate_limited_badges_seen)
app.include_router(badges_router.router)

from .routers import pick as pick_router
rate_limited_pick_add = limiter.limit("30/minute")(pick_router.add_pick)
rate_limited_pick_pool = limiter.limit("60/minute")(pick_router.pick_pool)
for route in pick_router.router.routes:
    if getattr(route, "path", None) == "/api/pick/add":
        bind_rate_limited_endpoint(route, rate_limited_pick_add)
    elif getattr(route, "path", None) == "/api/pick/pool":
        bind_rate_limited_endpoint(route, rate_limited_pick_pool)
app.include_router(pick_router.router)

from .routers import taste_quiz as taste_quiz_router
rate_limited_quiz_art = limiter.limit("60/minute")(taste_quiz_router.taste_quiz_art)
rate_limited_quiz_suggestions = limiter.limit("20/minute")(taste_quiz_router.taste_quiz_suggestions)
rate_limited_quiz_save = limiter.limit("10/minute")(taste_quiz_router.taste_quiz_save)
for route in taste_quiz_router.router.routes:
    path = getattr(route, "path", None)
    if path == "/api/taste-quiz/art/{kind}/{slug}":
        bind_rate_limited_endpoint(route, rate_limited_quiz_art)
    elif path == "/api/taste-quiz/suggestions":
        bind_rate_limited_endpoint(route, rate_limited_quiz_suggestions)
    elif path == "/api/taste-quiz/save":
        bind_rate_limited_endpoint(route, rate_limited_quiz_save)
app.include_router(taste_quiz_router.router)

from .routers import start as start_router
rate_limited_start_save = limiter.limit("90/minute")(start_router.start_save)
rate_limited_start_art = limiter.limit("60/minute")(start_router.start_art)
rate_limited_start_undo = limiter.limit("30/minute")(start_router.start_undo)
for route in start_router.router.routes:
    path = getattr(route, "path", None)
    if path == "/api/start/save":
        bind_rate_limited_endpoint(route, rate_limited_start_save)
    elif path == "/api/start/art/{kind}/{slug}":
        bind_rate_limited_endpoint(route, rate_limited_start_art)
    elif path == "/api/start/undo":
        bind_rate_limited_endpoint(route, rate_limited_start_undo)
app.include_router(start_router.router)

from .routers import if_you_liked as if_you_liked_router
app.include_router(if_you_liked_router.router)

from .routers import best_of as best_of_router
app.include_router(best_of_router.router)

from .routers import tonight as tonight_router
rate_limited_tonight_create = limiter.limit("10/minute")(tonight_router.create_poll)
rate_limited_tonight_vote = limiter.limit("30/minute")(tonight_router.vote_poll)
for route in tonight_router.router.routes:
    path, methods = getattr(route, "path", None), getattr(route, "methods", set()) or set()
    if path == "/api/tonight" and "POST" in methods:
        bind_rate_limited_endpoint(route, rate_limited_tonight_create)
    elif path == "/api/tonight/{token}/vote" and "PUT" in methods:
        bind_rate_limited_endpoint(route, rate_limited_tonight_vote)
app.include_router(tonight_router.router)

from .routers import weekly_roundup as weekly_roundup_router
app.include_router(weekly_roundup_router.router)

from .routers import in_order as in_order_router
rate_limited_order_progress = limiter.limit("60/minute")(in_order_router.in_order_progress)
rate_limited_order_add = limiter.limit("30/minute")(in_order_router.in_order_add)
for route in in_order_router.router.routes:
    path = getattr(route, "path", None)
    if path == "/api/in-order/{slug}/progress":
        bind_rate_limited_endpoint(route, rate_limited_order_progress)
    elif path == "/api/in-order/{slug}/add":
        bind_rate_limited_endpoint(route, rate_limited_order_add)
app.include_router(in_order_router.router)

from .routers import seasonal as seasonal_router
rate_limited_seasonal_progress = limiter.limit("60/minute")(seasonal_router.seasonal_progress)
rate_limited_seasonal_add = limiter.limit("30/minute")(seasonal_router.seasonal_add)
for route in seasonal_router.router.routes:
    path = getattr(route, "path", None)
    if path == "/api/seasonal/{slug}/progress":
        bind_rate_limited_endpoint(route, rate_limited_seasonal_progress)
    elif path == "/api/seasonal/{slug}/add":
        bind_rate_limited_endpoint(route, rate_limited_seasonal_add)
app.include_router(seasonal_router.router)

from .routers import tier_list as tier_list_router
rate_limited_tier_templates = limiter.limit("60/minute")(tier_list_router.tier_list_templates)
rate_limited_tier_library = limiter.limit("30/minute")(tier_list_router.tier_list_library)
rate_limited_tier_image = limiter.limit("240/minute")(tier_list_router.tier_list_image)
for route in tier_list_router.router.routes:
    path = getattr(route, "path", None)
    if path == "/api/tier-list/templates":
        bind_rate_limited_endpoint(route, rate_limited_tier_templates)
    elif path == "/api/tier-list/library":
        bind_rate_limited_endpoint(route, rate_limited_tier_library)
    elif path == "/api/tier-list/image":
        bind_rate_limited_endpoint(route, rate_limited_tier_image)
app.include_router(tier_list_router.router)

from .routers import daily as daily_router
rate_limited_daily_guess = limiter.limit("120/minute")(daily_router.daily_guess)
rate_limited_daily_add = limiter.limit("30/minute")(daily_router.daily_add)
for route in daily_router.router.routes:
    path = getattr(route, "path", None)
    if path == "/api/daily/{number}/guess":
        bind_rate_limited_endpoint(route, rate_limited_daily_guess)
    elif path == "/api/daily/add":
        bind_rate_limited_endpoint(route, rate_limited_daily_add)
app.include_router(daily_router.router)

from .routers import calendar as calendar_router
rate_limited_calendar_all = limiter.limit("60/minute")(calendar_router.release_radar_calendar)
rate_limited_calendar_section = limiter.limit("60/minute")(calendar_router.release_radar_section_calendar)
rate_limited_calendar_member = limiter.limit("30/minute")(calendar_router.member_calendar)
for route in calendar_router.router.routes:
    path = getattr(route, "path", None)
    if path == "/calendar/release-radar.ics":
        bind_rate_limited_endpoint(route, rate_limited_calendar_all)
    elif path == "/calendar/release-radar/{feed}.ics":
        bind_rate_limited_endpoint(route, rate_limited_calendar_section)
    elif path == "/calendar/u/feed-{token}.ics":
        bind_rate_limited_endpoint(route, rate_limited_calendar_member)
app.include_router(calendar_router.router)

from .routers import taste_match as taste_match_router
rate_limited_taste_overview = limiter.limit("30/minute")(taste_match_router.friends_overview)
rate_limited_taste_match = limiter.limit("60/minute")(taste_match_router.friend_match)
rate_limited_taste_add = limiter.limit("30/minute")(taste_match_router.add_friend_pick)
for route in taste_match_router.router.routes:
    path = getattr(route, "path", None)
    if path == "/api/taste-match/friends":
        bind_rate_limited_endpoint(route, rate_limited_taste_overview)
    elif path == "/api/taste-match/friends/{friend_id}":
        bind_rate_limited_endpoint(route, rate_limited_taste_match)
    elif path == "/api/taste-match/friends/{friend_id}/add":
        bind_rate_limited_endpoint(route, rate_limited_taste_add)
app.include_router(taste_match_router.router)

from .routers import taste_compare as taste_compare_router
# The page and card are opened from shared links, so they get the same room as profile pages.
TASTE_COMPARE_LIMITS = {
    "/u/{handle}/match": "60/minute",
    "/u/id/{user_id:database_id}/match": "60/minute",
    "/u/{handle}/match/card.png": "60/minute",
    "/u/id/{user_id:database_id}/match/card.png": "60/minute",
    "/api/taste-match/u/{owner_id}/guess": "20/minute",
    "/api/taste-match/u/{owner_id}": "30/minute",
    "/api/taste-match/u/{owner_id}/answers": "10/minute",
}
for route in taste_compare_router.router.routes:
    limit = TASTE_COMPARE_LIMITS.get(getattr(route, "path", None))
    if limit:
        bind_rate_limited_endpoint(route, limiter.limit(limit)(route.endpoint))
app.include_router(taste_compare_router.router)

from .routers import shared_lists as shared_lists_router
rate_limited_list_create = limiter.limit("20/hour")(shared_lists_router.create_list)
rate_limited_list_join = limiter.limit("30/minute")(shared_lists_router.join_list)
rate_limited_list_item = limiter.limit("60/minute")(shared_lists_router.add_item)
rate_limited_list_member = limiter.limit("30/minute")(shared_lists_router.add_member)
for route in shared_lists_router.router.routes:
    path, methods = getattr(route, "path", None), getattr(route, "methods", set())
    if path == "/api/lists" and "POST" in methods:
        bind_rate_limited_endpoint(route, rate_limited_list_create)
    elif path == "/api/lists/join/{token}":
        bind_rate_limited_endpoint(route, rate_limited_list_join)
    elif path == "/api/lists/{list_id}/items" and "POST" in methods:
        bind_rate_limited_endpoint(route, rate_limited_list_item)
    elif path == "/api/lists/{list_id}/members" and "POST" in methods:
        bind_rate_limited_endpoint(route, rate_limited_list_member)
app.include_router(shared_lists_router.router)

from .routers import clubs as clubs_router
rate_limited_club_start = limiter.limit("20/hour")(clubs_router.start_pick)
rate_limited_club_post = limiter.limit("30/minute")(clubs_router.add_post)
for route in clubs_router.router.routes:
    path, methods = getattr(route, "path", None), getattr(route, "methods", set())
    if path == "/api/lists/{list_id}/club" and "POST" in methods:
        bind_rate_limited_endpoint(route, rate_limited_club_start)
    elif path == "/api/lists/{list_id}/club/{round_id}/posts" and "POST" in methods:
        bind_rate_limited_endpoint(route, rate_limited_club_post)
app.include_router(clubs_router.router)

from .routers import friend_recs as friend_recs_router
rate_limited_rec_send = limiter.limit("30/hour")(friend_recs_router.send_recommendation)
rate_limited_rec_link = limiter.limit("30/hour")(friend_recs_router.share_link)
rate_limited_rec_claim = limiter.limit("30/hour")(friend_recs_router.claim_link)
rate_limited_rec_page = limiter.limit("60/minute")(friend_recs_router.link_page)
for route in friend_recs_router.router.routes:
    path, methods = getattr(route, "path", None), getattr(route, "methods", set())
    if path == "/api/friend-recs" and "POST" in methods:
        bind_rate_limited_endpoint(route, rate_limited_rec_send)
    elif path == "/api/friend-recs/link":
        bind_rate_limited_endpoint(route, rate_limited_rec_link)
    elif path == "/api/friend-recs/claim/{token}":
        bind_rate_limited_endpoint(route, rate_limited_rec_claim)
    elif path == "/r/{token}":
        bind_rate_limited_endpoint(route, rate_limited_rec_page)
app.include_router(friend_recs_router.router)

from .routers import friend_feed as friend_feed_router
rate_limited_feed_cheer = limiter.limit("120/hour")(friend_feed_router.cheer)
rate_limited_feed_save = limiter.limit("60/hour")(friend_feed_router.save)
for route in friend_feed_router.router.routes:
    path, methods = getattr(route, "path", None), getattr(route, "methods", set())
    if path == "/api/friend-feed/cheer":
        bind_rate_limited_endpoint(route, rate_limited_feed_cheer)
    elif path == "/api/friend-feed/save":
        bind_rate_limited_endpoint(route, rate_limited_feed_save)
app.include_router(friend_feed_router.router)

from .routers import follows as follows_router
rate_limited_follow = limiter.limit("30/minute")(follows_router.follow)
rate_limited_unfollow = limiter.limit("30/minute")(follows_router.unfollow)
rate_limited_remove_follower = limiter.limit("30/minute")(follows_router.remove_follower)
for route in follows_router.router.routes:
    path, methods = getattr(route, "path", None), getattr(route, "methods", set())
    if path == "/api/follows/{user_id:database_id}" and "POST" in methods:
        bind_rate_limited_endpoint(route, rate_limited_follow)
    elif path == "/api/follows/{user_id:database_id}" and "DELETE" in methods:
        bind_rate_limited_endpoint(route, rate_limited_unfollow)
    elif path == "/api/follows/followers/{user_id:database_id}":
        bind_rate_limited_endpoint(route, rate_limited_remove_follower)
app.include_router(follows_router.router)

from .routers import binge_calculator as binge_calculator_router
rate_limited_binge_length = limiter.limit("60/minute")(binge_calculator_router.binge_length)
for route in binge_calculator_router.router.routes:
    if getattr(route, "path", None) == "/api/binge-calculator/length":
        bind_rate_limited_endpoint(route, rate_limited_binge_length)
app.include_router(binge_calculator_router.router)


@app.get("/", tags=["root"])
@app.head("/", tags=["root"])
async def read_root(request: Request):
    html_file = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as file:
            html = apply_app_chrome(file.read())
            authenticated_shell = bool(request.cookies.get(AUTH_COOKIE_NAME))
            if (authenticated_shell and request.method == "GET" and not request.query_params
                    and request.cookies.get(start_flow.COOKIE) == "1"):
                # A new account's first visit: the start page, once (it clears the cookie).
                return RedirectResponse("/start", status_code=303)
            if not authenticated_shell:
                await run_in_threadpool(_warm_homepage_sections)
                html = public_root_html(html, request)
                if request.method == "GET" and "token" not in request.query_params:
                    funnel.record("landing_viewed", request)
            else:
                _, dashboard_version = dashboard_assets.bundle()
                html = html.replace('src="./app.js"', f'src="./app.js?v={dashboard_version}"', 1)
                # Signed-in pages show the Friends button; drawing it from the start keeps
                # the toolbar from re-wrapping (and the page from shifting) once scripts run.
                html = html.replace('aria-controls="friendsSidebar" hidden>', 'aria-controls="friendsSidebar">', 1)
            response = nonce_html_response(html)
            response.headers["Cache-Control"] = "private, no-store" if authenticated_shell else "no-cache"
            response.headers["Vary"] = "Cookie"
            return response
    return {"message": "OmniTrackr API is running 🚀"}


@app.get("/recommend/{token}", tags=["public"])
async def recommendation_postcard_page(request: Request, token: str):
    """Serve an unindexed guest response page; the token is read by client JS."""
    response = strict_template_response("recommendation_postcard.html", request)
    if response:
        response.headers["Cache-Control"] = "no-store"
        return response
    raise HTTPException(status_code=404, detail="Recommendation Postcard page not found")


# Privacy Policy endpoint
@app.get("/privacy", tags=["public"])
async def privacy_policy(request: Request):
    """Serve the privacy policy page."""
    response = strict_template_response("privacy.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Privacy policy not found")


@app.get("/advertising", tags=["public"])
async def advertising_page(request: Request):
    response = strict_template_response("advertising.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/content-quality", tags=["public"])
async def content_quality_page(request: Request):
    response = strict_template_response("content_quality.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/site-map", tags=["public"])
async def site_map_page(request: Request):
    from . import editorial_index
    response = strict_template_response("site_map.html", request,
                                        {"<!--GUIDE_DIRECTORY-->": editorial_index.directory_html()})
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/about", tags=["public"])
async def about_page(request: Request):
    response = strict_template_response("about.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/faq", tags=["public"])
async def faq_page(request: Request):
    response = strict_template_response("faq.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/guides", tags=["public"])
async def guides_page(request: Request):
    response = strict_template_response("guides.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/compare", tags=["public"])
async def compare_page(request: Request):
    response = strict_template_response("compare.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/use-cases", tags=["public"])
async def use_cases_page(request: Request):
    response = strict_template_response("use_cases.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/changelog", tags=["public"])
async def changelog_page(request: Request):
    response = strict_template_response("changelog.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/tv-show-tracker", tags=["public"])
async def tv_show_tracker_page(request: Request):
    response = strict_template_response("tv_show_tracker.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/game-tracker", tags=["public"])
async def game_tracker_page(request: Request):
    response = strict_template_response("game_tracker.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/movie-tracker", tags=["public"])
async def movie_tracker_page(request: Request):
    response = strict_template_response("movie_tracker.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/anime-tracker", tags=["public"])
async def anime_tracker_page(request: Request):
    response = strict_template_response("anime_tracker.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/book-tracker", tags=["public"])
async def book_tracker_page(request: Request):
    response = strict_template_response("book_tracker.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/manga-tracker", tags=["public"])
async def manga_tracker_page(request: Request):
    response = strict_template_response("manga_tracker.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/podcast-tracker", tags=["public"])
async def podcast_tracker_page(request: Request):
    response = strict_template_response("podcast_tracker.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/audiobook-tracker", tags=["public"])
async def audiobook_tracker_page(request: Request):
    response = strict_template_response("audiobook_tracker.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/music-tracker", tags=["public"])
async def music_tracker_page(request: Request):
    response = strict_template_response("music_tracker.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/media-statistics", tags=["public"])
async def media_statistics_page(request: Request):
    response = strict_template_response("media_statistics.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/export-import-guide", tags=["public"])
async def export_import_guide_page(request: Request):
    response = strict_template_response("export_import_guide.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/switch", tags=["public"])
async def switch_page(request: Request):
    response = strict_template_response("switch.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/media-tracker-checklist", tags=["public"])
async def media_tracker_checklist_page(request: Request):
    response = strict_template_response("media_tracker_checklist.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/tracking-templates", tags=["public"])
async def tracking_templates_page(request: Request):
    response = strict_template_response("tracking_templates.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/review-guidelines", tags=["public"])
async def review_guidelines_page(request: Request):
    response = strict_template_response("review_guidelines.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/sample-library", tags=["public"])
async def sample_library_page(request: Request):
    response = strict_template_response("sample_library.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/demo", tags=["public"])
async def demo_page(request: Request):
    response = strict_template_response("demo.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/media-tracking", tags=["public"])
async def media_tracking_page(request: Request):
    response = strict_template_response("media_tracking.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/roadmap", tags=["public"])
async def roadmap_page(request: Request):
    response = strict_template_response("roadmap.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/terms", tags=["public"])
async def terms_page(request: Request):
    response = strict_template_response("terms.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/contact", tags=["public"])
async def contact_page(request: Request):
    response = strict_template_response("contact.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/supporters", tags=["public"])
def supporters_page(request: Request, db: Session = Depends(get_db)):
    response = strict_template_response("supporters.html", request, replacements=supporters.page_sections(db))
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


# Public endpoint for user count
@app.get("/api/user-count", response_model=schemas.UserCount, tags=["public"])
@limiter.limit("30/minute")  # Rate limit: 30 requests per minute per IP
def get_user_count(request: Request, db: Session = Depends(get_db)):
    """Get total number of active user accounts. Public endpoint for landing page."""
    try:
        count = db.query(models.User).filter(models.User.is_active == True).count()
        return schemas.UserCount(count=count)
    except Exception:
        # Graceful degradation: return 0 on error rather than exposing errors
        return schemas.UserCount(count=0)


# Auto-browser opening functionality
def open_browser():
    """Open the default web browser to the OmniTrackr UI"""
    import webbrowser
    import time
    import threading

    def delayed_open():
        time.sleep(2)  # Wait 2 seconds for server to start
        webbrowser.open("http://127.0.0.1:8000")

    # Start browser opening in a separate thread
    browser_thread = threading.Thread(target=delayed_open, daemon=True)
    browser_thread.start()


if __name__ == "__main__":
    import uvicorn

    open_browser()
    uvicorn.run(app, host="127.0.0.1", port=8000)
