"""
Middleware for the OmniTrackr API.
Contains security headers and bot filtering middleware.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response as StarletteResponse


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
        
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.googletagmanager.com https://www.google-analytics.com https://pagead2.googlesyndication.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https: http:; "
            "connect-src 'self' https://www.google-analytics.com https://www.googletagmanager.com; "
            "frame-src https://www.google.com; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "upgrade-insecure-requests;"
        )
        response.headers["Content-Security-Policy"] = csp_policy
        
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        if request.url.path.startswith("/auth/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
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

