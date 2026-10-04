from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ConsentSubmissionRequest(BaseModel):
    status: str = Field(..., description="granted or declined")
    clauses_consented: List[str] = Field(default_factory=list, description="Clauses candidate explicitly checked")
    notice_version: str = Field(default="2023.1-dpdp", description="DPDP notice version string")


class ConsentResponse(BaseModel):
    status: str
    consent_id: Optional[UUID] = None
    timestamp: datetime
    message: str


class DataExportAccount(BaseModel):
    id: UUID
    name: str
    email: str
    role: str
    created_at: datetime


class DataExportSession(BaseModel):
    session_id: UUID
    exam_id: UUID
    exam_title: str
    started_at: datetime
    submitted_at: Optional[datetime] = None
    status: str
    score: Optional[float] = None
    trust_score: float
    review_status: str
    terminated_reason: Optional[str] = None
    violation_count: int


class DataExportViolation(BaseModel):
    id: UUID
    session_id: UUID
    violation_type: str
    severity: str
    timestamp: datetime
    review_status: str


class DataExportConsentLog(BaseModel):
    id: UUID
    exam_id: UUID
    status: str
    notice_version: str
    clauses_consented: Optional[List[str]] = None
    retention_days: int
    created_at: datetime


class DataExportPackage(BaseModel):
    data_fiduciary: str = "Proctor AI Examination Platform"
    jurisdiction: str = "Digital Personal Data Protection (DPDP) Act, 2023 (India)"
    data_residency: str = "AWS ap-south-1 (Mumbai, India)"
    retention_policy: str = "Proctoring evidence snapshots and biometric embeddings are purged after 90 days. Academic scores retained per institutional policy."
    exported_at: datetime
    account: DataExportAccount
    exam_sessions: List[DataExportSession]
    violations: List[DataExportViolation]
    consent_records: List[DataExportConsentLog]


class ErasureRequestCreate(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500, description="Optional explanation for erasure request")


class ErasureRequestResponse(BaseModel):
    request_id: UUID
    status: str
    requested_at: datetime
    message: str
