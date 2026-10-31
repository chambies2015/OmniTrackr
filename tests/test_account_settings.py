"""Settings dialog and sign-in forms: structure, labels and links the scripts rely on."""
import re
from pathlib import Path

from app import supporters

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
LANDING = (ROOT / "app" / "templates" / "public_landing.html").read_text(encoding="utf-8")
AUTH_JS = (ROOT / "app" / "static" / "auth.js").read_text(encoding="utf-8")
SETTINGS_JS = (ROOT / "app" / "static" / "account-settings.js").read_text(encoding="utf-8")
SUPPORTER_JS = (ROOT / "app" / "static" / "supporter.js").read_text(encoding="utf-8")
GROUPS = ("profile", "signin", "privacy", "notifications", "data", "membership", "danger")


def _modal() -> str:
    start = INDEX.index('<div id="accountModal"')
    return INDEX[start:INDEX.index("<!-- Friend Request Modal -->", start)]


def test_settings_menu_links_every_group_in_order():
    modal = _modal()
    links = re.findall(r'data-settings-link="([a-z]+)"', modal)
    assert tuple(links) == GROUPS
    positions = [modal.index(f'id="settings-{key}"') for key in GROUPS]
    assert positions == sorted(positions)
    for key in GROUPS:
        assert f'href="#settings-{key}"' in modal
        # Each group is a labelled region the menu can move focus to.
        assert re.search(rf'<section[^>]*id="settings-{key}"[^>]*aria-labelledby="settings-{key}-title"[^>]*tabindex="-1"', modal)
    assert "const GROUPS = ['profile', 'signin', 'privacy', 'notifications', 'data', 'membership', 'danger'];" in SETTINGS_JS


def test_sections_land_in_the_right_group():
    modal = _modal()
    def group_of(element_id):
        at = modal.index(f'id="{element_id}"')
        return re.findall(r'id="settings-([a-z]+)"', modal[:at])[-1]
    expected = {
        "accountUsername": "profile", "profilePictureForm": "profile", "publicProfileSection": "profile",
        "changeUsernameForm": "signin", "changeEmailForm": "signin", "changePasswordForm": "signin",
        "privacySettingsForm": "privacy", "tabVisibilityForm": "privacy",
        "emailPreferences": "notifications",
        "exportStudio": "data", "importStudio": "data",
        "supporterSection": "membership", "supporterTiers": "membership",
        "deactivateAccountForm": "danger",
    }
    for element_id, group in expected.items():
        assert group_of(element_id) == group, element_id


def test_settings_keeps_one_heading_level_per_layer():
    modal = _modal()
    assert modal.count("<h2") == 1
    assert len(re.findall(r'<h3 class="account-group__title"', modal)) == len(GROUPS)
    assert "<h3>" not in modal, "section titles sit one level under their group"


def test_password_boxes_in_settings_have_labels_and_show_buttons():
    modal = _modal()
    for field_id in ("usernamePassword", "emailPassword", "currentPassword", "accountNewPassword",
                     "accountConfirmNewPassword", "deactivatePassword"):
        assert re.search(rf'<label[^>]*for="{field_id}"[^>]*>[^<]+</label>', modal), field_id
        assert f'data-password-toggle="{field_id}"' in modal, field_id
    assert 'data-password-strength="accountNewPasswordStrength"' in modal
    assert 'id="accountNewPasswordStrength"' in modal


def test_settings_have_no_inline_handlers_and_load_their_script():
    modal = _modal()
    assert not re.search(r"\son[a-z]+=", modal)
    assert '<script src="/static/account-settings.js?v=' in INDEX
    assert '<link rel="stylesheet" href="/static/account-settings.css?v=' in INDEX
    assert 'id="accountToast" role="status"' in modal


def test_supporter_section_is_upfront_that_tracking_is_free():
    modal = _modal()
    section = modal[modal.index('id="supporterSection"'):modal.index('id="settings-danger"')]
    assert "Every tracking feature is free and stays free." in section
    assert 'href="/supporters"' in section


def test_tier_wording_covers_every_ko_fi_tier():
    perks = SUPPORTER_JS[SUPPORTER_JS.index("const TIER_PERKS = {"):SUPPORTER_JS.index("};", SUPPORTER_JS.index("const TIER_PERKS = {"))]
    for tier in supporters.TIERS:
        assert f"{tier['slug']}:" in perks, tier["slug"]
    assert "for 30 days" in SUPPORTER_JS and supporters.DONATION_DAYS == 30
    # Tier names and prices come from the server's status, never from page text.
    assert "renderTiers(status);" in SUPPORTER_JS
    assert "$3 a month" not in INDEX


def test_sign_in_forms_match_on_both_pages():
    def field_ids(html):
        start = html.index('<div id="loginForm"')
        end = html.index('</form>', html.index('<div id="resetPasswordForm"'))
        return re.findall(r'<(?:input|button|p|a)[^>]*\sid="([^"]+)"', html[start:end])
    assert field_ids(INDEX) == field_ids(LANDING)
    for html in (INDEX, LANDING):
        start = html.index('<div id="loginForm"')
        block = html[start:html.index('</form>', html.index('<div id="resetPasswordForm"'))]
        for field_id in re.findall(r'<input[^>]*\sid="([^"]+)"', block):
            assert re.search(rf'<label[^>]*for="{field_id}"', block), field_id
        for described in re.findall(r'aria-describedby="([^"]+)"', block):
            for target in described.split():
                assert f'id="{target}"' in block, target
        assert 'id="authError" role="alert"' in html
        assert "registerConfirmPassword" not in block


def test_sign_in_switch_links_are_reachable_by_keyboard():
    for html in (INDEX, LANDING):
        for link_id in ("showRegister", "showLogin", "showForgotPassword", "backToLogin"):
            assert re.search(rf'<a id="{link_id}"[^>]*href="#', html), link_id


def test_resend_never_uses_a_browser_prompt():
    assert "prompt(" not in AUTH_JS
    assert 'id="resendVerificationEmail"' in LANDING
