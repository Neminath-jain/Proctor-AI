import base64
import io
import math
import struct
import wave
import cv2
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.services.face_engine import FaceEngine
from app.services.audio_engine import AudioVADEngine


def create_blank_frame_base64(width=320, height=240, color=(0, 0, 0)) -> str:
    """Create a blank uniform image."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = color
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def create_synthetic_face_frame_base64(width=320, height=240, face_count=1) -> str:
    """
    Draw synthetic face-like ellipses and features to trigger or simulate face detections.
    Also used to test FaceEngine directly with controlled feature geometries.
    """
    img = np.ones((height, width, 3), dtype=np.uint8) * 200
    for i in range(face_count):
        center_x = int(width * (i + 1) / (face_count + 1))
        center_y = int(height / 2)
        # Head
        cv2.ellipse(img, (center_x, center_y), (40, 55), 0, 0, 360, (180, 150, 130), -1)
        # Eyes
        cv2.circle(img, (center_x - 15, center_y - 10), 6, (40, 40, 40), -1)
        cv2.circle(img, (center_x + 15, center_y - 10), 6, (40, 40, 40), -1)
        # Nose
        cv2.line(img, (center_x, center_y - 5), (center_x, center_y + 12), (70, 70, 70), 2)
        # Mouth
        cv2.ellipse(img, (center_x, center_y + 25), (16, 6), 0, 0, 180, (50, 50, 150), 3)

    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def create_sample_wav_base64(duration_seconds=2.0, sample_rate=16000, frequency_hz=0) -> str:
    """Create a sample WAV file in memory (silence if frequency=0, audio tone if frequency > 0)."""
    buf = io.BytesIO()
    num_samples = int(duration_seconds * sample_rate)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = []
        for i in range(num_samples):
            if frequency_hz > 0:
                # Modulated audio simulating speech harmonics
                value = int(10000 * math.sin(2 * math.pi * frequency_hz * (i / sample_rate)))
            else:
                value = 0
            frames.append(struct.pack("<h", value))
        wf.writeframes(b"".join(frames))
    return base64.b64encode(buf.getvalue()).decode("utf-8")


@pytest.mark.asyncio
async def test_ml_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["models_loaded"]["face_engine"] == "ready"
        assert data["models_loaded"]["audio_engine"] == "ready"


@pytest.mark.asyncio
async def test_evaluate_frame_no_face():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        blank_b64 = create_blank_frame_base64()
        resp = await client.post(
            "/api/v1/ml/evaluate-frame",
            json={"frame_base64": blank_b64},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["face_count"] == 0
        assert data["anomaly"] == "no_face_detected"


@pytest.mark.asyncio
async def test_face_engine_similarity_matching():
    engine = FaceEngine()
    # Create two arbitrary images
    img1 = np.ones((200, 200, 3), dtype=np.uint8) * 128
    cv2.circle(img1, (100, 100), 50, (255, 255, 255), -1)

    img2 = np.copy(img1)
    # Add slight noise to img2
    cv2.circle(img2, (100, 100), 48, (240, 240, 240), -1)

    emb1 = engine.extract_face_embedding(img1, {"x": 50, "y": 50, "width": 100, "height": 100})
    emb2 = engine.extract_face_embedding(img2, {"x": 50, "y": 50, "width": 100, "height": 100})

    assert emb1 is not None and len(emb1) == 128
    assert emb2 is not None and len(emb2) == 128

    sim_self = engine.calculate_similarity(emb1, emb1)
    assert sim_self > 0.99  # Identical embedding is ~1.0

    sim_similar = engine.calculate_similarity(emb1, emb2)
    assert sim_similar > 0.90  # Near-identical is high similarity

    # Create completely different image (checkers/gradient)
    img3 = np.zeros((200, 200, 3), dtype=np.uint8)
    img3[::4, ::4] = 255
    emb3 = engine.extract_face_embedding(img3, {"x": 50, "y": 50, "width": 100, "height": 100})
    sim_diff = engine.calculate_similarity(emb1, emb3)
    assert sim_diff < 0.60  # Dissimilar is low


@pytest.mark.asyncio
async def test_evaluate_audio_silence():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        silence_b64 = create_sample_wav_base64(duration_seconds=2.0, frequency_hz=0)
        resp = await client.post(
            "/api/v1/ml/evaluate-audio",
            json={"audio_base64": silence_b64},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["speech_detected"] is False
        assert data["speech_duration_seconds"] == 0.0
        assert data["total_duration_seconds"] >= 1.9


@pytest.mark.asyncio
async def test_evaluate_audio_speech_tone():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tone_b64 = create_sample_wav_base64(duration_seconds=2.0, frequency_hz=300)
        resp = await client.post(
            "/api/v1/ml/evaluate-audio",
            json={"audio_base64": tone_b64, "min_speech_duration": 0.3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_duration_seconds"] >= 1.9
        assert data["average_energy"] > 0.05
        assert data["speech_detected"] is True
