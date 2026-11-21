"""Nov 21 2026 sweep of #273 (Christmas 2026 guide), #274 (April 2027 challenge) and #275 (streamlined home)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")


def test_dark_mode_next_episode_button_uses_dark_ink():
    css = (STATIC / "episodes.css").read_text(encoding="utf-8")
    assert "body.app-shell.dark-mode .episode-next { color: #0e211c; }" in css
    assert "/static/episodes.css?v=20261121-sweep-1" in INDEX


def test_light_mode_today_labels_are_readable():
    css = (STATIC / "dashboard-home.css").read_text(encoding="utf-8")
    rule = re.search(r"body\.app-shell:not\(\.dark-mode\) :is\(([^)]*)\) \{ color: (#[0-9a-f]{6}); \}", css)
    assert rule and ".your-week__day.is-today .your-week__day-name" in rule.group(1)
    assert ".week-one__day.is-today .week-one__day-name" in rule.group(1)
    assert rule.group(2) == "#6d28d9"
    assert "/static/dashboard-home.css?v=20261121-sweep-1" in INDEX


def test_changed_assets_carry_new_tags():
    # challenges.js changed again for the May (#276), June, July, August and September challenges, and home-layout.js for the
    # member phone pass ("Mark watched" on Do this next) and the Nov 21 morning sweep, so they carry later tags.
    for tag in ("./styles.css?v=20261121-sweep-1", "/static/challenges.js?v=20261121-required-reading-1",
                "/static/home-layout.js?v=20261121-sweep-d-1"):
        assert tag in INDEX, tag


def test_home_layout_remembers_the_linked_card_without_expanding_everything():
    js = (STATIC / "home-layout.js").read_text(encoding="utf-8")
    assert "layout.asked = hashCard();" in js
    assert "id === layout.asked" in js
    assert "hashCard(event && event.newURL)" in js
    reveal = js[js.index("function revealFor("):js.index("function watchSettle(")]
    assert "setExpanded" not in reveal and "localStorage" not in reveal
    assert "keepAskedInView();" in js
