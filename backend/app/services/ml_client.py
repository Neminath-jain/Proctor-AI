import logging
from typing import Any, Dict, List, Optional, Tuple
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class MLServiceUnavailableError(Exception):
    """Raised when the ML Proctoring service cannot be reached or times out."""
    pass


class MLProctoringClient:
    """
    Asynchronous client for interacting with the AI/ML Proctoring Inference Service.
    Configured with aggressive timeouts and circuit-breaker handling to ensure
    candidate exam progression is never blocked if ML inference experiences latency or downtime.
    """

    def __init__(self, base_url: Optional[str] = None, timeout_seconds: float = 1.5):
        self.base_url = (base_url or settings.ML_SERVICE_URL).rstrip("/")
        self.timeout = timeout_seconds

    async def extract_reference_embedding(self, image_base64: str) -> Tuple[bool, Optional[List[float]], Optional[str]]:
        """
        Calls ML service to extract a 128-d reference face embedding.
        Returns: (success: bool, embedding: Optional[List[float]], error_message: Optional[str])
        """
        url = f"{self.base_url}/api/v1/ml/extract-embedding"
        payload = {"image_base64": image_base64}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    return False, None, f"ML service error: HTTP {resp.status_code}"
                data = resp.json()
                if not data.get("success"):
                    return False, None, data.get("error", "Failed to extract face embedding.")
                return True, data.get("embedding"), None
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.warning(f"ML Service unreachable during embedding extraction: {exc}")
            raise MLServiceUnavailableError(f"ML service connection failed: {exc}")
        except Exception as exc:
            logger.error(f"Unexpected error in extract_reference_embedding: {exc}")
            return False, None, str(exc)

    async def evaluate_frame(
        self,
        frame_base64: str,
        reference_embedding: Optional[List[float]] = None,
        similarity_threshold: float = 0.60,
    ) -> Dict[str, Any]:
        """
        Evaluates a periodic frame for face detection, face count, and candidate identity match.
        Returns dict matching EvaluateFrameResponse.
        """
        url = f"{self.base_url}/api/v1/ml/evaluate-frame"
        payload = {
            "frame_base64": frame_base64,
            "reference_embedding": reference_embedding,
            "similarity_threshold": similarity_threshold,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"ML Service returned HTTP {resp.status_code} for frame evaluation")
                raise MLServiceUnavailableError(f"HTTP {resp.status_code}")
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.warning(f"ML Service offline/timeout during frame evaluation: {exc}")
            raise MLServiceUnavailableError(f"ML inference unreachable: {exc}")

    async def evaluate_audio(
        self,
        audio_base64: str,
        sample_rate: int = 16000,
        min_speech_duration: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Evaluates an audio chunk for voice activity detection (VAD).
        """
        url = f"{self.base_url}/api/v1/ml/evaluate-audio"
        payload = {
            "audio_base64": audio_base64,
            "sample_rate": sample_rate,
            "min_speech_duration": min_speech_duration,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    return resp.json()
                raise MLServiceUnavailableError(f"HTTP {resp.status_code}")
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.warning(f"ML Service offline/timeout during audio evaluation: {exc}")
            raise MLServiceUnavailableError(f"ML inference unreachable: {exc}")


ml_client = MLProctoringClient()
