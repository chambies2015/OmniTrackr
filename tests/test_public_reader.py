"""Public reading paths must work with native links, including without JavaScript."""
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

import pytest


READER_PATHS = (
    "/guides", "/compare", "/export-import-guide", "/media-tracking",
    "/movie-tracker", "/tv-show-tracker", "/anime-tracker", "/game-tracker",
    "/music-tracker", "/book-tracker", "/media-statistics", "/tracking-templates",
    "/media-tracker-checklist", "/review-guidelines", "/sample-library", "/use-cases",
)

# These destinations predate the reading refresh and may already be bookmarked.
EXISTING_ANCHORS = {
    "/guides": {
        "guide-library-heading", "getting-started-heading", "tracking-heading",
        "library-filters-heading", "reviews-heading", "statistics-heading",
        "social-heading", "import-export-heading", "tips-heading",
    },
    "/compare": {
        "why-compare-heading", "table-heading", "decision-heading",
        "migration-heading", "related-heading",
    },
    "/export-import-guide": {
        "why-heading", "export-heading", "import-heading", "sources-heading",
        "examples-heading", "preview-heading", "duplicates-heading",
        "habits-heading", "not-included-heading", "trust-heading", "related-heading",
    },
}


class ReaderPage(HTMLParser):
    VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr",
    }

    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.stack = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        element = (tag, dict(attrs), tuple(self.stack))
        self.elements.append(element)
        if tag not in self.VOID_TAGS:
            self.stack.append(element)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def tagged(self, tag):
        return [element for element in self.elements if element[0] == tag]

    def inside(self, tag, ancestor):
        return [element for element in self.tagged(tag) if any(parent is ancestor for parent in element[2])]

    @property
    def ids(self):
        return [attrs["id"] for _, attrs, _ in self.elements if attrs.get("id")]

    @property
    def links(self):
        return [attrs["href"] for _, attrs, _ in self.tagged("a") if attrs.get("href")]


@pytest.mark.parametrize("path", READER_PATHS)
def test_reader_has_keyboard_skip_and_working_section_navigation(client, path):
    response = client.get(path)
    assert response.status_code == 200
    page = ReaderPage(response.text)
    assert len(page.ids) == len(set(page.ids)), f"Duplicate fragment targets on {path}"

    mains = page.tagged("main")
    assert len(mains) == 1
    main = mains[0]
    assert main[1].get("tabindex") == "-1"
    skip_links = [
        element for element in page.tagged("a")
        if "reader-skip" in element[1].get("class", "").split()
    ]
    assert len(skip_links) == 1
    assert skip_links[0][1]["href"] == f'#{main[1]["id"]}'
    assert page.elements.index(skip_links[0]) < page.elements.index(main)
    assert len(page.inside("h1", main)) == 1

    contents = [element for element in page.tagged("nav") if element[1].get("aria-label") == "On this page"]
    assert len(contents) == 1
    jumps = [element[1]["href"] for element in page.inside("a", contents[0])]
    assert jumps, f"No section jumps on {path}"
    heading_ids = {
        attrs["id"] for tag, attrs, _ in page.elements
        if tag in {"h2", "h3"} and attrs.get("id")
    }
    assert all(href.startswith("#") and unquote(href[1:]) in heading_ids for href in jumps)


def test_public_reader_fragment_links_resolve_across_pages(client):
    """A 200 response alone does not prove a cross-guide deep link works."""
    pages = {}

    def get_page(path):
        if path not in pages:
            response = client.get(path)
            assert response.status_code == 200, path
            pages[path] = ReaderPage(response.text)
        return pages[path]

    for source in READER_PATHS:
        page = get_page(source)
        for href in page.links:
            target = urlsplit(href)
            if target.scheme or target.netloc or not target.fragment:
                continue
            target_path = target.path or source
            target_page = get_page(target_path)
            assert unquote(target.fragment) in target_page.ids, f"{source} has broken deep link {href}"

    for path, anchors in EXISTING_ANCHORS.items():
        assert anchors.issubset(get_page(path).ids), f"Previously available bookmarks disappeared from {path}"


def test_guides_offer_four_native_task_paths_without_loading_the_private_app(client):
    page = ReaderPage(client.get("/guides").text)
    paths = [
        element for element in page.tagged("a")
        if "guide-path" in element[1].get("class", "").split()
    ]
    assert len(paths) == 4
    assert len({element[1]["href"] for element in paths}) == 4
    assert all(element[1]["href"].startswith("#") for element in paths)
    assert all(element[1]["href"][1:] in page.ids for element in paths)
    script_paths = {
        urlsplit(attrs["src"]).path for _, attrs, _ in page.tagged("script")
        if attrs.get("src")
    }
    assert script_paths.isdisjoint({"/app.js", "/auth.js", "/credentials.js", "/static/app.js", "/static/auth.js"})


def test_comparison_table_preserves_context_for_keyboard_and_screen_reader_users(client):
    page = ReaderPage(client.get("/compare").text)
    tables = page.tagged("table")
    assert len(tables) == 1
    table = tables[0]
    scroll_regions = [
        ancestor for ancestor in table[2]
        if ancestor[1].get("role") == "region" and ancestor[1].get("tabindex") == "0"
    ]
    assert len(scroll_regions) == 1
    assert scroll_regions[0][1].get("aria-label")
    assert len(page.inside("caption", table)) == 1
    rows = page.inside("tr", table)
    assert len(rows) > 1
    columns = page.inside("th", rows[0])
    assert columns
    assert all(element[1].get("scope") == "col" for element in columns)
    for row in rows[1:]:
        cells = [element for element in page.elements if element[0] in {"th", "td"} and any(parent is row for parent in element[2])]
        assert len(cells) == len(columns)
        assert cells[0][0] == "th" and cells[0][1].get("scope") == "row"
