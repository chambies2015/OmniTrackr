"""Draws the /switch/<slug> guides from app/switch_guides.py into templates/switch_source.html."""
from __future__ import annotations

import json
from datetime import date
from html import escape
from html.parser import HTMLParser

from .reader_pages import ReaderPage
from .switch_guides import GUIDES, path, short_name

SITE = "https://omnitrackr.xyz"
HUB = ("Switching guide", "/switch")
SIGNUP = "/?start=import#landing-auth"


def _e(value: str) -> str:
    return escape(value, quote=True)


class _TextOnly(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _text(fragment: str) -> str:
    """Plain text of the trusted inline HTML used in answers, for structured data."""
    parser = _TextOnly()
    parser.feed(fragment)
    parser.close()
    return "".join(parser.parts)


def reader_page(slug: str, *, with_related: bool = True) -> ReaderPage:
    guide = GUIDES[slug]
    related = tuple(reader_page(other, with_related=False) for other in guide["related"]) if with_related else ()
    return ReaderPage(path(slug), f"From {short_name(slug)}", "guides",
                      f"Export steps and what carries over from {guide['name']}: {guide['kinds']}.",
                      related, parent=HUB)


def _structured(slug: str, guide: dict) -> str:
    url = SITE + path(slug)
    howto = {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": guide["h1"],
        "description": guide["description"],
        "dateModified": guide["reviewed"],
        "inLanguage": "en-US",
        "mainEntityOfPage": url,
        "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": SITE},
        "step": [{"@type": "HowToStep", "position": i, "text": _text(step)}
                 for i, step in enumerate(guide["export"], start=1)]
        + [{"@type": "HowToStep", "position": len(guide["export"]) + 1,
            "text": "Open the Import Studio in OmniTrackr, preview the import, check a few rows and confirm."}],
    }
    faq = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": question,
                        "acceptedAnswer": {"@type": "Answer", "text": _text(answer)}}
                       for question, answer in guide["faq"]],
    }
    blocks = []
    for data in (howto, faq):
        payload = json.dumps(data, ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
        blocks.append(f'  <script type="application/ld+json">{payload}</script>')
    return "\n".join(blocks)


def _cta(text: str) -> str:
    return (f'      <div class="switch-cta"><p>{text}</p>'
            f'<a href="{SIGNUP}" rel="nofollow">Start importing</a></div>\n')


def _content(slug: str, guide: dict) -> str:
    name = guide["name"]
    sections = []
    sections.append(
        '      <header class="content-header">\n'
        f'        <h1>{_e(guide["h1"])}</h1>\n'
        f'        <p>{_e(guide["lead"])}</p>\n'
        '      </header>\n')
    sections.append(_cta("Have your export? Create a free account and the Import Studio opens as soon as you're in. "
                         "Nothing is saved until you've seen the preview."))
    intro = "".join(f"<p>{_e(paragraph)}</p>" for paragraph in guide["intro"])
    sections.append(f'      <section class="content-section" aria-labelledby="why-heading">\n'
                    f'        <h2 id="why-heading">Who this move suits</h2>{intro}</section>\n')
    steps = "".join(f"<li>{step}</li>" for step in guide["export"])
    note = f'<p>{guide["export_note"]}</p>' if guide.get("export_note") else ""
    get_heading = "Connect your account" if slug in {"anilist", "steam"} else f"Get your {name} export"
    sections.append(f'      <section class="content-section" aria-labelledby="export-heading">\n'
                    f'        <h2 id="export-heading">{_e(get_heading)}</h2><ol>{steps}</ol>{note}</section>\n')
    rows = "".join(f'<tr><th scope="row">{_e(theirs)}</th><td>{_e(ours)}</td></tr>' for theirs, ours in guide["mapping"])
    sections.append(
        f'      <section class="content-section" aria-labelledby="map-heading">\n'
        f'        <h2 id="map-heading">What comes across</h2>\n'
        f'        <div class="switch-table-wrap switch-map" tabindex="0" role="region" aria-label="What comes across from {_e(name)}">'
        f'<table class="switch-table"><thead><tr><th scope="col">In {_e(name)}</th><th scope="col">In OmniTrackr</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div>\n'
        '        <p>A title you already track is skipped, so your own rating, review and progress are never replaced. '
        'A title repeated in the file is created once. Imported notes stay private until you publish one.</p></section>\n')
    stays = "".join(f"<li>{_e(item)}</li>" for item in guide["stays"])
    sections.append(f'      <section class="content-section" aria-labelledby="stays-heading">\n'
                    f'        <h2 id="stays-heading">What stays on {_e(name)}</h2><ul>{stays}</ul></section>\n')
    if slug in {"anilist", "steam"}:
        how = ("<li>Create a free account. The Import Studio opens under Account Settings.</li>"
               "<li>Fetch your list as described above. The preview says what it found.</li>")
    else:
        how = ("<li>Create a free account and open <strong>Account Settings</strong>, then <strong>Import Studio</strong>.</li>"
               "<li>Leave the format on Detect automatically, choose your file and select <strong>Preview import</strong>. "
               "The preview names the format it recognized.</li>")
    sections.append(
        '      <section class="content-section" aria-labelledby="import-heading">\n'
        '        <h2 id="import-heading">Import and check</h2>'
        f'<ol>{how}<li>Look at the counts for ready, duplicate and needs-attention rows, then page through a few and '
        f'compare them with {_e(name)}.</li><li>Confirm. Every ready row is saved together, or none are if something goes wrong.</li></ol>'
        '<p>One import can hold up to 5,000 titles and 5 MB. Split a bigger history into several files; titles saved by an '
        'earlier file are recognized as duplicates.</p></section>\n')
    after = "".join(f"<li>{_e(item)}</li>" for item in guide["after"])
    sections.append(f'      <section class="content-section" aria-labelledby="after-heading">\n'
                    f'        <h2 id="after-heading">Your first week after switching</h2><ul>{after}</ul></section>\n')
    faq = "".join(f"<dt>{_e(question)}</dt><dd>{answer}</dd>" for question, answer in guide["faq"])
    sections.append(f'      <section class="content-section" aria-labelledby="faq-heading">\n'
                    f'        <h2 id="faq-heading">Questions</h2><dl class="switch-faq">{faq}</dl></section>\n')
    sections.append(_cta(f"Ready to bring your {_e(guide['kinds'])} across? Sign up free and you land in the Import Studio."))
    others = "".join(f'<li><a href="{path(other)}">{_e(short_name(other))}</a></li>' for other in GUIDES if other != slug)
    sections.append(f'      <section class="content-section" aria-labelledby="others-heading">\n'
                    f'        <h2 id="others-heading">Coming from somewhere else?</h2><ul class="switch-others">{others}</ul>'
                    '<p>Or use a spreadsheet: the <a href="/export-import-guide">export and import guide</a> shows the columns.</p></section>\n')
    reviewed = date.fromisoformat(guide["reviewed"])
    sections.append(
        '      <section class="content-section" aria-labelledby="method-heading">\n'
        '        <h2 id="method-heading">How this guide was checked</h2>'
        f'<p>Written by OmniTrackr and checked against the Import Studio on '
        f'<time datetime="{reviewed.isoformat()}">{reviewed.strftime("%B")} {reviewed.day}, {reviewed.year}</time>. '
        f'{_e(name[0].upper() + name[1:])} changes its menus from time to time, so the steps say where to look rather than quoting every button. '
        'If something no longer matches, tell us through <a href="/contact">Contact</a>.</p></section>\n')
    sections.append(
        '      <section class="content-section" aria-labelledby="related-heading">\n'
        '        <h2 id="related-heading">Related pages</h2>'
        f'<p>The <a href="/switch#{guide["hub"]}">switching guide</a> compares every service on one page, and the '
        '<a href="/demo">demo</a> shows a full library before you sign up.</p></section>\n')
    return "".join(sections)


def render(requested: str) -> tuple[dict[str, str], ReaderPage] | None:
    # Draw the page from the catalog's own key so nothing from the URL reaches the HTML.
    slug = next((known for known in GUIDES if known == requested), None)
    if slug is None:
        return None
    guide = GUIDES[slug]
    replacements = {
        "{{TITLE}}": _e(guide["title"]),
        "{{DESCRIPTION}}": _e(guide["description"]),
        "{{OG_TITLE}}": _e(guide["h1"]),
        "{{PATH}}": path(slug),
        "{{STRUCTURED_DATA}}": _structured(slug, guide),
        "{{CONTENT}}": _content(slug, guide),
    }
    return replacements, reader_page(slug)
