"""Tests of LektoClient: connecting, the version, the token, closing."""

import warnings

import httpx2
import pytest

from pylekto import (
    API_VERSION,
    LEKTO_VERSION,
    LektoAuthenticationError,
    LektoClient,
    LektoResponseError,
    LektoVersionWarning,
)
from pylekto.client import _fits

from .conftest import TOKEN, URL, Api, me


async def test_connect_reads_the_versions(api: Api, http: httpx2.AsyncClient) -> None:
    """Connecting asks who calls and keeps the versions; the same API warns nothing."""
    api.answer("GET", "/auth/me", json=me())
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        async with LektoClient(URL, TOKEN, client=http) as lekto:
            assert lekto.lekto_version == LEKTO_VERSION
            assert lekto.api_version == API_VERSION


async def test_another_lekto_with_the_same_api_warns_nothing(api: Api, lekto: LektoClient) -> None:
    """Another Lekto release that speaks the same API needs no warning."""
    api.answer("GET", "/auth/me", json=me(lekto_version="0.99.0"))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        answer = await lekto.connect()
    assert answer.lekto_version == "0.99.0"
    assert lekto.lekto_version == "0.99.0"


async def test_another_api_warns(api: Api, lekto: LektoClient) -> None:
    """An API version that may not fit gives a warning that names both versions."""
    api.answer("GET", "/auth/me", json=me(lekto_version="0.99.0", api_version="0.98"))
    with pytest.warns(
        LektoVersionWarning, match=rf"0\.99\.0 answers with the API 0\.98;.* {API_VERSION} "
    ):
        answer = await lekto.connect()
    assert answer.api_version == "0.98"
    assert lekto.api_version == "0.98"


async def test_a_lekto_without_an_api_version_warns(api: Api, lekto: LektoClient) -> None:
    """A Lekto before 0.16 names no API version: the warning says why its answer does not fit."""
    answer = me(lekto_version="0.15.5")
    del answer["api_version"]
    api.answer("GET", "/auth/me", json=answer)
    with (
        pytest.warns(LektoVersionWarning, match=r"0\.15\.5 answers with no API version"),
        pytest.raises(LektoResponseError),
    ):
        await lekto.connect()


async def test_an_answer_that_is_no_json_warns(api: Api, lekto: LektoClient) -> None:
    """A page that is no JSON (a proxy's) names no API version either."""
    api.answer("GET", "/auth/me", content=b"<html>Muster Proxy</html>")
    with (
        pytest.warns(LektoVersionWarning, match=r"^Lekto answers with no API version"),
        pytest.raises(LektoResponseError),
    ):
        await lekto.connect()


@pytest.mark.parametrize(
    ("answered", "spoken", "fits"),
    [
        ("0.2", "0.2", True),
        ("0.3", "0.2", False),
        ("0.1", "0.2", False),
        ("1.0", "0.2", False),
        ("0.2", "1.0", False),
        ("1.0", "1.0", True),
        ("1.3", "1.1", True),
        ("1.0", "1.1", False),
        ("2.0", "1.0", False),
        ("1.0", "2.0", False),
        ("1.0.1", "1.0", False),
        ("v1.0", "1.0", False),
        ("", "1.0", False),
    ],
)
def test_which_api_versions_fit(answered: str, spoken: str, *, fits: bool) -> None:
    """During the beta only the same MINOR fits; from 1.0 the same MAJOR, at least our MINOR."""
    assert _fits(answered, spoken) is fits


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
