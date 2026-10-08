"""October polish: first-visit order, mobile hero weight, contrast, image sizes, dependency floors."""
import re
from pathlib import Path

from app import dashboard_assets

INDEX = Path("app/templates/index.html").read_text(encoding="utf-8")
LANDING = Path("app/templates/public_landing.html").read_text(encoding="utf-8")


def test_quick_start_comes_before_the_launchpad():
    assert INDEX.index('id="starterPicks"') < INDEX.index('id="libraryLaunchpad"')
    css = Path("app/static/dashboard-2026.css").read_text(encoding="utf-8")
    assert "#starterPicks:not([hidden]) ~ #libraryLaunchpad #libraryLaunchpadCategories { display: none; }" in css


def test_phones_get_the_still_vortex():
    picture = LANDING[LANDING.index("<picture>"):LANDING.index("</picture>")]
    assert '<source srcset="/vortex-still.webp" media="(max-width: 760px)">' in picture
    assert picture.index("max-width: 760px") < picture.index('src="/vortex.webp"')


def test_active_tabs_meet_contrast():
    def ratio(hex_color):
        r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
        lin = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
        return 1.05 / (lum + 0.05)
    assert ratio("#7c3aed") >= 4.5 > ratio("#8b5cf6")
    assert ".showcase-tabs .active { background: #7c3aed" in Path("app/static/public-landing.css").read_text(encoding="utf-8")
    assert 'a[aria-current="page"] { background: #7c3aed' in Path("app/static/release-radar.css").read_text(encoding="utf-8")


def test_poster_tiles_reserve_their_space():
    for path in ("app/routers/release_radar.py", "app/guest_picks.py"):
        source = Path(path).read_text(encoding="utf-8")
        assert all('width="200" height="300"' in tag for tag in re.findall(r"<img src=[^>]+>", source)), path


def test_dependency_security_floors():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    assert "starlette>=1.6.0" in requirements and "h11>=0.16.0" in requirements
    assert "python-multipart==0.0.31" in requirements and "Pillow==12.3.0" in requirements


def test_dead_code_and_unused_files_are_gone():
    assert "cancelFriendRequest" not in dashboard_assets.full_source()
    assert not Path("app/static/movie_theater_background.jpg").exists()
