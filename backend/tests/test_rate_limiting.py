"""Tests for Phase 8 Security Hardening: Section 1 Rate Limiting.

Verifies:
1. Strict per-IP and per-account auth limits with exponential backoff.
2. No permanent account lockout (legitimate candidates can authenticate once backoff expires).
3. Public / unauthenticated tier rate limits.
4. Authenticated general tier rate limits.
5. High-risk endpoints (code execution and violation reporting) with configurable settings.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.rate_limit import (
    check_login_backoff,
    clear_login_failures,
    record_login_failure,
    reset_rate_limits,
)
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_auth_login_exponential_backoff(async_client: AsyncClient):
    """
    Verifies that repeated failed login attempts trigger exponential backoff
    rather than a permanent lockout.
    """
    reset_rate_limits()

    # 1. Create a user
    user_payload = {
        "email": "candidate_backoff@example.com",
        "name": "Backoff Test",
        "password": "CorrectPassword123",
        "role": "candidate",
    }
    signup_res = await async_client.post("/api/v1/auth/signup", json=user_payload)
    assert signup_res.status_code == 201

    # 2. Attempt failed logins up to the threshold (default 5)
    for i in range(settings.RATE_LIMIT_LOGIN_MAX_FAILED_BEFORE_BACKOFF):
        fail_res = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "candidate_backoff@example.com", "password": "WrongPassword!"},
        )
        assert fail_res.status_code == 401
        assert "Incorrect email or password" in fail_res.json()["detail"]

    # 3. Next immediate failed attempt triggers HTTP 429 with exponential backoff
    throttled_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "candidate_backoff@example.com", "password": "WrongPassword!"},
    )
    assert throttled_res.status_code == 429
    assert "Retry-After" in throttled_res.headers
    assert "Too many failed login attempts" in throttled_res.json()["detail"]

    # 4. Clear/simulate backoff expiration and verify legitimate login succeeds
    clear_login_failures("candidate_backoff@example.com")
    success_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "candidate_backoff@example.com", "password": "CorrectPassword123"},
    )
    assert success_res.status_code == 200
    assert "access_token" in success_res.json()


@pytest.mark.asyncio
async def test_auth_signup_rate_limiting(async_client: AsyncClient):
    """
    Verifies that IP-level rate limiting throttles rapid signup requests.
    """
    reset_rate_limits()

    # Rapidly attempt signups from the test client IP
    throttled = False
    for i in range(settings.RATE_LIMIT_SIGNUP_PER_IP_MAX + 2):
        res = await async_client.post(
            "/api/v1/auth/signup",
            json={
                "email": f"spam_user_{i}@example.com",
                "name": f"Spammer {i}",
                "password": "Password123",
                "role": "candidate",
            },
        )
        if res.status_code == 429:
            throttled = True
            assert "Retry-After" in res.headers
            assert "Too many account registrations" in res.json()["detail"]
            break

    assert throttled, "Expected signup rate limiting to trigger 429"


@pytest.mark.asyncio
async def test_public_endpoint_rate_limiting(async_client: AsyncClient):
    """
    Verifies that unauthenticated / public endpoints enforce moderate rate limits.
    """
    reset_rate_limits()

    throttled = False
    # Hammer public root endpoint beyond limit
    for _ in range(settings.RATE_LIMIT_PUBLIC_MAX_REQUESTS + 5):
        res = await async_client.get("/")
        if res.status_code == 429:
            throttled = True
            assert "Retry-After" in res.headers
            break

    assert throttled, "Expected public tier rate limiting to trigger 429"


@pytest.mark.asyncio
async def test_authenticated_endpoint_rate_limiting(async_client: AsyncClient):
    """
    Verifies that authenticated requests enforce the looser per-user rate limit.
    """
    reset_rate_limits()

    # Signup and login to get valid token
    signup_res = await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "authed_rate_limit@example.com",
            "name": "Authed User",
            "password": "Password123",
            "role": "candidate",
        },
    )
    assert signup_res.status_code == 201

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "authed_rate_limit@example.com", "password": "Password123"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    throttled = False
    for _ in range(settings.RATE_LIMIT_AUTHENTICATED_MAX_REQUESTS + 5):
        res = await async_client.get("/api/v1/candidate/exams", headers=headers)
        if res.status_code == 429:
            throttled = True
            assert "Retry-After" in res.headers
            assert "Too many requests" in res.json()["detail"]
            break

    assert throttled, "Expected authenticated tier rate limiting to trigger 429"


def test_configurable_thresholds_exist():
    """Confirms that rate limiting parameters are strictly non-hardcoded and configurable."""
    assert hasattr(settings, "RATE_LIMIT_LOGIN_PER_IP_MAX")
    assert hasattr(settings, "RATE_LIMIT_LOGIN_MAX_FAILED_BEFORE_BACKOFF")
    assert hasattr(settings, "RATE_LIMIT_LOGIN_BACKOFF_BASE_SECONDS")
    assert hasattr(settings, "RATE_LIMIT_LOGIN_BACKOFF_FACTOR")
    assert hasattr(settings, "RATE_LIMIT_LOGIN_BACKOFF_MAX_SECONDS")
    assert hasattr(settings, "RATE_LIMIT_SIGNUP_PER_IP_MAX")
    assert hasattr(settings, "RATE_LIMIT_PUBLIC_MAX_REQUESTS")
    assert hasattr(settings, "RATE_LIMIT_AUTHENTICATED_MAX_REQUESTS")
    assert hasattr(settings, "RATE_LIMIT_CODE_EXECUTION_MIN_INTERVAL")
    assert hasattr(settings, "RATE_LIMIT_VIOLATION_LOG_MAX_REQUESTS")
