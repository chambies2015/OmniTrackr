"""Nov 22 2026 sweep of PR #303, the homepage "Your library" panel."""
from pathlib import Path

from app import guest_picks, landing_proof

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "app/static/public-landing.css").read_text(encoding="utf-8")
SHELF_JS = (ROOT / "app/static/home-shelf.js").read_text(encoding="utf-8")
LANDING = (ROOT / "app/templates/public_landing.html").read_text(encoding="utf-8")


def test_a_spanish_review_with_an_english_phrase_is_not_quoted():
    # A real review on /reviews: "a" and "at" alone cleared the English share.
    assert not landing_proof.reads_as_english(
        "Animación distinta y una historia muy original, unsettling at times pero eso añade a la experiencia.")
    # Polish uses "i", "a", "to" and "on" a lot, which are English words too.
    assert not landing_proof.reads_as_english(
        "To jest naprawdę dobry film i polecam go każdemu, a zwłaszcza fanom kina akcji. On jest świetny i to widać.")


def test_english_reviews_with_names_and_accents_are_still_quoted():
    for text in (
        "Pokémon Legends is the first Pokémon game in years that made me want to explore, and the Pokémon themselves feel alive.",
        "Sōsō no Frieren is the best anime of the decade for me. The pacing is slow but it pays off in every episode.",
        "Another good Leonardo di Caprio movie that continually changes what you think will happen next.",
        "La La Land is still the musical I put on when I want to feel something, and the ending gets me every time.",
    ):
        assert landing_proof.reads_as_english(text), text


def test_the_other_language_words_are_never_english_ones():
    assert not landing_proof.OTHER_WORDS & landing_proof.ENGLISH_WORDS


def test_phone_rule_for_even_rows_skips_a_chosen_format():
    # The tenth most-tracked tile is hidden on phones only while "Most tracked" is chosen.
    assert ".lp-picks__grid:not(.is-filtered) > li[data-picks-top]:nth-child(10)" in CSS
    assert ".lp-picks__grid > li[data-picks-top]:nth-child(10)" not in CSS
    assert "grid.classList.toggle('is-filtered', which !== 'top')" in SHELF_JS


def test_focus_is_kept_when_the_suggestion_row_is_redrawn():
    draw = SHELF_JS[SHELF_JS.index("async function drawAlso"):SHELF_JS.index("function focusInRow")]
    # Where focus was is read before the row is replaced, and put back after.
    assert draw.index("row.contains(document.activeElement)") < draw.index("row.replaceChildren(")
    assert "focusInRow(shelf, row, focusAt)" in draw
    assert "setTimeout" not in SHELF_JS[SHELF_JS.index("function setupShelf"):]


def test_panel_is_a_labelled_section_inside_the_picks():
    html = guest_picks.shelf_html()
    assert html.startswith('<section class="lp-shelf') and html.endswith("</section>")
    assert "<aside" not in html and 'aria-labelledby="lp-shelf-title"' in html


def test_suggestion_titles_wrap_and_changed_files_have_new_tags():
    rule = next(line for line in CSS.splitlines() if line.startswith(".lp-shelf__pick-title {"))
    assert "overflow-wrap: anywhere" in rule
    # Static files are cached for a year, so a change needs a new ?v= tag.
    assert "/static/public-landing.css?v=20261122-shelf-1" not in LANDING
    assert "/static/home-shelf.js?v=20261122-shelf-1" not in LANDING
    assert "/static/home-shelf.js?v=20261122-shelf-sweep-1" in LANDING
