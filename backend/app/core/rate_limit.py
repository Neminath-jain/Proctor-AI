"""Phase 8 Rate Limiter & Abuse Prevention Engine.

Provides multi-tiered rate limiting and abuse mitigation:
1. Strict per-IP and per-account limits on auth routes (login, signup, refresh, reset)
   with exponential backoff on repeated failures (no permanent lockouts for candidates mid-exam).
2. Public / unauthenticated tier limits (per IP).
3. Authenticated general tier limits (per user session/token).
4. Configurable Phase 6 high-risk endpoints (Judge0 code runs, violation logging).
"""
import time
from collections import defaultdict
from threading import Lock
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, Request, status

from app.core.config import settings

# Thread-safe in-memory sliding logs
_timestamps_lock = Lock()
_action_logs: Dict[str, List[float]] = defaultdict(list)
_last_execution_time: Dict[str, float] = {}
_login_failures: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "last_failure": 0.0})


def get_client_ip(request: Request) -> str:
    """Extract client IP address respecting reverse proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First IP in comma-separated chain is the original client
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def check_rate_limit(
    key: str,
    action: str,
    max_requests: int,
    window_seconds: float,
    error_message: Optional[str] = None,
) -> None:
    """
    Sliding window rate limit check.
    Raises HTTPException 429 if `max_requests` exceeded within `window_seconds`.
    """
    now = time.time()
    lookup_key = f"{action}:{key}"

    with _timestamps_lock:
        timestamps = _action_logs[lookup_key]
        cutoff = now - window_seconds
        _action_logs[lookup_key] = [t for t in timestamps if t > cutoff]
        current_count = len(_action_logs[lookup_key])

        if current_count >= max_requests:
            oldest_in_window = _action_logs[lookup_key][0]
            retry_after = max(1, int(window_seconds - (now - oldest_in_window)))
            msg = (
                error_message
                or f"Rate limit exceeded for {action}. Please wait {retry_after}s before retrying."
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=msg,
                headers={"Retry-After": str(retry_after)},
            )

        _action_logs[lookup_key].append(now)


def record_login_failure(account_identifier: str, client_ip: Optional[str] = None) -> int:
    """
    Record a failed login attempt for an account identifier (email).
    Increments failure count and records timestamp for exponential backoff.
    """
    now = time.time()
    account_key = account_identifier.lower().strip()
    with _timestamps_lock:
        data = _login_failures[account_key]
        data["count"] += 1
        data["last_failure"] = now
        return data["count"]


def check_login_backoff(account_identifier: str) -> None:
    """
    Enforces exponential backoff for an account with repeated failed logins.
    Does NOT permanently lock out an account; requires exponential waiting delay.
    """
    now = time.time()
    account_key = account_identifier.lower().strip()

    with _timestamps_lock:
        data = _login_failures.get(account_key)
        if not data or data["count"] < settings.RATE_LIMIT_LOGIN_MAX_FAILED_BEFORE_BACKOFF:
            return

        excess = data["count"] - settings.RATE_LIMIT_LOGIN_MAX_FAILED_BEFORE_BACKOFF
        # Exponential backoff: base * (factor ^ excess), capped at max_seconds
        backoff_seconds = min(
            settings.RATE_LIMIT_LOGIN_BACKOFF_BASE_SECONDS * (settings.RATE_LIMIT_LOGIN_BACKOFF_FACTOR ** excess),
            settings.RATE_LIMIT_LOGIN_BACKOFF_MAX_SECONDS,
        )
        elapsed = now - data["last_failure"]

        if elapsed < backoff_seconds:
            retry_after = max(1, int(backoff_seconds - elapsed))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Too many failed login attempts for this account. "
                    f"Please wait {retry_after}s before trying again."
                ),
                headers={"Retry-After": str(retry_after)},
            )


def clear_login_failures(account_identifier: str, client_ip: Optional[str] = None) -> None:
    """Clear failed login attempts counter upon successful authentication."""
    account_key = account_identifier.lower().strip()
    with _timestamps_lock:
        _login_failures.pop(account_key, None)


def check_code_execution_rate_limit(
    session_id: str,
    min_interval_seconds: Optional[float] = None,
) -> None:
    """
    Ensures minimum delay between code execution requests per exam session.
    Prevents brute-forcing hidden test cases and protects Judge0 capacity.
    """
    interval = (
        min_interval_seconds
        if min_interval_seconds is not None
        else settings.RATE_LIMIT_CODE_EXECUTION_MIN_INTERVAL
    )
    now = time.time()
    key = str(session_id)

    with _timestamps_lock:
        last_time = _last_execution_time.get(key, 0.0)
        elapsed = now - last_time

        if elapsed < interval:
            wait_seconds = round(interval - elapsed, 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {wait_seconds}s before submitting another code execution.",
                headers={"Retry-After": str(max(1, int(wait_seconds)))},
            )

        _last_execution_time[key] = now


def check_violation_rate_limit(
    session_id: str,
    max_requests: Optional[int] = None,
    window_seconds: Optional[float] = None,
) -> None:
    """
    Prevents client scripts from flooding fake proctoring violation logs.
    """
    max_req = (
        max_requests
        if max_requests is not None
        else settings.RATE_LIMIT_VIOLATION_LOG_MAX_REQUESTS
    )
    window = (
        window_seconds
        if window_seconds is not None
        else settings.RATE_LIMIT_VIOLATION_LOG_WINDOW_SECONDS
    )
    check_rate_limit(
        key=str(session_id),
        action="violation_logging",
        max_requests=max_req,
        window_seconds=window,
        error_message="Too many proctoring events reported. Violation reporting is throttled.",
    )


def reset_rate_limits() -> None:
    """Reset rate limiter state (useful for tests)."""
    with _timestamps_lock:
        _action_logs.clear()
        _last_execution_time.clear()
        _login_failures.clear()
