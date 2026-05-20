"""
Helpers for serving HTML with a strict nonce-based Content Security Policy.
"""
from html import escape
from html.parser import HTMLParser
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


def _safe_style_declarations(style: str) -> str | None:
    declarations = style.replace("\x00", "").strip()
    lower_declarations = declarations.lower()
    if (
        "<" in declarations
        or ">" in declarations
        or "{" in declarations
        or "}" in declarations
        or "</style" in lower_declarations
        or "<script" in lower_declarations
        or "</script" in lower_declarations
    ):
        return None
    return declarations


class _CSPHTMLTransformer(HTMLParser):
    def __init__(self, nonce: str, add_nonces: bool = True, extract_styles: bool = True):
        super().__init__(convert_charrefs=False)
        self.nonce = nonce
        self.add_nonces = add_nonces
        self.extract_styles = extract_styles
        self.output: list[str] = []
        self.styles: dict[str, str] = {}
        self.style_block_inserted = False

    def class_name_for(self, style: str) -> str:
        if style not in self.styles:
            self.styles[style] = f"csp-style-{len(self.styles) + 1}"
        return self.styles[style]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.output.append(self.render_start_tag(tag, attrs))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.output.append(self.render_start_tag(tag, attrs, self_closing=True))

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "head":
            self.inject_style_block()
        self.output.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.output.append(data)

    def handle_entityref(self, name: str) -> None:
        self.output.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.output.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.output.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.output.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self.output.append(f"<?{data}>")

    def close(self) -> None:
        super().close()
        self.inject_style_block()

    def has_attr(self, attrs: list[tuple[str, str | None]], name: str) -> bool:
        return any(attr_name.lower() == name for attr_name, _ in attrs)

    def render_start_tag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
        self_closing: bool = False,
    ) -> str:
        normalized_tag = tag.lower()
        rendered_attrs: list[tuple[str, str | None]] = []
        generated_class = None

        for attr_name, attr_value in attrs:
            normalized_attr_name = attr_name.lower()
            if self.extract_styles and normalized_tag != "style" and normalized_attr_name == "style":
                if attr_value is not None:
                    safe_style = _safe_style_declarations(attr_value)
                    if safe_style:
                        generated_class = self.class_name_for(safe_style)
                continue
            rendered_attrs.append((attr_name, attr_value))

        if generated_class:
            rendered_attrs = self.add_or_extend_class(rendered_attrs, generated_class)

        should_nonce = (
            self.add_nonces
            and not self.has_attr(rendered_attrs, "nonce")
            and (
                normalized_tag == "style"
                or (normalized_tag == "script" and not self.has_attr(rendered_attrs, "src"))
            )
        )
        if should_nonce:
            rendered_attrs.append(("nonce", self.nonce))

        suffix = " />" if self_closing else ">"
        return f"<{tag}{self.render_attrs(rendered_attrs)}{suffix}"

    def add_or_extend_class(
        self,
        attrs: list[tuple[str, str | None]],
        generated_class: str,
    ) -> list[tuple[str, str | None]]:
        for index, (attr_name, attr_value) in enumerate(attrs):
            if attr_name.lower() == "class":
                existing_classes = (attr_value or "").strip()
                combined_classes = f"{existing_classes} {generated_class}".strip()
                attrs[index] = (attr_name, combined_classes)
                return attrs
        attrs.append(("class", generated_class))
        return attrs

    def render_attrs(self, attrs: list[tuple[str, str | None]]) -> str:
        rendered = []
        for attr_name, attr_value in attrs:
            if attr_value is None:
                rendered.append(f" {escape(attr_name, quote=True)}")
            else:
                rendered.append(f' {escape(attr_name, quote=True)}="{escape(attr_value, quote=True)}"')
        return "".join(rendered)

    def style_block(self) -> str:
        if not self.styles:
            return ""
        style_rules = "\n".join(f".{class_name} {{{style}}}" for style, class_name in self.styles.items())
        return f'<style nonce="{escape(self.nonce, quote=True)}">\n{style_rules}\n</style>\n'

    def inject_style_block(self) -> None:
        if self.style_block_inserted:
            return
        block = self.style_block()
        if block:
            self.output.append(block)
            self.style_block_inserted = True


def transform_html_for_csp(html: str, nonce: str, add_nonces: bool = True, extract_styles: bool = True) -> str:
    transformer = _CSPHTMLTransformer(nonce, add_nonces=add_nonces, extract_styles=extract_styles)
    transformer.feed(html)
    transformer.close()
    return "".join(transformer.output)


def add_nonce_to_inline_tags(html: str, nonce: str) -> str:
    return transform_html_for_csp(html, nonce, add_nonces=True, extract_styles=False)


def extract_inline_styles(html: str, nonce: str) -> str:
    return transform_html_for_csp(html, nonce, add_nonces=False, extract_styles=True)


def nonce_html_response(
    html: str,
    status_code: int = 200,
    allow_inline_style: bool = False,
    allow_inline_script: bool = False,
) -> HTMLResponse:
    nonce = secrets.token_urlsafe(16)
    return HTMLResponse(
        transform_html_for_csp(html, nonce),
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
