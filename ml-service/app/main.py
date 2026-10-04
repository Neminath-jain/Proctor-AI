import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.services.face_engine import FaceEngine
from app.services.audio_engine import AudioVADEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ml-service")

app = FastAPI(
    title="ML Proctoring Inference Service",
    version="0.2.0",
    description="Production-grade AI proctoring inference service for face detection, face-match verification, and voice activity detection (VAD).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engines on startup
face_engine = FaceEngine()
audio_engine = AudioVADEngine()


# --------------------------------------------------------------------------
# Request / Response Schemas
# --------------------------------------------------------------------------

class ExtractEmbeddingRequest(BaseModel):
    image_base64: str = Field(..., description="Base64 encoded reference snapshot JPEG/PNG")


class ExtractEmbeddingResponse(BaseModel):
    success: bool
    face_detected: bool
    face_count: int
    embedding: Optional[List[float]] = None
    error: Optional[str] = None


class EvaluateFrameRequest(BaseModel):
    frame_base64: str = Field(..., description="Base64 encoded periodic video frame JPEG/PNG")
    reference_embedding: Optional[List[float]] = Field(default=None, description="Candidate 128-d reference embedding")
    similarity_threshold: float = Field(default=0.60, ge=0.0, le=1.0, description="Minimum similarity threshold")


class FaceBoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int
    confidence: float


class EvaluateFrameResponse(BaseModel):
    face_count: int
    faces: List[FaceBoundingBox]
    similarity: Optional[float] = None
    anomaly: Optional[str] = None  # no_face_detected, multiple_faces_detected, face_mismatch, or None
    embedding: Optional[List[float]] = None


class EvaluateAudioRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64 encoded 3-5s audio chunk (WAV or 16-bit PCM)")
    sample_rate: int = Field(default=16000, description="Audio sampling rate in Hz")
    min_speech_duration: float = Field(default=0.5, description="Minimum duration to flag speech in seconds")


class EvaluateAudioResponse(BaseModel):
    speech_detected: bool
    speech_duration_seconds: float
    total_duration_seconds: float
    speech_ratio: float
    average_energy: float


# Legacy / stub compatibility
class InferenceRequest(BaseModel):
    session_id: str = Field(..., description="Active candidate exam session UUID")
    frame_base64: Optional[str] = Field(default=None, description="Base64 encoded JPEG/PNG frame")
    audio_chunk_base64: Optional[str] = Field(default=None, description="Base64 encoded audio slice")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AnomalyPrediction(BaseModel):
    violation_type: str
    confidence: float
    severity: str
    details: Dict[str, Any]


class InferenceResponse(BaseModel):
    session_id: str
    status: str
    anomalies_detected: bool
    predictions: List[AnomalyPrediction]


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for Docker Compose and Backend probing."""
    return {
        "status": "healthy",
        "service": "ml-service",
        "version": "0.2.0",
        "models_loaded": {
            "face_engine": "ready",
            "audio_engine": "ready",
            "detector": "haarcascade_frontalface",
            "embedder": "spatial_dct_128d",
        },
    }


@app.post(
    "/api/v1/ml/extract-embedding",
    response_model=ExtractEmbeddingResponse,
    tags=["Face Proctoring"],
    summary="Extract face embedding from reference photo during pre-exam verification",
)
async def extract_reference_embedding(payload: ExtractEmbeddingRequest) -> ExtractEmbeddingResponse:
    image = FaceEngine.decode_image_base64(payload.image_base64)
    if image is None:
        return ExtractEmbeddingResponse(
            success=False,
            face_detected=False,
            face_count=0,
            error="Invalid or corrupted base64 image data.",
        )

    faces = face_engine.detect_faces(image)
    if len(faces) == 0:
        return ExtractEmbeddingResponse(
            success=False,
            face_detected=False,
            face_count=0,
            error="No face detected in reference photo. Please face the camera directly in good lighting.",
        )
    elif len(faces) > 1:
        return ExtractEmbeddingResponse(
            success=False,
            face_detected=True,
            face_count=len(faces),
            error="Multiple faces detected in reference photo. Ensure only the candidate is in view.",
        )

    embedding = face_engine.extract_face_embedding(image, faces[0])
    if not embedding:
        return ExtractEmbeddingResponse(
            success=False,
            face_detected=True,
            face_count=1,
            error="Failed to extract facial feature embedding.",
        )

    return ExtractEmbeddingResponse(
        success=True,
        face_detected=True,
        face_count=1,
        embedding=embedding,
    )


@app.post(
    "/api/v1/ml/evaluate-frame",
    response_model=EvaluateFrameResponse,
    tags=["Face Proctoring"],
    summary="Evaluate periodic video frame for face presence, count, and candidate identity match",
)
async def evaluate_frame(payload: EvaluateFrameRequest) -> EvaluateFrameResponse:
    image = FaceEngine.decode_image_base64(payload.frame_base64)
    if image is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to decode frame_base64 image payload.",
        )

    result = face_engine.evaluate_frame(
        image=image,
        reference_embedding=payload.reference_embedding,
        similarity_threshold=payload.similarity_threshold,
    )

    boxes = [
        FaceBoundingBox(
            x=f["x"],
            y=f["y"],
            width=f["width"],
            height=f["height"],
            confidence=f.get("confidence", 0.95),
        )
        for f in result["faces"]
    ]

    return EvaluateFrameResponse(
        face_count=result["face_count"],
        faces=boxes,
        similarity=result["similarity"],
        anomaly=result["anomaly"],
        embedding=result["embedding"],
    )


@app.post(
    "/api/v1/ml/evaluate-audio",
    response_model=EvaluateAudioResponse,
    tags=["Audio Proctoring"],
    summary="Evaluate 3-5 second audio chunk for Voice Activity Detection (VAD)",
)
async def evaluate_audio(payload: EvaluateAudioRequest) -> EvaluateAudioResponse:
    audio_bytes = AudioVADEngine.decode_audio_base64(payload.audio_base64)
    if audio_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to decode audio_base64 payload.",
        )

    analysis = audio_engine.analyze_audio_chunk(
        audio_bytes=audio_bytes,
        sample_rate=payload.sample_rate,
        min_speech_duration=payload.min_speech_duration,
    )

    return EvaluateAudioResponse(
        speech_detected=analysis["speech_detected"],
        speech_duration_seconds=analysis["speech_duration_seconds"],
        total_duration_seconds=analysis["total_duration_seconds"],
        speech_ratio=analysis["speech_ratio"],
        average_energy=analysis["average_energy"],
    )


@app.post(
    "/api/v1/proctor/inference-stub",
    response_model=InferenceResponse,
    tags=["Proctoring Inference"],
    summary="Legacy inference endpoint for backward compatibility",
)
async def proctor_inference_stub(payload: InferenceRequest) -> InferenceResponse:
    anomalies: List[AnomalyPrediction] = []

    if payload.frame_base64:
        image = FaceEngine.decode_image_base64(payload.frame_base64)
        if image is not None:
            res = face_engine.evaluate_frame(image)
            if res["anomaly"] == "no_face_detected":
                anomalies.append(AnomalyPrediction(
                    violation_type="no_face_detected",
                    confidence=0.95,
                    severity="low",
                    details={"face_count": 0},
                ))
            elif res["anomaly"] == "multiple_faces_detected":
                anomalies.append(AnomalyPrediction(
                    violation_type="multiple_faces_detected",
                    confidence=0.95,
                    severity="high",
                    details={"face_count": res["face_count"]},
                ))

    return InferenceResponse(
        session_id=payload.session_id,
        status="success",
        anomalies_detected=len(anomalies) > 0,
        predictions=anomalies,
    )
