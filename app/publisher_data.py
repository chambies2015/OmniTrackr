"""Who publishes OmniTrackr, in structured data.

The homepage and the About page carry the full Organization record (``organization``):
logo, contact point, the editorial standards, the corrections policy, how the site is
paid for, and the profiles that belong to it. Every other page that names OmniTrackr
as its publisher points at that record by ``@id`` (``link_publisher``, an html_finish
step), so a guide's Article data and the About page describe the same publisher, and
each guide says which standards it was written to (``publishingPrinciples``).

``link_publisher`` edits the JSON text in place instead of re-serialising it, so
everything else in a page's data keeps its exact formatting.
"""
from __future__ import annotations

import json
import re

SITE = "https://omnitrackr.xyz"
ORG_ID = f"{SITE}/#organization"
LOGO = f"{SITE}/omnitrackr_vortex.png"
STANDARDS = f"{SITE}/content-quality"
CORRECTIONS = f"{SITE}/corrections"
EMAIL = "omnitrackr@gmail.com"
PROFILES = ("https://ko-fi.com/omnitrackr", "https://github.com/chambies2015/OmniTrackr")


def organization() -> dict:
    """The full publisher record, for the homepage and the About page."""
    return {
        "@type": "Organization",
        "@id": ORG_ID,
        "name": "OmniTrackr",
        "url": f"{SITE}/",
        "logo": LOGO,
        "description": ("An independent, free media tracker for movies, TV shows, anime, video games, music, books, "
                        "manga, podcasts and audiobooks, with free written guides to what to try next. Run by one person."),
        "email": EMAIL,
        "contactPoint": {"@type": "ContactPoint", "contactType": "customer support", "email": EMAIL,
                         "url": f"{SITE}/contact", "availableLanguage": "English"},
        "publishingPrinciples": STANDARDS,
        "correctionsPolicy": CORRECTIONS,
        "ethicsPolicy": STANDARDS,
        "actionableFeedbackPolicy": f"{CORRECTIONS}#send",
        "ownershipFundingInfo": f"{SITE}/about#money-heading",
        "sameAs": list(PROFILES),
    }


def organization_json() -> str:
    data = {"@context": "https://schema.org", **organization()}
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


# The publisher objects routers and templates write today, in any spacing.
_PUBLISHER = re.compile(
    r'"publisher":\s*\{\s*"@type":\s*"Organization",\s*"name":\s*"OmniTrackr",\s*'
    r'"url":\s*"https://omnitrackr\.xyz(?:/(?:about)?)?"\s*\}'
)
_LD = re.compile(r'(<script type="application/ld\+json"[^>]*>)(.*?)(</script>)', re.S)
_PUBLISHER_REF = json.dumps({"@type": "Organization", "@id": ORG_ID, "name": "OmniTrackr", "url": f"{SITE}/",
                             "logo": LOGO})


def _link(block: str) -> str:
    if '"OmniTrackr"' not in block or '"publisher"' not in block:
        return block
    principles = "" if '"publishingPrinciples"' in block else f', "publishingPrinciples": "{STANDARDS}"'
    changed = _PUBLISHER.sub(lambda _: f'"publisher": {_PUBLISHER_REF}{principles}', block)
    if changed == block:
        return block
    try:
        json.loads(changed)
    except ValueError:
        return block  # never send data that no longer parses
    return changed


def link_publisher(html: str) -> str:
    if "application/ld+json" not in html or '"publisher"' not in html:
        return html
    return _LD.sub(lambda m: m.group(1) + _link(m.group(2)) + m.group(3), html)
