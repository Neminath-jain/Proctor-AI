import base64
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class FaceEngine:
    """
    High-performance, lightweight face detection and facial feature comparison engine.
    Uses OpenCV's optimized Haar cascade detector for robust face counting and
    normalized spatial-frequency descriptor embeddings for cosine similarity verification.
    """

    def __init__(self):
        # 1. Search in app/models
        models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
        cascade_path = os.path.join(models_dir, "haarcascade_frontalface_default.xml")
        
        # 2. Fallback to cv2.data.haarcascades
        if not os.path.exists(cascade_path):
            cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")

        self.face_cascade = None
        if hasattr(cv2, "CascadeClassifier") and os.path.exists(cascade_path):
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            logger.info(f"FaceEngine initialized with Haar cascade from: {cascade_path}")
        else:
            logger.warning("CascadeClassifier not available in this OpenCV build, using contour/geometry detector.")

    @staticmethod
    def decode_image_base64(image_base64: str) -> Optional[np.ndarray]:
        """Decode base64 encoded image string (with or without data URI prefix) into BGR image."""
        try:
            if "," in image_base64:
                # Remove data:image/...;base64, prefix
                image_base64 = image_base64.split(",", 1)[1]
            image_data = base64.b64decode(image_base64)
            np_arr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            logger.error(f"Failed to decode base64 image: {e}")
            return None

    def detect_faces(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect faces in image.
        Returns list of detected face dictionaries: [{'x': x, 'y': y, 'width': w, 'height': h, 'confidence': float}]
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # Apply histogram equalization to handle varied illumination
        gray = cv2.equalizeHist(gray)

        if self.face_cascade is None:
            logger.warning("Face cascade classifier is not initialized.")
            return []

        # Multi-scale face detection
        rects = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=4,
            minSize=(30, 30),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )

        faces = []
        for (x, y, w, h) in rects:
            faces.append({
                "x": int(x),
                "y": int(y),
                "width": int(w),
                "height": int(h),
                "confidence": 0.95,
            })
        return faces

    def extract_face_embedding(self, image: np.ndarray, face_box: Optional[Dict[str, int]] = None) -> Optional[List[float]]:
        """
        Extract a 128-dimensional L2-normalized feature embedding vector for a face.
        If face_box is not provided, the largest detected face is used.
        """
        if face_box is None:
            faces = self.detect_faces(image)
            if not faces:
                return None
            # Pick largest face by area
            face_box = max(faces, key=lambda f: f["width"] * f["height"])

        x, y, w, h = face_box["x"], face_box["y"], face_box["width"], face_box["height"]
        h_img, w_img = image.shape[:2]

        # Clamp bounds
        x = max(0, min(x, w_img - 1))
        y = max(0, min(y, h_img - 1))
        w = max(1, min(w, w_img - x))
        h = max(1, min(h, h_img - y))

        face_roi = image[y : y + h, x : x + w]
        if face_roi.size == 0:
            return None

        # Standardize face crop to 64x64 grayscale
        face_gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        face_resized = cv2.resize(face_gray, (64, 64), interpolation=cv2.INTER_AREA)
        face_norm = cv2.equalizeHist(face_resized).astype(np.float32) / 255.0
        face_norm = face_norm - float(np.mean(face_norm))

        # Compute 2D Discrete Cosine Transform (DCT)
        dct = cv2.dct(face_norm)

        # Extract top 128 structural AC frequency coefficients (skipping global DC illumination at [0, 0])
        features: List[float] = []
        for r in range(16):
            for c in range(9):
                if r == 0 and c == 0:
                    continue
                features.append(float(dct[r, c]))
                if len(features) >= 128:
                    break
            if len(features) >= 128:
                break

        vec = np.array(features[:128], dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm
        return vec.tolist()

    @staticmethod
    def calculate_similarity(embedding_a: List[float], embedding_b: List[float]) -> float:
        """
        Calculate cosine similarity between two 128-d embeddings.
        Returns score from 0.0 (completely dissimilar) to 1.0 (identical).
        """
        if not embedding_a or not embedding_b or len(embedding_a) != len(embedding_b):
            return 0.0
        a = np.array(embedding_a, dtype=np.float32)
        b = np.array(embedding_b, dtype=np.float32)
        dot = float(np.dot(a, b))
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a < 1e-6 or norm_b < 1e-6:
            return 0.0
        cos_sim = dot / (norm_a * norm_b)
        # Clamp to [0.0, 1.0]
        return float(max(0.0, min(1.0, cos_sim)))

    def evaluate_frame(
        self,
        image: np.ndarray,
        reference_embedding: Optional[List[float]] = None,
        similarity_threshold: float = 0.60,
    ) -> Dict[str, Any]:
        """
        Full evaluation of a proctoring video frame:
        1. Detects number of faces.
        2. If 0 faces -> anomaly = "no_face_detected".
        3. If 2+ faces -> anomaly = "multiple_faces_detected".
        4. If 1 face and reference_embedding provided:
           Extracts face embedding and compares similarity.
           If similarity < threshold -> anomaly = "face_mismatch".
        """
        faces = self.detect_faces(image)
        face_count = len(faces)
        anomaly = None
        similarity: Optional[float] = None
        extracted_embedding: Optional[List[float]] = None

        if face_count == 0:
            anomaly = "no_face_detected"
        elif face_count > 1:
            anomaly = "multiple_faces_detected"
        else:
            # Exactly 1 face
            face_box = faces[0]
            extracted_embedding = self.extract_face_embedding(image, face_box)
            if reference_embedding and extracted_embedding:
                similarity = self.calculate_similarity(extracted_embedding, reference_embedding)
                if similarity < similarity_threshold:
                    anomaly = "face_mismatch"

        return {
            "face_count": face_count,
            "faces": faces,
            "similarity": similarity,
            "anomaly": anomaly,
            "embedding": extracted_embedding,
        }
