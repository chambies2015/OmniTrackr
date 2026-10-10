"""Public privacy, browser-origin and pre-parser body limits."""
import pytest
from fastapi import FastAPI, Request
from starlette import formparsers
from app import auth, models
from app.middleware import RequestBodyLimitMiddleware


def member(db, name, **kwargs):
    user = models.User(username=name, email=f"private-{name}@example.com",
                       hashed_password=auth.get_password_hash("tea on the porch"), is_verified=True, is_active=True, **kwargs)
    db.add(user)
    db.commit()
    return user


def headers(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}"}


def test_friend_request_and_friendship_responses_never_disclose_email(client, db_session):
    sender, receiver = member(db_session, "sender"), member(db_session, "receiver")
    response = client.post("/friends/request", json={"receiver_username": receiver.username}, headers=headers(sender))
    assert response.status_code == 200
    for key in ("sender", "receiver"):
        assert set(response.json()[key]) == {"id", "username", "profile_picture_url"}
    request_id = response.json()["id"]
    for viewer in (sender, receiver):
        pending = client.get("/friends/requests", headers=headers(viewer))
        assert sender.email not in pending.text and receiver.email not in pending.text
    accepted = client.post(f"/friends/requests/{request_id}/accept", headers=headers(receiver))
    assert accepted.status_code == 200 and sender.email not in accepted.text and receiver.email not in accepted.text
    friends = client.get("/friends", headers=headers(sender))
    assert friends.status_code == 200
    assert friends.json()[0]["friend"]["username"] == receiver.username
    assert receiver.email not in friends.text
    assert client.get("/account/me", headers=headers(receiver)).json()["email"] == receiver.email


@pytest.mark.parametrize("browser_headers", [
    {"Origin": "https://attacker.example"}, {"Origin": "null"},
    {"Origin": "http://testserver.attacker.example"}, {"Origin": "http://testserver@attacker.example"},
    {"Origin": "http://testserver/path"}, {"Origin": "http://testserver https://attacker.example"},
    {"Referer": "https://attacker.example/form"}, {"Sec-Fetch-Site": "cross-site"},
])
def test_foreign_browser_login_is_rejected_without_setting_session(client, db_session, browser_headers):
    user = member(db_session, "login_user")
    result = client.post("/auth/login", data={"username": user.username, "password": "tea on the porch"}, headers=browser_headers)
    assert result.status_code == 403
    assert auth.AUTH_COOKIE_NAME not in result.cookies
    assert client.get("/account/me").status_code == 401


@pytest.mark.parametrize("browser_headers", [
    {}, {"Origin": "http://testserver"}, {"Origin": "http://testserver:80"},
    {"Referer": "http://testserver/form?next=account"},
])
def test_same_origin_and_native_login_still_work(client, db_session, browser_headers):
    user = member(db_session, "legit_login")
    result = client.post("/auth/login", data={"username": user.username, "password": "tea on the porch"}, headers=browser_headers)
    assert result.status_code == 200
    assert auth.AUTH_COOKIE_NAME in result.cookies
    assert client.get("/account/me").status_code == 200


def test_explicit_trusted_cors_origin_works_behind_https_proxy(client, db_session, monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://www.omnitrackr.xyz")
    user = member(db_session, "proxy_login")
    result = client.post("/auth/login", data={"username": user.username, "password": "tea on the porch"},
                         headers={"Origin": "https://www.omnitrackr.xyz", "Sec-Fetch-Site": "cross-site"})
    assert result.status_code == 200


def test_cross_site_cookie_write_is_blocked(client, db_session):
    user = member(db_session, "cookie_writer")
    client.cookies.set(auth.AUTH_COOKIE_NAME, auth.create_user_access_token(user))
    result = client.put("/account/privacy", json={"movies_private": True}, headers={"Origin": "https://attacker.example"})
    assert result.status_code == 403
    db_session.refresh(user)
    assert not user.movies_private


def test_opaque_origin_requires_development_opt_in(client, db_session, monkeypatch):
    monkeypatch.setenv("ALLOW_NULL_ORIGIN", "true")
    monkeypatch.setenv("ENVIRONMENT", "production")
    user = member(db_session, "opaque_login")
    payload = {"username": user.username, "password": "tea on the porch"}
    assert client.post("/auth/login", data=payload, headers={"Origin": "null"}).status_code == 403
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert client.post("/auth/login", data=payload, headers={"Origin": "null"}).status_code == 200


def test_uploaded_profile_picture_respects_owner_friend_public_and_active_state(client, db_session):
    owner = member(db_session, "picture_owner", profile_picture_data=b"test-webp", profile_picture_mime_type="image/webp")
    friend, stranger = member(db_session, "picture_friend"), member(db_session, "picture_stranger")
    db_session.add(models.Friendship(user1_id=owner.id, user2_id=friend.id))
    db_session.commit()
    path = f"/profile-pictures/{owner.id}"
    assert client.get(path).status_code == 404
    assert client.get(path, headers=headers(stranger)).status_code == 404
    assert client.get(path, headers=headers(owner)).content == b"test-webp"
    assert client.get(path, headers=headers(friend)).status_code == 200
    db_session.add(models.PublicProfile(user_id=owner.id, enabled=True))
    db_session.commit()
    assert client.get(path).status_code == 200
    owner.is_active = False
    db_session.commit()
    assert client.get(path).status_code == 404
    assert client.get(path, headers=headers(friend)).status_code == 404


async def invoke(app, chunks, extra_headers=()):
    incoming = [{"type": "http.request", "body": body, "more_body": index < len(chunks) - 1}
                for index, body in enumerate(chunks)]
    output = []
    async def receive():
        return incoming.pop(0) if incoming else {"type": "http.disconnect"}
    async def send(message):
        output.append(message)
    scope = {"type": "http", "method": "POST", "path": "/parse", "raw_path": b"/parse", "query_string": b"",
             "scheme": "http", "server": ("testserver", 80), "client": ("testclient", 123), "root_path": "",
             "http_version": "1.1", "headers": list(extra_headers)}
    await app(scope, receive, send)
    return output


@pytest.mark.asyncio
async def test_body_length_is_rejected_before_endpoint_or_receiving_bytes():
    reached = []
    async def app(scope, receive, send):
        reached.append(True)
    messages = await invoke(RequestBodyLimitMiddleware(app, max_body_bytes=16), [b"unused"], [(b"content-length", b"17")])
    assert messages[0]["status"] == 413
    assert not reached


@pytest.mark.asyncio
async def test_chunked_body_over_limit_is_rejected_even_without_length():
    seen = []
    async def app(scope, receive, send):
        while True:
            message = await receive()
            seen.append(message["body"])
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})
    messages = await invoke(RequestBodyLimitMiddleware(app, max_body_bytes=16), [b"a" * 10, b"b" * 10])
    assert messages[0]["status"] == 413
    assert seen == [b"a" * 10]
    allowed = await invoke(RequestBodyLimitMiddleware(app, max_body_bytes=16), [b"a" * 8, b"b" * 8])
    assert allowed[0]["status"] == 200


@pytest.mark.asyncio
async def test_multipart_limit_closes_files_spooled_before_excess_chunk(monkeypatch):
    spooled = []
    original = formparsers.SpooledTemporaryFile
    def record(*args, **kwargs):
        file = original(*args, **kwargs)
        spooled.append(file)
        return file
    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", record)
    app = FastAPI()
    @app.post("/parse")
    async def parse(request: Request):
        async with request.form():
            return {"ok": True}
    prefix = b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="test.bin"\r\nContent-Type: application/octet-stream\r\n\r\n' + b'a' * 128
    messages = await invoke(RequestBodyLimitMiddleware(app, max_body_bytes=512),
                            [prefix, b'b' * 1024 + b'\r\n--boundary--\r\n'],
                            [(b"content-type", b"multipart/form-data; boundary=boundary")])
    assert messages[0]["status"] == 413
    assert spooled and all(file.closed for file in spooled)


UPLOAD_PATHS = ["/account/profile-picture", "/custom-tabs/1/items/1/poster", "/import/file/",
                "/import-studio/preview/", "/import-studio/apply/"]


@pytest.mark.parametrize("path", UPLOAD_PATHS)
def test_anonymous_uploads_never_create_multipart_files(client, monkeypatch, path):
    spooled = []
    original = formparsers.SpooledTemporaryFile
    def record(*args, **kwargs):
        file = original(*args, **kwargs)
        spooled.append(file)
        return file
    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", record)
    result = client.post(path, files={"file": ("large.bin", b"x" * (2 * 1024 * 1024))})
    assert result.status_code == 401
    assert result.headers["www-authenticate"] == "Bearer"
    assert not spooled


@pytest.mark.parametrize("kind", ["invalid", "inactive", "revoked"])
def test_invalid_upload_sessions_rejected_before_parser(client, db_session, monkeypatch, kind):
    user = member(db_session, "upload_user")
    token = auth.create_user_access_token(user)
    if kind == "inactive":
        user.is_active = False
    elif kind == "revoked":
        user.hashed_password = auth.get_password_hash("a different long password")
    else:
        token = "invalid-token"
    db_session.commit()
    def never(*args, **kwargs):
        pytest.fail("unauthorized upload entered the multipart parser")
    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", never)
    result = client.post("/account/profile-picture", headers={"Authorization": f"Bearer {token}"},
                         files={"file": ("large.bin", b"x" * (2 * 1024 * 1024))})
    assert result.status_code == 401


def test_authenticated_image_upload_enforces_route_cap_before_parser(client, db_session, monkeypatch):
    user = member(db_session, "upload_limit_user")
    def never(*args, **kwargs):
        pytest.fail("over-limit upload entered the multipart parser")
    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", never)
    for path in ("/account/profile-picture", "/custom-tabs/1/items/1/poster", "/import-studio/preview/"):
        result = client.post(path, content=b"unused", headers={**headers(user), "Content-Length": str(6 * 1024 * 1024 + 1),
                                                            "Content-Type": "multipart/form-data; boundary=test"})
        assert result.status_code == 413


def test_valid_cookie_upload_still_reaches_csv_preview(client, db_session):
    user = member(db_session, "cookie_upload")
    client.cookies.set(auth.AUTH_COOKIE_NAME, auth.create_user_access_token(user))
    result = client.post("/import-studio/preview/", files={"file": ("movies.csv", b"title,year\nA film,2024\n", "text/csv")},
                         data={"category": "movies"})
    assert result.status_code == 200
