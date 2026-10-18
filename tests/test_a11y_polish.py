"""Accessibility and phone polish on the signed-in dashboard."""
import re
from pathlib import Path

from app import dashboard_assets

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
A11Y_CSS = (ROOT / "app" / "static" / "a11y.css").read_text(encoding="utf-8")
BUNDLE, _ = dashboard_assets.bundle()


def _contrast(foreground: str, background: str) -> float:
    def luminance(hex_color: str) -> float:
        channels = [int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    high, low = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_dialog_and_row_edit_focus_ship_in_the_dashboard_bundle():
    assert "a11y.js" in dashboard_assets.EAGER_MODULES
    for hook in ("a11yWatchOverlayDialogs", "aria-modal", "a11yDialogOpeners", "#skipToLibrary"):
        assert hook in BUNDLE


def test_skip_link_comes_first_and_search_is_a_combobox():
    body = INDEX.split("<body", 1)[1]
    assert body.index('class="skip-link"') < body.index('class="account-toolbar"')
    assert re.search(r'id="librarySearchInput"[^>]*role="combobox"', INDEX)
    assert 'role="banner"' not in INDEX


def test_account_fields_have_names_and_autofill_hints():
    for field_id, autocomplete in (
        ("newUsername", "username"), ("usernamePassword", "current-password"), ("newEmail", "email"),
        ("emailPassword", "current-password"), ("currentPassword", "current-password"),
        ("accountNewPassword", "new-password"), ("accountConfirmNewPassword", "new-password"),
    ):
        tag = re.search(rf'<input[^>]*id="{field_id}"[^>]*>', INDEX).group(0)
        assert "aria-label=" in tag and f'autocomplete="{autocomplete}"' in tag


def test_violet_buttons_keep_white_text_readable():
    assert "body.app-shell.dark-mode { --accent-solid: #7c3aed; }" in A11Y_CSS
    for colour in ("#7c3aed", "#9333ea"):
        assert _contrast("#ffffff", colour) >= 4.5
    assert _contrast("#0f766e", "#ffffff") >= 4.5


def test_touch_screens_get_44px_targets():
    coarse = A11Y_CSS[A11Y_CSS.index("@media (pointer: coarse)"):]
    assert "min-height: 44px" in coarse
