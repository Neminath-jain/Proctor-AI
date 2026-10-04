import base64
import io
import logging
import math
import struct
import wave
from typing import Any, Dict, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

# Attempt to load webrtcvad if available
try:
    import webrtcvad
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False
    logger.warning("webrtcvad not available, using energy & spectral ZCR VAD fallback.")


class AudioVADEngine:
    """
    Lightweight Voice Activity Detection (VAD) Engine.
    Detects human speech vs. ambient background noise or silence.
    Uses WebRTC VAD (mode 2/3) when available, complemented by
    Root-Mean-Square (RMS) energy and Zero-Crossing Rate (ZCR) acoustic analysis.
    """

    def __init__(self, mode: int = 2):
        self.vad = webrtcvad.Vad(mode) if WEBRTC_AVAILABLE else None
        logger.info(f"AudioVADEngine initialized (webrtcvad={WEBRTC_AVAILABLE}, mode={mode}).")

    @staticmethod
    def decode_audio_base64(audio_base64: str) -> Optional[bytes]:
        """Decode base64 encoded audio string."""
        try:
            if "," in audio_base64:
                audio_base64 = audio_base64.split(",", 1)[1]
            return base64.b64decode(audio_base64)
        except Exception as e:
            logger.error(f"Failed to decode base64 audio: {e}")
            return None

    def analyze_audio_chunk(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        min_speech_duration: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Analyze audio slice for voice activity.
        Handles WAV files and raw 16-bit PCM byte streams.
        Returns:
            {
                "speech_detected": bool,
                "speech_duration_seconds": float,
                "total_duration_seconds": float,
                "speech_ratio": float,
                "average_energy": float
            }
        """
        raw_pcm = None
        actual_sample_rate = sample_rate

        # 1. Check for WAV header
        if audio_bytes.startswith(b"RIFF"):
            try:
                with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                    actual_sample_rate = wf.getframerate()
                    channels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    frames = wf.readframes(wf.getnframes())

                    # Convert to mono if multi-channel
                    if channels == 2 and sampwidth == 2:
                        samples = np.frombuffer(frames, dtype=np.int16)
                        # Average left and right channels
                        mono = ((samples[0::2].astype(np.int32) + samples[1::2].astype(np.int32)) // 2).astype(np.int16)
                        raw_pcm = mono.tobytes()
                    elif sampwidth == 2:
                        raw_pcm = frames
                    else:
                        # 8-bit or float -> convert to 16-bit
                        samples = np.frombuffer(frames, dtype=np.uint8).astype(np.int16)
                        raw_pcm = ((samples - 128) * 256).astype(np.int16).tobytes()
            except Exception as e:
                logger.warning(f"Could not parse WAV structure, treating as raw PCM: {e}")
                raw_pcm = audio_bytes
        else:
            raw_pcm = audio_bytes

        if not raw_pcm or len(raw_pcm) < 640:
            return {
                "speech_detected": False,
                "speech_duration_seconds": 0.0,
                "total_duration_seconds": 0.0,
                "speech_ratio": 0.0,
                "average_energy": 0.0,
            }

        # Convert to numpy array for signal analysis
        samples = np.frombuffer(raw_pcm, dtype=np.int16)
        total_samples = len(samples)
        total_duration = total_samples / float(actual_sample_rate)

        # Frame windowing: 20ms frame
        frame_ms = 20
        frame_size = int(actual_sample_rate * (frame_ms / 1000.0))
        if frame_size <= 0:
            frame_size = 320

        speech_frames = 0
        total_frames = 0
        energies = []

        # Background noise adaptive threshold
        # Calculate overall RMS
        float_samples = samples.astype(np.float32) / 32768.0
        rms_total = float(np.sqrt(np.mean(float_samples**2))) if len(float_samples) > 0 else 0.0

        for i in range(0, total_samples - frame_size + 1, frame_size):
            frame = samples[i : i + frame_size]
            total_frames += 1

            # Energy calculation for this frame
            frame_float = frame.astype(np.float32) / 32768.0
            frame_rms = float(np.sqrt(np.mean(frame_float**2)))
            energies.append(frame_rms)

            # Zero crossing rate
            zcr = float(np.mean(np.abs(np.diff(np.sign(frame_float)))) / 2.0)

            is_speech = False
            # 1. WebRTC VAD if matching standard sample rates (8000, 16000, 32000, 48000)
            if self.vad and actual_sample_rate in (8000, 16000, 32000, 48000):
                try:
                    is_speech = self.vad.is_speech(frame.tobytes(), actual_sample_rate)
                except Exception:
                    is_speech = False

            # 2. Hybrid acoustic fallback (RMS energy > 0.02 and ZCR in human speech range [0.02, 0.40])
            if not is_speech:
                if frame_rms > 0.025 and (0.02 <= zcr <= 0.45):
                    is_speech = True

            if is_speech:
                speech_frames += 1

        speech_duration = (speech_frames * frame_ms) / 1000.0
        speech_ratio = (speech_frames / total_frames) if total_frames > 0 else 0.0
        avg_energy = float(np.mean(energies)) if energies else 0.0

        speech_detected = speech_duration >= min_speech_duration

        return {
            "speech_detected": speech_detected,
            "speech_duration_seconds": round(speech_duration, 2),
            "total_duration_seconds": round(total_duration, 2),
            "speech_ratio": round(speech_ratio, 3),
            "average_energy": round(avg_energy, 4),
        }
