from typing import Dict, Optional
from pydantic import BaseModel


class ServiceStatus(BaseModel):
    status: str  # "healthy", "unhealthy", "degraded"
    latency_ms: Optional[float] = None
    details: Optional[str] = None


class HealthResponse(BaseModel):
    status: str  # "ok", "degraded", "error"
    version: str
    environment: str
    services: Dict[str, ServiceStatus]
