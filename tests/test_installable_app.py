"""Installable app: manifest, offline-only service worker, and page wiring."""
import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def test_manifest_is_served_and_installable(client):
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")
    manifest = json.loads(response.text)
    assert manifest["name"] == "OmniTrackr"
    assert manifest["start_url"] == "/" and manifest["scope"] == "/"
    assert manifest["display"] == "standalone"
    purposes = {(icon["sizes"], icon["purpose"]) for icon in manifest["icons"]}
    assert {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")} <= purposes
    for shortcut in manifest["shortcuts"]:
        assert shortcut["url"].startswith("/") and not shortcut["url"].startswith("//")


def test_manifest_icons_exist_with_declared_sizes(client):
    manifest = json.loads((STATIC / "manifest.webmanifest").read_text(encoding="utf-8"))
    icons = manifest["icons"] + [icon for shortcut in manifest["shortcuts"] for icon in shortcut["icons"]]
    for icon in icons:
        response = client.get(icon["src"])
        assert response.status_code == 200, icon["src"]
        width, height = (int(value) for value in icon["sizes"].split("x"))
        with Image.open(STATIC / icon["src"].removeprefix("/static/")) as image:
            assert image.size == (width, height)
    with Image.open(STATIC / "icons" / "apple-touch-icon.png") as image:
        assert image.size == (180, 180)


def test_service_worker_is_root_scoped_and_revalidated(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["service-worker-allowed"] == "/"


def test_service_worker_never_caches_private_data():
    source = (STATIC / "sw.js").read_text(encoding="utf-8")
    precache = re.search(r"PRECACHE_URLS = \[(.*?)\];", source).group(1)
    assert precache.replace(" ", "") == "OFFLINE_URL,'/static/offline.css?v=1','/static/icons/icon-192.png'"
    # The only writes are the precache list; navigations and API calls are never stored.
    assert source.count("cache.addAll(") == 1
    assert ".put(" not in source
    assert "request.method !== 'GET'" in source
    assert "url.origin !== self.location.origin" in source


def test_offline_page_is_static_and_unindexed(client):
    response = client.get("/offline")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert "You're offline" in response.text
    assert "<script" not in response.text and "style=" not in response.text
    assert client.get("/static/offline.css?v=1").status_code == 200


def test_offline_page_is_not_in_sitemap(client):
    assert "/offline" not in client.get("/sitemap.xml").text


def test_public_pages_link_manifest_and_register_worker(client):
    for path in ("/", "/about", "/reviews", "/release-radar"):
        html = client.get(path).text
        assert html.count('rel="manifest" href="/manifest.webmanifest"') == 1, path
        assert '/static/icons/apple-touch-icon.png' in html, path
        assert re.search(r'<script src="/static/pwa\.js\?v=[^"]+" defer></script>', html), path


def test_dashboard_has_hidden_install_button_and_ios_help():
    html = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
    assert html.count('rel="manifest"') == 1
    assert re.search(r'<button id="installAppBtn"[^>]*\bhidden\b', html)
    assert '<dialog id="installAppDialog"' in html
    assert "/static/pwa.js?v=" in html
