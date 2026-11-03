"""Sweep of the work since the October 31 check: imports, year so far, episode alerts,
the recap additions, release guides and the phone speed pass."""
import asyncio
import json
import re
from pathlib import Path

from app import dashboard_assets, import_studio
from app.routers import import_studio as import_studio_router

STATIC = Path("app/static")
TEMPLATES = Path("app/templates")


def _off_the_event_loop(calls):
    def record(*args, **kwargs):
        try:
            asyncio.get_running_loop()
            calls.append("event loop")
        except RuntimeError:
            calls.append("worker thread")
        return original(*args, **kwargs)
    original = import_studio_router.classify_rows
    return record


class TestImportsDoNotHoldUpTheServer:
    """Parsing a 5 MB file and matching it against the library took a couple of seconds on the
    event loop, and every other request waited. Both steps now run on a worker thread."""

    CSV = "title,year,rating,watched\nArrival,2016,9,yes\n"

    def test_preview_matches_rows_on_a_worker_thread(self, authenticated_client, monkeypatch):
        calls = []
        monkeypatch.setattr(import_studio_router, "classify_rows", _off_the_event_loop(calls))
        response = authenticated_client.post(
            "/import-studio/preview/", files={"file": ("movies.csv", self.CSV.encode(), "text/csv")},
            data={"source": "generic", "category": "movies"})
        assert response.status_code == 200, response.text
        assert response.json()["ready_count"] == 1
        assert calls == ["worker thread"]

    def test_apply_saves_on_a_worker_thread(self, authenticated_client, monkeypatch):
        files = {"file": ("movies.csv", self.CSV.encode(), "text/csv")}
        data = {"source": "generic", "category": "movies"}
        preview = authenticated_client.post("/import-studio/preview/", files=files, data=data).json()
        calls = []
        monkeypatch.setattr(import_studio_router, "classify_rows", _off_the_event_loop(calls))
        response = authenticated_client.post(
            "/import-studio/apply/", files={"file": ("movies.csv", self.CSV.encode(), "text/csv")},
            data={**data, "fingerprint_confirmation": preview["fingerprint"]})
        assert response.status_code == 200, response.text
        assert response.json()["created_count"] == 1
        assert calls == ["worker thread"]

    def test_a_changed_file_is_still_refused(self, authenticated_client):
        response = authenticated_client.post(
            "/import-studio/apply/", files={"file": ("movies.csv", self.CSV.encode(), "text/csv")},
            data={"source": "generic", "category": "movies", "fingerprint_confirmation": "0" * 64})
        assert response.status_code == 409


class TestDeeplyNestedFiles:
    """json.loads raises RecursionError on arrays nested thousands deep, which came back as a 500."""

    DEEP = ("[" * 50_000 + "]" * 50_000).encode()

    def test_parse_reports_a_broken_file(self):
        try:
            import_studio.parse_csv(self.DEEP, "auto", None, {}, "library.json")
        except ValueError as exc:
            assert "nested too deeply" in str(exc)
        else:
            raise AssertionError("expected a ValueError")

    def test_import_studio_answers_400(self, authenticated_client):
        response = authenticated_client.post(
            "/import-studio/preview/", files={"file": ("library.json", self.DEEP, "application/json")})
        assert response.status_code == 400
        assert "nested too deeply" in response.json()["detail"]

    def test_backup_restore_answers_400(self, authenticated_client):
        response = authenticated_client.post(
            "/import/file/", files={"file": ("backup.json", self.DEEP, "application/json")})
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid JSON file"

    def test_backup_restore_still_imports(self, authenticated_client):
        backup = {"movies": [{"title": "Arrival", "director": "Denis Villeneuve", "year": 2016, "watched": True}],
                  "tv_shows": []}
        response = authenticated_client.post(
            "/import/file/", files={"file": ("backup.json", json.dumps(backup).encode(), "application/json")})
        assert response.status_code == 200, response.text
        assert response.json()["movies_created"] == 1


class TestAccessibility:
    def test_switch_guide_button_keeps_its_contrast_in_dark_mode(self):
        # --primary is light lilac (#c4b5fd) in the reader's dark theme; white on it is 1.8:1.
        for name in ("switch.html", "switch_source.html"):
            html = (TEMPLATES / name).read_text(encoding="utf-8")
            rule = re.search(r"\.switch-cta a \{[^}]*\}", html).group(0)
            assert "background: #6d28d9" in rule and "color: #fff" in rule, name
            assert "var(--primary)" not in rule, name

    def test_account_button_name_includes_the_username_it_shows(self):
        html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
        button = html[html.index('<button id="userDisplay"'):]
        button = button[:button.index("</button>")]
        assert "aria-label" not in button  # a fixed label hid the visible username (WCAG 2.5.3)
        assert '<span class="sr-only">Account settings, </span><span id="userDisplayText"></span>' in button
        assert 'alt=""' in button

    def test_bell_hides_its_emoji_and_says_how_many_are_unread(self):
        html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
        bell = html[html.index('<button id="notificationBell"'):]
        bell = bell[:bell.index("</button>")]
        assert '<span aria-hidden="true">🔔</span>' in bell
        social = dashboard_assets._read("social.js")
        assert "View notifications, ${data.count} unread" in social

    def test_offline_message_goes_to_a_status_box_that_is_already_there(self):
        source = dashboard_assets._read("connection.js")
        assert "bar.status.setAttribute('role', 'status')" in source
        assert "bar.setAttribute('aria-hidden', 'true')" in source
        assert "node.status.textContent = text;" in source
        assert "document.addEventListener('DOMContentLoaded', ensureBar, { once: true })" in source
