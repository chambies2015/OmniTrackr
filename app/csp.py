"""
Helpers for serving HTML with a strict nonce-based Content Security Policy.
"""
import re
import secrets

from fastapi.responses import HTMLResponse


SCRIPT_SOURCES = (
    "'self'",
    "https://www.googletagmanager.com",
    "https://www.google-analytics.com",
    "https://pagead2.googlesyndication.com",
)


def build_csp(nonce: str | None = None, allow_inline_script: bool = False, allow_inline_style: bool = False) -> str:
    script_sources = list(SCRIPT_SOURCES)
    style_sources = ["'self'", "https://fonts.googleapis.com"]

    if nonce:
        script_sources.append(f"'nonce-{nonce}'")
        style_sources.append(f"'nonce-{nonce}'")
    if allow_inline_script:
        script_sources.append("'unsafe-inline'")
    if allow_inline_style:
        style_sources.append("'unsafe-inline'")

    return (
        "default-src 'self'; "
        f"script-src {' '.join(script_sources)}; "
        f"style-src {' '.join(style_sources)}; "
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


def add_nonce_to_inline_tags(html: str, nonce: str) -> str:
    def add_nonce(match: re.Match[str]) -> str:
        tag = match.group(0)
        if " nonce=" in tag:
            return tag
        return tag[:-1] + f' nonce="{nonce}">'

    html = re.sub(r"<script(?=[\s>])(?![^>]*\bsrc=)[^>]*>", add_nonce, html)
    return re.sub(r"<style(?=[\s>])[^>]*>", add_nonce, html)


def extract_inline_styles(html: str, nonce: str) -> str:
    styles: dict[str, str] = {}

    def class_name_for(style: str) -> str:
        normalized = style.strip()
        if normalized not in styles:
            styles[normalized] = f"csp-style-{len(styles) + 1}"
        return styles[normalized]

    def replace_style_attr(match: re.Match[str]) -> str:
        tag_name = match.group("tag")
        if tag_name.lower() == "style":
            return match.group(0)

        before = match.group("before")
        style = match.group("style")
        after = match.group("after")
        generated_class = class_name_for(style)
        attrs = f"{before}{after}"

        class_match = re.search(r'\sclass="([^"]*)"', attrs)
        if class_match:
            existing_classes = class_match.group(1).strip()
            replacement = f' class="{existing_classes} {generated_class}"'
            attrs = attrs[:class_match.start()] + replacement + attrs[class_match.end():]
        else:
            attrs += f' class="{generated_class}"'

        return f"<{tag_name}{attrs}>"

    html = re.sub(
        r"<(?P<tag>[A-Za-z][A-Za-z0-9:-]*)(?P<before>[^>]*?)\sstyle=\"(?P<style>[^\"]*)\"(?P<after>[^>]*)>",
        replace_style_attr,
        html,
    )

    if not styles:
        return html

    style_rules = "\n".join(f".{class_name} {{{style}}}" for style, class_name in styles.items())
    style_block = f'<style nonce="{nonce}">\n{style_rules}\n</style>\n'
    if "</head>" in html:
        return html.replace("</head>", f"{style_block}</head>", 1)
    return f"{style_block}{html}"


def nonce_html_response(
    html: str,
    status_code: int = 200,
    allow_inline_style: bool = False,
    allow_inline_script: bool = False,
) -> HTMLResponse:
    nonce = secrets.token_urlsafe(16)
    html = extract_inline_styles(html, nonce)
    return HTMLResponse(
        add_nonce_to_inline_tags(html, nonce),
        status_code=status_code,
        headers={
            "Content-Security-Policy": build_csp(
                nonce=nonce,
                allow_inline_script=allow_inline_script,
                allow_inline_style=allow_inline_style,
            )
        },
    )


def strict_html_response(html: str, status_code: int = 200) -> HTMLResponse:
    return nonce_html_response(html, status_code=status_code)
