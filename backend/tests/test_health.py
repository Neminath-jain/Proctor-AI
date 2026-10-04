import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_live_probe_unauthenticated(async_client: AsyncClient):
    """Container orchestrators and load balancers can hit /health/live without credentials."""
    response = await async_client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_diagnostics_endpoint_unauthenticated_rejected(async_client: AsyncClient):
    """Calling detailed infrastructure diagnostics without token must return 401."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_diagnostics_endpoint_candidate_rejected_with_403(async_client: AsyncClient):
    """Calling detailed infrastructure diagnostics with candidate role MUST be rejected with 403 Forbidden."""
    uid = uuid.uuid4().hex[:6]
    cand_email = f"candidate_{uid}@example.com"
    await async_client.post(
        "/api/v1/auth/signup",
        json={"email": cand_email, "name": "Candidate", "password": "Password123", "role": "candidate"},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": cand_email, "password": "Password123"},
    )
    token = login_res.json()["access_token"]

    response = await async_client.get(
        "/api/v1/health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


@pytest.mark.asyncio
async def test_diagnostics_endpoint_admin_allowed(async_client: AsyncClient):
    """Calling detailed infrastructure diagnostics with admin role must succeed with 200."""
    uid = uuid.uuid4().hex[:6]
    admin_email = f"admin_{uid}@example.com"
    await async_client.post(
        "/api/v1/auth/signup",
        json={"email": admin_email, "name": "Administrator", "password": "Password123", "role": "admin"},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin_email, "password": "Password123"},
    )
    token = login_res.json()["access_token"]

    response = await async_client.get(
        "/api/v1/health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "postgres" in data["services"]
    assert "redis" in data["services"]
    assert "ml_service" in data["services"]
    assert "judge0" in data["services"]
