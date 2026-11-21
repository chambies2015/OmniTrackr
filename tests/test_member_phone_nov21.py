"""Member app phone pass (Nov 21 2026): member-phone.css, one-tap Add on phones, Mark watched."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "member-phone.css").read_text(encoding="utf-8")
QUICK = (STATIC / "dashboard" / "lazy" / "quick-capture.js").read_text(encoding="utf-8")
LAYOUT = (STATIC / "home-layout.js").read_text(encoding="utf-8")


def test_stylesheet_is_linked_once_with_a_version():
    assert INDEX.count('/static/member-phone.css?v=20261121-sweep-d-1') == 1


def test_edge_to_edge_rows_match_the_10px_phone_gutter():
    # app-theme.css drops the page gutter to 10px at 380px; the bleeding rows must follow it.
    theme = (STATIC / "app-theme.css").read_text(encoding="utf-8")
    assert re.search(r"@media \(max-width: 380px\) \{\s*body\.app-shell \{ padding-inline: 10px; \}", theme)
    block = CSS[CSS.index("@media (max-width: 380px)"):]
    block = block[:block.index("}\n}") + 3]
    assert ".ffeed__filters { margin-inline: -10px; padding-inline: 10px; }" in block
    assert ".stats-head__jump { margin-inline: -10px; padding-inline: 10px;" in block


def test_feed_bar_does_not_wrap_on_phones():
    assert "body.app-shell .social-bar { flex-wrap: nowrap; }" in CSS
    assert ".social-switch__btn { flex: 1 1 0;" in CSS
    assert ".activity-diary__controls .action-btn { flex: 1 1 0; margin: 0; min-height: 44px; min-width: 0;" in CSS


def test_one_tap_add_uses_the_same_breakpoint_as_the_full_screen_dialog():
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert "@media (max-width: 680px) {\n  .modal-overlay.quick-capture-overlay { padding: 0; }" in styles
    assert "window.matchMedia('(max-width: 680px)').matches" in QUICK
    assert "oneTap: !!quickCaptureShare || quickCaptureOneTap()" in QUICK
    assert "@media (max-width: 680px) {\n  /* The intro paragraph" in CSS
    # The scrolling body is a flex column; its parts must not shrink into each other.
    assert ".quick-capture-body > * { flex-shrink: 0; }" in CSS


def test_editing_keeps_save_above_the_bottom_bar():
    nav = (STATIC / "app-nav.css").read_text(encoding="utf-8")
    assert "padding-bottom: calc(76px + env(safe-area-inset-bottom, 0px))" in nav
    assert "bottom: calc(76px + env(safe-area-inset-bottom, 0px)); }" in CSS
    assert "position: sticky;" in CSS


def test_mark_watched_uses_each_formats_own_field_and_reuses_the_finish_moment():
    done = LAYOUT[LAYOUT.index("const DONE = {"):LAYOUT.index("function say(")]
    for category, field in (("movies", "watched"), ("'video-games'", "played"), ("music", "listened"),
                            ("books", "read"), ("audiobooks", "listened")):
        assert f"{category}: ['{field}'," in done
    button = LAYOUT[LAYOUT.index("function doneButton("):LAYOUT.index("function started(")]
    assert "method: 'PUT'" in button and "JSON.stringify({ [field]: true })" in button
    assert "openCompletionMoment(item.category, itemId)" in button
    assert "innerHTML" not in button
    # Only when nothing else moves the title forward.
    assert "!actions.querySelector('button.episode-next, button.progress-update')" in LAYOUT
