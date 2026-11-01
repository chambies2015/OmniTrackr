"""Installable app: the manifest's install sheet and the dashboard install card."""
import json
from pathlib import Path


def test_manifest_has_install_sheet_screenshots_and_member_shortcuts(client):
    data = json.loads(client.get("/manifest.webmanifest").text)
    factors = {shot["form_factor"] for shot in data["screenshots"]}
    assert factors == {"wide", "narrow"}
    for shot in data["screenshots"]:
        response = client.get(shot["src"])
        assert response.status_code == 200 and response.headers["content-type"] == "image/webp"
    urls = [shortcut["url"] for shortcut in data["shortcuts"]]
    assert urls[0].startswith("/?") and any(url.startswith("/daily") for url in urls)
    for url in urls:
        assert client.get(url).status_code == 200
    assert data["launch_handler"]["client_mode"][0] == "navigate-existing"


def test_dashboard_has_a_hidden_install_card_wired_to_sign_in():
    html = Path("app/templates/index.html").read_text(encoding="utf-8")
    assert '<section id="installAppCard" class="install-card" aria-labelledby="installAppCardTitle" hidden>' in html
    for required in ('id="installAppCardInstall"', 'id="installAppCardDismiss"', 'id="installAppCardSummary"'):
        assert required in html, required
    auth = Path("app/static/auth.js").read_text(encoding="utf-8")
    assert "window.refreshInstallCard?.();" in auth
    assert auth.count("window.resetInstallCard?.();") == 2
    social = Path("app/static/dashboard/social.js").read_text(encoding="utf-8")
    assert "window.setAppIconBadge?.(data.count);" in social
