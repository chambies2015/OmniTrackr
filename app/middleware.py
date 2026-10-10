"""
Middleware for the OmniTrackr API.
Contains security headers and bot filtering middleware.
"""
import re
import os
from contextlib import contextmanager
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response as StarletteResponse

from .csp import build_csp


NOINDEX_PATHS = {"/docs", "/redoc", "/openapi.json"}
NOINDEX_PREFIXES = (
    "/account/",
    "/activity/",
    "/anime/",
    "/api/",
    "/auth/",
    "/books/",
    "/custom-tab-posters/",
    "/custom-tabs/",
    "/docs/",
    "/export/",
    "/friends",
    "/import/",
    "/import-studio/",
    "/library/",
    "/movies/",
    "/music/",
    "/notifications/",
    "/profile-pictures/",
    "/progress/",
    "/recap/",
    "/recommend/",
    "/recommendations/",
    "/static/profile_pictures/",
    "/statistics/",
    "/tv-shows/",
    "/video-games/",
    "/year-in-review",
)
PUBLIC_WELL_KNOWN_PATHS = {"/.well-known/ai.txt"}
PUBLIC_PROFILE_PATH = re.compile(r"^/u/(?:[A-Za-z0-9_-][A-Za-z0-9_.-]{0,49}|id/\d{1,10})(?:/card\.png)?/?$")
# Shared Year in Review links carry a random token that could contain a scanned word.
PUBLIC_RECAP_PATH = re.compile(r"^/recap/[A-Za-z0-9_-]{8,32}(?:/card\.png)?/?$")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        
        if "Content-Security-Policy" not in response.headers:
            response.headers["Content-Security-Policy"] = build_csp()
        
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        if request.url.path.startswith("/auth/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        if request.url.path.startswith((
            "/account/",
            "/activity/",
            "/anime/",
            "/books/",
            "/custom-tab-posters/",
            "/custom-tabs/",
            "/export/",
            "/friends",
            "/import/",
            "/import-studio/",
            "/library/",
            "/movies/",
            "/music/",
            "/next-up/",
            "/progress/",
            "/notifications",
            "/recommend/",
            "/recommendations/",
            "/statistics/",
            "/tv-shows/",
            "/video-games/",
        )):
            response.headers["Cache-Control"] = "private, no-store"

        review_path = request.url.path.rstrip("/")
        review_save_api = review_path.startswith("/api/public/reviews/") and review_path.endswith(("/save-preview", "/save"))
        review_save_page = review_path.startswith("/reviews/") and review_path.endswith("/save")
        collection_save = review_path.startswith("/collections/public/") and review_path.endswith(("/save-preview", "/save", "/copy"))
        if review_save_api or review_save_page or collection_save:
            # Include authentication and validation failures before a route runs.
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["X-Robots-Tag"] = "noindex, follow"

        path = request.url.path
        if (path.startswith("/static/") and not path.startswith("/static/profile_pictures/")
                and response.status_code == 200 and "cache-control" not in response.headers):
            # Versioned assets (?v=...) never change, so browsers can keep them for a year;
            # unversioned ones are rechecked daily.
            # Font files are never edited in place (a new cut gets a new file name).
            versioned = "v=" in request.url.query or path.startswith("/static/fonts/")
            response.headers["Cache-Control"] = (
                "public, max-age=31536000, immutable" if versioned else "public, max-age=86400"
            )

        if request.url.path in NOINDEX_PATHS or request.url.path.startswith(NOINDEX_PREFIXES):
            response.headers["X-Robots-Tag"] = "noindex, nofollow"

        return response


class BotFilterMiddleware(BaseHTTPMiddleware):
    """Filter out obvious bot/scanner requests."""
    
    # Suspicious paths that bots commonly scan
    SUSPICIOUS_PATHS = [
        "/.env", "/.env.bak", "/.env.backup", "/.env.local",
        "/.git", "/.git/config", "/.git/logs/HEAD",
        "/wp-admin", "/wp-login.php", "/wp-config.php", "/setup-config.php",
        "/wp-includes", "/wp-content", "/xmlrpc.php", "/wlwmanifest.xml",
        "/wordpress/wp-admin/setup-config.php", "/2020/", "/2021/",
        "/admin", "/administrator", "/phpmyadmin",
        "/.aws", "/aws-config.js", "/aws.config.js",
        "/config.json", "/config.js", "/.gitlab-ci.yml",
        "/backend/.env", "/core/.env", "/api/.env",
        "/.htaccess", "/web.config", "/.well-known",
        # WordPress common directory paths
        "/blog/", "/web/", "/wordpress/", "/website/", "/wp/", "/news/",
        "/2018/", "/2019/", "/shop/", "/wp1/", "/test/", "/media/",
        "/wp2/", "/site/", "/cms/", "/sito/",
        # API gateway and config file scanners
        "/api_gateway/", "/apis/", "/app-config", "/app.config",
        "/app.py", "/app.toml", "/app.yaml", "/app.yml", "/app/.secrets",
        "/app/config/", "/app/models/", "/app/sign.go",
        "/application.ini", "/application/config/", "/application/configs/",
        "/application/libraries/", "/appveyor.yml",
        "/aws-example", "/aws-lambda", "/aws-notifications", "/aws-nuke",
        "/aws-s3", "/aws-wrapper", "/aws.config", "/aws.ino", "/aws.md",
        "/aws.properties", "/aws.service", "/aws.show", "/aws/",
        "/awsApp", "/awsKEY", "/awsS3", "/aws_config", "/aws_cred",
        "/aws_credentials", "/aws_ec2", "/awsconfig", "/aws.yml",
        # Backend paths
        "/backend/app.js", "/backend/aws/", "/backend/config/",
        "/backend/constant", "/backend/controller", "/backend/helper",
        "/backend/index.js", "/backend/mail.js", "/backend/mailer.js",
        "/backend/mailserver.js", "/backend/node/", "/backend/server.js",
        "/backend/utils.js",
        # Config file scanners
        "/base.yaml", "/be/config.js", "/circle.yml", "/compose.yaml",
        "/conf.yaml", "/config.rb", "/config.ts", "/config.yaml", "/config.yml",
        "/config/app.js", "/config/common.js", "/config/config.exs",
        "/config/config.go", "/config/config.ino", "/config/constant.js",
        "/config/constants.js", "/config/controller.js", "/config/dev/",
        "/config/index.js", "/config/mail.js", "/config/mailer.js",
        "/config/mailserver.js", "/config/model.properties", "/config/server.js",
        "/config/sitemap.rb", "/config/storage.yml", "/config/template.js",
        "/config/utils.js", "/configs/",
        # Development/staging/production paths
        "/dev/app.js", "/dev/config.js", "/dev/config/", "/dev/constant.js",
        "/dev/constants.js", "/dev/controller.js", "/dev/helper.js",
        "/dev/index.js", "/dev/mail.js", "/dev/mailer.js", "/dev/mailserver.js",
        "/dev/server.js", "/dev/utils.js",
        "/staging/config.js", "/staging/config/", "/staging/index.js",
        "/prod/config.js", "/qa/config.js",
        # Server paths
        "/server/app.js", "/server/config.js", "/server/config/",
        "/server/configs/", "/server/constant.js", "/server/constants.js",
        "/server/controller.js", "/server/helper.js", "/server/helper/",
        "/server/index.js", "/server/mail.js", "/server/mailer.js",
        "/server/mailserver.js", "/server/main.go", "/server/server.js",
        "/server/src/", "/server/utils.js",
        # Source paths
        "/src/FileUpload.js", "/src/Utils/", "/src/app.js", "/src/app/services/",
        "/src/aws.ts", "/src/config.ts", "/src/config/", "/src/constant.js",
        "/src/constants.js", "/src/constants.ts", "/src/controller.js",
        "/src/helper.js", "/src/helpers/", "/src/index.js", "/src/lib/",
        "/src/libs/", "/src/mail.js", "/src/mailer.js", "/src/mailserver.js",
        "/src/main.py", "/src/main.rb", "/src/s3.ts", "/src/server.js",
        "/src/src.js", "/src/utils.js",
        # Web paths
        "/web/app.js", "/web/config/", "/web/constant.js", "/web/constants.js",
        "/web/controller.js", "/web/helper.js", "/web/index.js", "/web/mail.js",
        "/web/mailer.js", "/web/mailserver.js", "/web/server.js", "/web/utils.js",
        "/web/web.js", "/website/index.js",
        # Helper/utils paths
        "/helper.js", "/helper/", "/helpers/", "/utils.js", "/utils/",
        # Mail paths
        "/mail.js", "/mailer.js", "/mailserver.js",
        # Common config files
        "/constant.js", "/constants.ini", "/constants.js", "/constants.json",
        "/constants.ts", "/constants.yml", "/controller.js", "/index.js",
        "/index.md", "/index.ts", "/main.go", "/readme.md", "/server.js",
        # Other paths
        "/cron/", "/default.ts", "/elb.rb", "/libs/", "/minio.md",
        "/model/", "/partner/", "/providers/", "/recipes/", "/scripts/",
        "/shared/", "/user/",
        # CI/CD and hidden files
        "/.remote", "/.local", "/.production", "/.aws-secrets",
        "/.cirrus.yml", "/.drone.yml", "/.git-secrets", "/.jaynes.yml",
        "/.lakectl.yaml", "/.properties", "/.sync.yml", "/.travis.old.yml",
        "/.travis.yml", "/.docker/",
        # Connect paths
        "/connect/",
    ]
    
    # Suspicious user agents (common scanners)
    SUSPICIOUS_AGENTS = [
        "sqlmap", "nikto", "nmap", "masscan", "zap",
        "acunetix", "nessus", "openvas", "w3af",
        "dirbuster", "gobuster", "dirb", "wfuzz",
    ]
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path.lower()
        user_agent = request.headers.get("user-agent", "").lower()
        client_ip = request.client.host if request.client else "unknown"
        
        normalized_path = path.replace("//", "/")
        
        blocked = False
        reason = ""
        
        if path in PUBLIC_WELL_KNOWN_PATHS:
            return await call_next(request)
        if PUBLIC_PROFILE_PATH.match(request.url.path) or PUBLIC_RECAP_PATH.match(request.url.path):
            # /u/<username> pages: a username such as "admin_fan" would otherwise
            # trip the substring scan. The route validates the name itself.
            return await call_next(request)

        if any(suspicious in path for suspicious in self.SUSPICIOUS_PATHS) or \
           any(suspicious in normalized_path for suspicious in self.SUSPICIOUS_PATHS):
            blocked = True
            reason = "suspicious_path"
        
        if "//" in path and ("wp-includes" in path or "wp-admin" in path or "xmlrpc.php" in path):
            blocked = True
            reason = "wordpress_scan"
        
        if any(agent in user_agent for agent in self.SUSPICIOUS_AGENTS):
            if any(suspicious in path for suspicious in self.SUSPICIOUS_PATHS):
                blocked = True
                reason = "suspicious_agent_and_path"
        
        if blocked:
            print(f"SECURITY: Bot request blocked - IP: {client_ip}, Path: {path}, User-Agent: {user_agent[:100]}, Reason: {reason}")
            return StarletteResponse(
                content="Not Found",
                status_code=404,
                headers={"X-Robots-Tag": "noindex, nofollow"}
            )
        
        return await call_next(request)



def _browser_origin(value: str, *, referer: bool = False) -> str | None:
    """Normalize an HTTP(S) origin without trusting forwarded headers."""
    try:
        if any(char.isspace() for char in value) or "\\" in value:
            return None
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username is not None or parts.password is not None:
            return None
        if not referer and (parts.path not in ("", "/") or parts.query or parts.fragment):
            return None
        host = parts.hostname.lower()
        if ":" in host:
            host = f"[{host}]"
        port = parts.port
        suffix = f":{port}" if port is not None and port != (443 if parts.scheme == "https" else 80) else ""
        return f"{parts.scheme}://{host}{suffix}"
    except (ValueError, TypeError):
        return None


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """Reject browser writes from untrusted sites; native API clients still work."""
    async def dispatch(self, request: Request, call_next):
        if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
            return await call_next(request)
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        trusted = {_browser_origin(str(request.base_url))}
        for configured in os.getenv("ALLOWED_ORIGINS", "").split(","):
            normalized = _browser_origin(configured.strip())
            if normalized:
                trusted.add(normalized)
        trusted.discard(None)
        if origin is not None:
            allow_local_file = (origin == "null"
                                and os.getenv("ENVIRONMENT", "development").lower() != "production"
                                and os.getenv("ALLOW_NULL_ORIGIN", "").lower() == "true")
            allowed = allow_local_file or _browser_origin(origin) in trusted
        elif referer is not None:
            allowed = _browser_origin(referer, referer=True) in trusted
        else:
            allowed = request.headers.get("sec-fetch-site", "").lower() != "cross-site"
        if not allowed:
            return StarletteResponse('{"detail":"Cross-site request rejected"}', status_code=403, media_type="application/json")
        return await call_next(request)


def _protected_upload_path(path: str) -> bool:
    path = path.rstrip("/")
    return (path in {"/account/profile-picture", "/import/file", "/import-studio/preview", "/import-studio/apply"}
            or re.fullmatch(r"/custom-tabs/[^/]+/items/[^/]+/poster", path) is not None)


class UploadAuthenticationMiddleware:
    """Authenticate file uploads before FastAPI starts its multipart parser."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or not _protected_upload_path(scope["path"]):
            return await self.app(scope, receive, send)
        from fastapi import HTTPException
        from . import auth
        from .dependencies import get_current_user, get_db, oauth2_scheme

        request = Request(scope, receive=receive)
        try:
            token = await oauth2_scheme(request)
            if not token and not request.cookies.get(auth.AUTH_COOKIE_NAME):
                raise HTTPException(401, "Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
            # Use the same database provider as the route, including isolated
            # database overrides. Authentication checks revocation and activity.
            provider = request.app.dependency_overrides.get(get_db, get_db)
            with contextmanager(provider)() as db:
                await get_current_user(request, token, db)
        except HTTPException as exc:
            from starlette.responses import JSONResponse
            return await JSONResponse({"detail": exc.detail}, status_code=exc.status_code,
                                      headers=exc.headers)(scope, receive, send)
        await self.app(scope, receive, send)


class RequestBodyLimitMiddleware:
    """Bound bytes before JSON or multipart parsing, including chunked uploads."""
    def __init__(self, app, max_body_bytes: int = 26 * 1024 * 1024):
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        from starlette.formparsers import MultiPartException

        class BodyLimitExceeded(MultiPartException):
            pass

        response = StarletteResponse('{"detail":"Request body too large"}', status_code=413, media_type="application/json")
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except (ValueError, TypeError):
            length = 0
        limit = self.max_body_bytes
        path = scope["path"].rstrip("/")
        if _protected_upload_path(path) and path != "/import/file":
            # Five MiB files plus bounded multipart fields and framing.
            limit = min(limit, 6 * 1024 * 1024)
        elif path == "/auth/login":
            limit = min(limit, 64 * 1024)
        if length > limit:
            return await response(scope, receive, send)
        received = 0
        exceeded = False

        async def bounded_receive():
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    # Multipart parsers close already-spooled files on this
                    # exception; endpoint code never receives the excess chunk.
                    raise BodyLimitExceeded("Request body too large")
            return message

        async def bounded_send(message):
            if not exceeded:
                await send(message)

        try:
            await self.app(scope, bounded_receive, bounded_send)
        except BodyLimitExceeded:
            pass
        if exceeded:
            await response(scope, receive, send)
