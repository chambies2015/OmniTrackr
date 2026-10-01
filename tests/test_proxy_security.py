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
