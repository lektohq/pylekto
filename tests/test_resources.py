"""Tests of who calls, the health of Lekto and its version."""

from typing import TYPE_CHECKING

from pylekto import API_VERSION, LEKTO_VERSION, LektoClient

if TYPE_CHECKING:
    from .conftest import Api


async def test_me(api: Api, lekto: LektoClient) -> None:
    """``auth.me`` reads the caller."""
    recorded = api.replay("auth_me")
    answer = await lekto.auth.me()
    assert str(answer.user.id) == recorded.body["user"]["id"]
    assert answer.user.role == "admin"
    assert answer.token_scope == "read_write"
    assert "admin:count_all" in answer.rights
    assert str(answer.instance_id) == recorded.body["instance_id"]
    assert answer.lekto_version == LEKTO_VERSION
    assert answer.api_version == API_VERSION


async def test_health(api: Api, lekto: LektoClient) -> None:
    """``health.get`` reads the state of Lekto and its services."""
    recorded = api.replay("health")
    health = await lekto.health.get()
    assert health.status == "ok"
    assert health.checks == recorded.body["checks"]


async def test_health_unavailable(api: Api, lekto: LektoClient) -> None:
    """``health.get`` returns the state also when Lekto answers 503."""
    checks = {"database": "ok", "object_store": "failed"}
    api.answer("GET", "/health", 503, json={"status": "degraded", "checks": checks})
    health = await lekto.health.get()
    assert health.status == "degraded"
    assert health.checks == checks


async def test_version(api: Api, lekto: LektoClient) -> None:
    """``version.get`` reads the versions of Lekto and its API and the newest release."""
    api.replay("version_get")
    version = await lekto.version.get()
    assert version.lekto_version == LEKTO_VERSION
    assert version.api_version == API_VERSION
    assert not version.update_available
