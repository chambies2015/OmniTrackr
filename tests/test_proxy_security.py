"""Security and error-contract tests for external metadata proxies."""
import httpx


class _MockClient:
    def __init__(self, response):
        self.response = response

    async def get(self, *args, **kwargs):
        return self.response


def test_proxy_requires_authentication(client):
    response = client.get("/api/proxy/jikan", params={"query": "Cowboy Bebop"})

    assert response.status_code == 401


def test_proxy_preserves_upstream_rate_limit(authenticated_client):
    request = httpx.Request("GET", "https://api.jikan.moe/v4/anime")
    upstream = httpx.Response(429, request=request)

    app = authenticated_client.app
    real_client = app.state.external_api_client
    app.state.external_api_client = _MockClient(upstream)
    try:
        response = authenticated_client.get("/api/proxy/jikan", params={"query": "Cowboy Bebop"})
    finally:
        app.state.external_api_client = real_client

    assert response.status_code == 429
    assert response.json()["detail"] == "Jikan API rate limit reached"


class _RecordingClient:
    def __init__(self):
        self.calls = []

    async def get(self, url, params=None, **kwargs):
        self.calls.append(params)
        return httpx.Response(200, json={"data": []}, request=httpx.Request("GET", url))


def test_jikan_proxy_returns_one_match_unless_a_few_are_asked_for(authenticated_client):
    app = authenticated_client.app
    real_client = app.state.external_api_client
    recorder = _RecordingClient()
    app.state.external_api_client = recorder
    try:
        assert authenticated_client.get("/api/proxy/jikan", params={"query": "Frieren"}).status_code == 200
        assert authenticated_client.get("/api/proxy/jikan", params={"query": "Frieren", "limit": 5}).status_code == 200
        assert authenticated_client.get("/api/proxy/jikan", params={"query": "Frieren", "limit": 50}).status_code == 422
    finally:
        app.state.external_api_client = real_client

    assert [call["limit"] for call in recorder.calls] == [1, 5]
