"""Guides link across sections, the editorial page lists every guide, and the
"If you liked" guides and monthly editions carry more original writing (Nov 4 2026)."""
import re

from app import editorial_index, guide_links
from app.discover_catalog import published_editions
from app.html_finish import finish
from app.if_you_liked_guides import GUIDES as LIKED_GUIDES


def test_dune_guides_link_to_each_other():
    to_liked = guide_links.related("/in-order/dune")
    assert any(link["href"] == "/if-you-liked/dune" and "Dune" in link["shared"] for link in to_liked)
    back = guide_links.related("/if-you-liked/dune")
    assert any(link["href"] == "/in-order/dune" for link in back)


def test_spellings_of_one_title_match():
    assert guide_links._key("Mushi-Shi") == guide_links._key("Mushishi")
    assert guide_links._key("OXENFREE") == guide_links._key("Oxenfree")
    assert guide_links._key("The Witcher") == guide_links._key("Witcher")


def test_cross_links_only_point_to_other_sections_and_stay_short():
    for piece in editorial_index.entries():
        links = guide_links.related(piece["href"])
        assert len(links) <= guide_links.MAX_LINKS
        sections = [link["section"] for link in links]
        assert piece["section"] not in sections
        assert all(sections.count(section) <= guide_links.MAX_PER_SECTION for section in sections)
        for link in links:
            assert link["shared"] or link["creators"] or link["kind"]


def test_most_guides_get_at_least_one_cross_link():
    pieces = editorial_index.entries()
    linked = [piece for piece in pieces if guide_links.related(piece["href"])]
    assert len(linked) >= len(pieces) * 2 // 3


def test_guide_page_shows_one_cross_link_block(client):
    html = client.get("/in-order/dune").text
    assert html.count(guide_links.MARKER) == 1
    block = html[html.index("guide-crosslinks"):]
    assert 'href="/if-you-liked/dune"' in block[:block.index("</section>")]
    # The block sits with the page's own related guides, inside <main>.
    assert html.index("guide-crosslinks") < html.index("</main>")


def test_finish_leaves_other_pages_alone():
    page = '<html><head><link rel="canonical" href="https://omnitrackr.xyz/about"></head><body><main></main></body></html>'
    assert guide_links.add_crosslinks(page) == page
    guide = ('<html><head><link rel="canonical" href="https://omnitrackr.xyz/in-order/dune"></head>'
             '<body><main><p>x</p></main></body></html>')
    once = finish(guide)
    assert once.count(guide_links.MARKER) == 1
    assert finish(once).count(guide_links.MARKER) == 1


def test_every_if_you_liked_guide_answers_three_questions(client):
    for slug, guide in LIKED_GUIDES.items():
        assert len(guide["faq"]) == 3, slug
        html = client.get(f"/if-you-liked/{slug}").text
        assert 'id="questions"' in html and 'href="#questions"' in html
        for question, answer in guide["faq"]:
            assert len(answer.split()) >= 30, question
            assert question.replace("'", "&#x27;") in html


def test_monthly_editions_explain_how_the_picks_fit(client):
    for slug, edition in published_editions().items():
        assert len(edition["notes"]["paragraphs"]) >= 2
        html = client.get(f"/discover/monthly/{slug}").text
        assert 'class="editorial edition-notes"' in html
        assert f'Updated <time datetime="{edition["reviewed"]}">' in html
        assert f'"dateModified": "{edition["reviewed"]}"' in html


def test_editorial_page_lists_every_guide_with_its_date(client):
    html = client.get("/content-quality").text
    assert "<!--" not in html[html.index("<main"):html.index("</main>")]
    assert "AI writing tools" in html
    assert 'id="kinds-heading"' in html and 'id="ledger-heading"' in html
    ledger = html[html.index('id="ledger-heading"'):]
    ledger = ledger[:ledger.index("</section>")]
    for piece in editorial_index.entries():
        assert f'href="{piece["href"]}"' in ledger, piece["href"]
    assert len(re.findall(r'<li><a href="', ledger)) == len(editorial_index.entries())


def test_editor_name_is_anonymous_until_set(monkeypatch):
    assert editorial_index.editor_label() == "The site owner"
    monkeypatch.setattr(editorial_index, "EDITOR_NAME", "Sam")
    assert editorial_index.editor_label() == "Sam, who runs OmniTrackr,"
