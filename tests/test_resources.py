"""Tests of the areas of the API that the first version covers: auth and health."""

from typing import TYPE_CHECKING

import pytest

from .conftest import USER_ID, Api, me

if TYPE_CHECKING:
    from pylekto import LektoClient


async def test_me(api: Api, lekto: LektoClient) -> None:
    """``auth.me`` reads the caller."""
    api.answer("GET", "/auth/me", json=me())
    answer = await lekto.auth.me()
    assert str(answer.user.id) == USER_ID
    assert answer.user.display_name == "Jane Doe"
    assert answer.token_scope == "read"


@pytest.mark.parametrize(("status", "state"), [(200, "ok"), (503, "degraded")])
async def test_health(api: Api, lekto: LektoClient, status: int, state: str) -> None:
    """``health.get`` returns the state, also when Lekto answers 503."""
    checks = {"database": "ok", "object_store": "ok" if state == "ok" else "failed"}
    api.answer("GET", "/health", status, json={"status": state, "checks": checks})
    health = await lekto.health.get()
    assert health.status == state
    assert health.checks == checks
