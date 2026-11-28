"""Whole-site security check, Nov 15 2026 (second pass).

1. Public reviews and collections are unlisted after reports from three different
   visitors. A visitor was only a cookie, so one person clearing cookies could file
   all three. Each network address now counts once per report target.
2. Changing or resetting a password, and moving the sign-in email, now emails the
   account's (previous) address, so a hijacked session can't take the account quietly.
3. The legacy review page escaped text for HTML but not quotes, and put it in attributes.
"""
from pathlib import Path

import pytest

from app import crud, models, visitor_identity
from app import email as email_utils
from app.schemas import MovieCreate

from tests.test_collections import _publish_three_item_collection

ROOT = Path(__file__).resolve().parents[1]
REVIEW_TEXT = (
    "This review explains the deliberate pacing and the lead performance in enough detail for another "
    "viewer to understand the rating. The middle act repeats one conflict, but the ending rewards the "
    "setup and makes the film worth revisiting. I would recommend it to viewers who enjoy patient, "
    "character-focused thrillers more than constant action or plot twists."
)


@pytest.fixture
def report_guard(monkeypatch):
    """Turn the per-address report guard on, with the address read from a test header."""
    monkeypatch.setattr(visitor_identity, "REPORT_ADDRESS_GUARD", True)
    monkeypatch.setattr(visitor_identity, "client_address",
                        lambda request: request.headers.get("x-test-address", "203.0.113.1"))
    visitor_identity.clear_report_addresses()
    yield
    visitor_identity.clear_report_addresses()


def _public_review(db_session, username):
    user = db_session.query(models.User).filter(models.User.username == username).one()
    user.reviews_public = True
    movie = crud.create_movie(db_session, user.id, MovieCreate(
        title="Report Guard Movie", director="Safety Director", year=2026, rating=8,
        review=REVIEW_TEXT, review_public=True))
    db_session.commit()
    return movie


def _fresh_visitor(client):
    client.cookies.delete(visitor_identity.VISITOR_COOKIE)


class TestOnePersonCannotUnlistAlone:
    def test_review_reports_from_one_address_count_once(self, client, db_session, authenticated_client,
                                                        test_user_data, report_guard):
        movie = _public_review(db_session, test_user_data["username"])
        endpoint = f"/api/public/reviews/movie/{movie.id}/report"
        results = []
        for reason in ("spam", "harassment", "personal_information", "other"):
            _fresh_visitor(client)
            results.append(client.post(endpoint, json={"reason": reason}).json())

        assert all(result["visibility"] == "visible" for result in results)
        assert [result["duplicate"] for result in results] == [False, True, True, True]
        assert db_session.query(models.PublicReviewReport).count() == 1
        assert client.get(f"/api/public/reviews/{movie.id}?category=movie").status_code == 200

    def test_review_reports_from_three_addresses_still_unlist(self, client, db_session, authenticated_client,
                                                              test_user_data, report_guard):
        movie = _public_review(db_session, test_user_data["username"])
        endpoint = f"/api/public/reviews/movie/{movie.id}/report"
        results = []
        for address in ("198.51.100.1", "198.51.100.2", "198.51.100.3"):
            _fresh_visitor(client)
            results.append(client.post(endpoint, json={"reason": "spam"},
                                       headers={"x-test-address": address}).json())

        assert [result["visibility"] for result in results] == ["visible", "visible", "unlisted"]
        assert client.get(f"/api/public/reviews/{movie.id}?category=movie").status_code == 404

    def test_an_edited_review_can_be_reported_again_from_the_same_address(
            self, client, db_session, authenticated_client, test_user_data, report_guard):
        movie = _public_review(db_session, test_user_data["username"])
        endpoint = f"/api/public/reviews/movie/{movie.id}/report"
        assert client.post(endpoint, json={"reason": "spam"}).json()["duplicate"] is False

        stored = db_session.get(models.Movie, movie.id)
        stored.review = REVIEW_TEXT + " On a second watch the score is what stays with me most."
        db_session.commit()
        _fresh_visitor(client)
        assert client.post(endpoint, json={"reason": "spam"}).json()["duplicate"] is False

    def test_collection_public_page_and_share_link_share_one_count(
            self, authenticated_client, db_session, test_movie_data, test_anime_data, test_book_data, report_guard):
        collection, _, _ = _publish_three_item_collection(
            authenticated_client, test_movie_data, test_anime_data, test_book_data)
        link = authenticated_client.post(f"/collections/{collection['id']}/link").json()["link_url"]
        link_path = "/collections/link/" + link.rstrip("/").rsplit("/", 1)[1]

        outcomes = []
        for endpoint in (f"{collection['public_url']}/report", f"{link_path}/report",
                         f"{collection['public_url']}/report", f"{link_path}/report"):
            _fresh_visitor(authenticated_client)
            outcomes.append(authenticated_client.post(endpoint, json={"reason": "spam"}).json())

        assert [item["duplicate"] for item in outcomes] == [False, True, True, True]
        assert all(item["visibility"] == "visible" for item in outcomes)
        db_session.expire_all()
        assert db_session.get(models.Collection, collection["id"]).report_count == 1
        assert authenticated_client.get(collection["public_url"]).status_code == 200

    def test_guard_forgets_old_entries_and_stays_bounded(self, monkeypatch):
        monkeypatch.setattr(visitor_identity, "REPORT_ADDRESS_GUARD", True)
        monkeypatch.setattr(visitor_identity, "REPORT_ADDRESS_MAX_ENTRIES", 3)
        monkeypatch.setattr(visitor_identity, "client_address", lambda request: "192.0.2.9")
        visitor_identity.clear_report_addresses()
        try:
            assert visitor_identity.first_report_from_address(None, "review:a", now=0) is True
            assert visitor_identity.first_report_from_address(None, "review:a", now=10) is False
            week = visitor_identity.REPORT_ADDRESS_TTL_SECONDS
            assert visitor_identity.first_report_from_address(None, "review:a", now=week + 1) is True
            for index in range(5):
                visitor_identity.first_report_from_address(None, f"review:{index}", now=week + 2)
            assert len(visitor_identity._report_addresses) == 3
            # The stored key is a keyed hash; the address itself is never kept.
            assert not any("192.0.2.9" in key for key in visitor_identity._report_addresses)
        finally:
            visitor_identity.clear_report_addresses()

    def test_guard_is_off_in_tests_by_default(self):
        assert visitor_identity.REPORT_ADDRESS_GUARD is False


@pytest.fixture
def notices(monkeypatch):
    sent = []

    async def record(email, username, subject, headline, body):
        sent.append({"email": email, "username": username, "subject": subject, "body": body})

    monkeypatch.setattr(email_utils, "send_security_notice_email", record)
    return sent


class TestSecurityNoticeEmails:
    def test_password_change_emails_the_account(self, authenticated_client, test_user_data, notices):
        response = authenticated_client.put("/account/password", json={
            "current_password": test_user_data["password"], "new_password": "a-brand-new-passphrase-42"})
        assert response.status_code == 200
        assert [(n["email"], n["subject"]) for n in notices] == [
            (test_user_data["email"], "Your OmniTrackr password was changed")]

    def test_wrong_current_password_sends_nothing(self, authenticated_client, notices):
        response = authenticated_client.put("/account/password", json={
            "current_password": "not-the-password", "new_password": "a-brand-new-passphrase-42"})
        assert response.status_code == 400
        assert notices == []

    def test_password_reset_emails_the_account(self, client, db_session, authenticated_client,
                                               test_user_data, notices):
        from datetime import datetime, timedelta, timezone
        from app import auth
        token = email_utils.generate_reset_token(test_user_data["email"])
        user = db_session.query(models.User).filter_by(email=test_user_data["email"]).one()
        user.reset_token = auth.hash_token(token)
        user.reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        db_session.commit()

        response = client.post("/auth/reset-password", json={"token": token, "new_password": "reset-passphrase-9876"})
        assert response.status_code == 200, response.text
        assert [(n["email"], n["subject"]) for n in notices] == [
            (test_user_data["email"], "Your OmniTrackr password was reset")]

    def test_email_change_tells_the_old_address(self, client, db_session, authenticated_client,
                                                test_user_data, notices):
        response = authenticated_client.put("/account/email", json={
            "new_email": "moved@example.com", "password": test_user_data["password"]})
        assert response.status_code == 200
        user = db_session.query(models.User).filter_by(email=test_user_data["email"]).one()
        token = user.verification_token.split(":", 2)[1]

        confirmed = client.get("/auth/verify-email", params={"token": token})
        assert confirmed.status_code == 200, confirmed.text
        assert len(notices) == 1
        assert notices[0]["email"] == test_user_data["email"]
        assert "moved@example.com" in notices[0]["body"]

    def test_notice_html_escapes_the_new_address(self, monkeypatch):
        import asyncio
        captured = {}
        monkeypatch.setattr(email_utils, "html_message",
                            lambda subject, recipients, html, headers=None: captured.update(html=html))
        monkeypatch.setattr(email_utils.conf, "MAIL_USERNAME", "")
        asyncio.run(email_utils.send_security_notice_email(
            "old@example.com", "<b>sam</b>", *email_utils.email_changed_notice('x"<script>@example.com')))
        assert "<script>" not in captured["html"]
        assert "&lt;b&gt;sam&lt;/b&gt;" in captured["html"]

    def test_a_failed_notice_never_breaks_the_change(self, monkeypatch, authenticated_client, test_user_data):
        async def broken(*args):
            raise RuntimeError("smtp down")

        monkeypatch.setattr(email_utils, "send_security_notice_email", broken)
        response = authenticated_client.put("/account/password", json={
            "current_password": test_user_data["password"], "new_password": "a-brand-new-passphrase-42"})
        assert response.status_code == 200


def test_legacy_review_page_escapes_quotes_in_attributes():
    script = (ROOT / "app/static/review_detail.js").read_text()
    body = script[script.index("function escapeHtml"):]
    body = body[:body.index("\n}\n")]
    assert "&quot;" in body and "&#39;" in body and "innerHTML" not in body
    template = (ROOT / "app/templates/review_detail.html").read_text()
    assert "review_detail.js?v=20261115-review-quotes-" in template
