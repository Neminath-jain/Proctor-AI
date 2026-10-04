"""Spending & Usage Quota Management Service.

Tracks and enforces daily API caps and storage volume to prevent runaway costs or abuse.
Uses Redis when available with seamless in-memory fallback.
"""
import time
import logging
from typing import Tuple
from datetime import datetime, timezone
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger("proctoring.quota")

# In-memory storage fallback for standalone / dev testing
_local_usage_store = {
    "day": "",
    "judge0_count": 0,
    "evidence_bytes": 0,
}


class QuotaService:
    @classmethod
    def _get_current_day_key(cls) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    @classmethod
    async def check_and_increment_judge0(cls) -> Tuple[bool, str]:
        """
        Check if today's Judge0 execution quota is within limit.
        Returns: (is_allowed, notice)
        """
        day = cls._get_current_day_key()
        max_cap = settings.DAILY_JUDGE0_EXECUTION_CAP

        try:
            r = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.3,
                socket_timeout=0.3,
            )
            redis_key = f"quota:judge0:{day}"
            current = await r.incr(redis_key)
            if current == 1:
                await r.expire(redis_key, 86400 * 2)
            await r.aclose()
        except Exception:
            # Fallback to local process store
            if _local_usage_store["day"] != day:
                _local_usage_store["day"] = day
                _local_usage_store["judge0_count"] = 0
            _local_usage_store["judge0_count"] += 1
            current = _local_usage_store["judge0_count"]

        if current > max_cap:
            logger.warning(
                f"Judge0 daily usage cap reached ({current}/{max_cap}). Diverting to sandbox fallback."
            )
            return False, f"Daily execution quota ({max_cap}) reached"

        if current >= int(max_cap * 0.8):
            logger.info(
                f"Judge0 quota alert: 80% threshold reached ({current}/{max_cap})."
            )

        return True, "OK"

    @classmethod
    async def record_evidence_bytes(cls, byte_count: int) -> Tuple[bool, str]:
        """Track daily evidence storage bytes."""
        day = cls._get_current_day_key()
        max_bytes = settings.DAILY_EVIDENCE_STORAGE_MB_CAP * 1024 * 1024

        try:
            r = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.3,
                socket_timeout=0.3,
            )
            redis_key = f"quota:evidence:{day}"
            total = await r.incrby(redis_key, byte_count)
            if total == byte_count:
                await r.expire(redis_key, 86400 * 2)
            await r.aclose()
        except Exception:
            if _local_usage_store["day"] != day:
                _local_usage_store["day"] = day
                _local_usage_store["evidence_bytes"] = 0
            _local_usage_store["evidence_bytes"] += byte_count
            total = _local_usage_store["evidence_bytes"]

        if total > max_bytes:
            logger.warning(f"Daily evidence storage cap exceeded: {total} / {max_bytes} bytes.")
            return False, "Daily evidence storage limit reached"

        return True, "OK"
