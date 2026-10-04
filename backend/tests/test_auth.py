import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_success(async_client: AsyncClient):
    payload = {
        "email": "candidate1@example.com",
        "name": "Alex Candidate",
        "password": "Password123",
        "role": "candidate",
    }
    response = await async_client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "candidate1@example.com"
    assert data["name"] == "Alex Candidate"
    assert data["role"] == "candidate"
    assert "password" not in data
    assert "password_hash" not in data
    assert "id" in data


@pytest.mark.asyncio
async def test_signup_duplicate_email(async_client: AsyncClient):
    payload = {
        "email": "duplicate@example.com",
        "name": "First User",
        "password": "Password123",
        "role": "candidate",
    }
    res1 = await async_client.post("/api/v1/auth/signup", json=payload)
    assert res1.status_code == 201

    res2 = await async_client.post("/api/v1/auth/signup", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_signup_password_validation(async_client: AsyncClient):
    # Too short (< 8 chars)
    res_short = await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "short@example.com",
            "name": "Short Pwd",
            "password": "Pass1",
            "role": "candidate",
        },
    )
    assert res_short.status_code == 422

    # No digits
    res_no_digit = await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "nodigit@example.com",
            "name": "No Digit",
            "password": "PasswordOnly",
            "role": "candidate",
        },
    )
    assert res_no_digit.status_code == 422


@pytest.mark.asyncio
async def test_login_and_auth_me(async_client: AsyncClient):
    # 1. Signup
    signup_payload = {
        "email": "auth_me@example.com",
        "name": "Sam Student",
        "password": "SecurePassword456",
        "role": "candidate",
    }
    signup_res = await async_client.post("/api/v1/auth/signup", json=signup_payload)
    assert signup_res.status_code == 201

    # 2. Login
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "auth_me@example.com", "password": "SecurePassword456"},
    )
    assert login_res.status_code == 200
    tokens = login_res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"

    # 3. Access /auth/me with Bearer token
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me_res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == "auth_me@example.com"
    assert me_data["role"] == "candidate"

    # 4. Access /auth/me without token -> 401
    unauth_res = await async_client.get("/api/v1/auth/me")
    assert unauth_res.status_code == 401 or unauth_res.status_code == 403


@pytest.mark.asyncio
async def test_refresh_token_flow(async_client: AsyncClient):
    # Signup and login
    await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "refresher@example.com",
            "name": "Refresh User",
            "password": "Password789",
            "role": "candidate",
        },
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "refresher@example.com", "password": "Password789"},
    )
    refresh_token = login_res.json()["refresh_token"]

    # Exchange refresh token
    refresh_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200
    new_tokens = refresh_res.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens

    # Verify new access token works
    headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
    me_res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200


@pytest.mark.asyncio
async def test_role_based_access_control(async_client: AsyncClient):
    # Register Candidate
    await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "cand@example.com",
            "name": "Candidate User",
            "password": "Password123",
            "role": "candidate",
        },
    )
    cand_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "cand@example.com", "password": "Password123"},
    )
    cand_token = cand_login.json()["access_token"]
    cand_headers = {"Authorization": f"Bearer {cand_token}"}

    # Register Admin
    await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "admin@example.com",
            "name": "Admin Invigilator",
            "password": "Password123",
            "role": "admin",
        },
    )
    admin_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Password123"},
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Register Grader
    await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "grader@example.com",
            "name": "Grader Specialist",
            "password": "Password123",
            "role": "grader",
        },
    )
    grader_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "grader@example.com", "password": "Password123"},
    )
    grader_token = grader_login.json()["access_token"]
    grader_headers = {"Authorization": f"Bearer {grader_token}"}

    # Test Admin-Only Route
    # Candidate -> 403 Forbidden
    cand_res = await async_client.get("/api/v1/auth/admin-only", headers=cand_headers)
    assert cand_res.status_code == 403

    # Grader -> 403 Forbidden
    grader_res = await async_client.get("/api/v1/auth/admin-only", headers=grader_headers)
    assert grader_res.status_code == 403

    # Admin -> 200 OK
    admin_res = await async_client.get("/api/v1/auth/admin-only", headers=admin_headers)
    assert admin_res.status_code == 200

    # Test Grader-Only Route (accessible to Grader and Admin)
    # Candidate -> 403 Forbidden
    cand_res2 = await async_client.get("/api/v1/auth/grader-only", headers=cand_headers)
    assert cand_res2.status_code == 403

    # Grader -> 200 OK
    grader_res2 = await async_client.get("/api/v1/auth/grader-only", headers=grader_headers)
    assert grader_res2.status_code == 200

    # Admin -> 200 OK
    admin_res2 = await async_client.get("/api/v1/auth/grader-only", headers=admin_headers)
    assert admin_res2.status_code == 200
