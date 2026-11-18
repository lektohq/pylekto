"""Tests of LektoClient: connecting, the version, the token, closing."""

import warnings

import httpx2
import pytest

from pylekto import (
    LEKTO_VERSION,
    LektoAuthenticationError,
    LektoClient,
    LektoVersionWarning,
)

from .conftest import TOKEN, URL, Api, me


async def test_connect_reads_the_version(api: Api, http: httpx2.AsyncClient) -> None:
    """Connecting asks who calls and keeps Lekto's version; the same version warns nothing."""
    api.answer("GET", "/auth/me", json=me())
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        async with LektoClient(URL, TOKEN, client=http) as lekto:
            assert lekto.lekto_version == LEKTO_VERSION


async def test_another_version_warns(api: Api, lekto: LektoClient) -> None:
    """Another Lekto version gives a warning that names both versions."""
    api.answer("GET", "/auth/me", json=me(lekto_version="0.99.0"))
    with pytest.warns(LektoVersionWarning, match=rf"0\.99\.0.*{LEKTO_VERSION}"):
        answer = await lekto.connect()
    assert answer.lekto_version == "0.99.0"
    assert lekto.lekto_version == "0.99.0"


@pytest.mark.parametrize("url", [URL, URL + "/"])
async def test_requests_go_below_the_api_with_the_token(
    api: Api, http: httpx2.AsyncClient, url: str
) -> None:
    """Every request goes below /api/v1 of the address and carries the token."""
    api.answer("GET", "/auth/me", json=me())
    await LektoClient(url, TOKEN, client=http).auth.me()
    request = api.requests[-1]
    assert str(request.url) == URL + "/api/v1/auth/me"
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"


async def test_shared_client_stays_open(api: Api, http: httpx2.AsyncClient) -> None:
    """A client passed in keeps its settings and stays open."""
    api.answer("GET", "/auth/me", json=me())
    async with LektoClient(URL, TOKEN, client=http):
        pass
    assert not http.is_closed
    assert "Authorization" not in http.headers


async def test_own_client_is_closed() -> None:
    """The client pylekto makes itself is closed with it."""
    lekto = LektoClient(URL, TOKEN)
    await lekto.close()
    assert lekto._client.is_closed


async def test_failed_connect_closes_own_client(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    """A refused connect closes the client pylekto made and raises."""
    made: list[httpx2.AsyncClient] = []
    original = httpx2.AsyncClient

    def client(**settings: object) -> httpx2.AsyncClient:
        made.append(original(transport=httpx2.MockTransport(api)))
        assert "timeout" in settings
        return made[-1]

    monkeypatch.setattr(httpx2, "AsyncClient", client)
    api.answer("GET", "/auth/me", 401, json={"title": "Unauthorized", "status": 401})
    with pytest.raises(LektoAuthenticationError):
        async with LektoClient(URL, TOKEN):
            pytest.fail("connected with an unknown token")
    assert made[0].is_closed
