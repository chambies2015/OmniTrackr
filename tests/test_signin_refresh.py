"""The refreshed sign-in card: same markup on both pages, one stylesheet that draws it."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = (ROOT / "app" / "templates" / "public_landing.html").read_text(encoding="utf-8")
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
AUTH_CSS = (ROOT / "app" / "static" / "auth-forms.css").read_text(encoding="utf-8")
LANDING_CSS = (ROOT / "app" / "static" / "public-landing.css").read_text(encoding="utf-8")
AUTH_JS = (ROOT / "app" / "static" / "auth.js").read_text(encoding="utf-8")


def _card(html: str) -> str:
    start = html.index('<div class="auth-container auth-card')
    return html[start:html.index("</section>", start)]


def test_both_pages_carry_the_new_steps():
    for html in (LANDING, INDEX):
        card = _card(html)
        for required in ('id="verifySentPanel"', 'id="verifySentInbox"', 'id="verifySentResend"', 'id="verifySentLogin"',
                         'id="verifySentRestart"', 'id="authStatusPanel"', 'id="registerHandle"', 'id="registerHandleChange"',
                         'id="registerUsernameField"', 'id="registerEmailSuggest"', 'id="registerEmailFix"'):
            assert required in card, required
        # The resend box sits under the messages, above every form.
        assert card.index('id="resendVerificationContainer"') < card.index('id="loginForm"')
        assert card.index('id="authSuccess"') < card.index('id="resendVerificationContainer"')
        # New passwords are typed once, with a Show button.
        assert "confirmNewPassword" not in card and "registerConfirmPassword" not in card
        assert card.count("data-password-toggle=") == 3
        # A link that leaves for a mail service must not hand it the opener or the referrer.
        inbox = re.search(r'<a[^>]*id="verifySentInbox"[^>]*>', card).group(0)
        assert 'target="_blank"' in inbox and 'rel="noopener noreferrer"' in inbox


def test_sign_up_asks_for_email_then_password_and_keeps_the_username_box_for_no_script():
    for html in (LANDING, INDEX):
        form = html[html.index('<form id="registerFormElement"'):html.index("</form>", html.index('<form id="registerFormElement"'))]
        order = [form.index(f'id="{name}"') for name in ("registerEmail", "registerPassword", "registerHandle", "registerUsername", "registerWeekly")]
        assert order == sorted(order)
        # Folded by the script, so the box is still there (and required) when the script does not run.
        assert '<p class="auth-handle" id="registerHandle" hidden>' in form
        assert re.search(r'<div class="auth-field" id="registerUsernameField">', form)
        assert re.search(r'<input type="text" id="registerUsername"[^>]*required', form)


def test_the_card_is_drawn_by_one_stylesheet_on_shared_tokens():
    assert ".lp-auth__card" not in AUTH_CSS
    for leftover in (".lp .lp-auth__card .auth-form", ".lp .lp-auth__card .auth-google", ".lp #authError"):
        assert leftover not in LANDING_CSS, leftover
    for token in ("var(--radius-pill", "var(--radius-md", "var(--radius-xl", "var(--ring", "var(--space-4", "var(--dur-fast"):
        assert token in AUTH_CSS, token
    # Both themes of the dashboard fallback come from the app's own tokens.
    for token in ("var(--card-bg", "var(--field-bg", "var(--accent-solid", "var(--danger-soft", "var(--success-soft"):
        assert token in AUTH_CSS, token
    assert "prefers-reduced-motion" in AUTH_CSS
    # On a phone the pop-up fills the screen.
    phone = LANDING_CSS[LANDING_CSS.index("@media (max-width: 560px) {\n  .lp-auth-dialog"):]
    assert "height: 100dvh" in phone.split("}\n@keyframes", 1)[0]


def test_pages_ask_for_the_new_copies_of_the_files():
    tags = {}
    for name in ("auth-forms.css", "public-landing.css", "public-landing.js"):
        found = re.search(rf"{re.escape(name)}\?v=(\d{{8}})", LANDING)
        assert found and found.group(1) >= "20261110", name
        tags[name] = found.group(0)
    assert tags["auth-forms.css"] in INDEX
    # preauth.js is matched by its exact tag when the public page is built.
    assert './preauth.js?v=20261010-audit-preauth-1' in INDEX


def test_served_homepage_has_the_card_and_the_pop_up(client):
    page = client.get("/").text
    assert 'class="auth-container auth-card lp-auth__card"' in page
    assert '<dialog id="authDialog" class="lp-auth-dialog" aria-labelledby="authTitle">' in page
    assert 'data-action="close-auth-dialog"' in page
    assert "Email me once a week when something I track has a new episode or release." in page


def test_messages_have_no_emoji_and_funnel_events_are_still_sent():
    assert "✅" not in AUTH_JS
    for event in ("signup_form_opened", "guest_list_signup", "signup_rejected_invalid"):
        assert f"reportFunnelEvent('{event}')" in AUTH_JS, event
    assert "document.getElementById('registerFormElement').addEventListener('focusin', () => reportSignupStart());" in AUTH_JS


def test_changelog_mentions_the_new_sign_in():
    changelog = (ROOT / "app" / "templates" / "changelog.html").read_text(encoding="utf-8")
    assert 'id="sign-in-nov10-2026-heading"' in changelog
