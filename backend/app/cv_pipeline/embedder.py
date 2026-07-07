from typing import List

import cv2
import numpy as np
import onnxruntime as ort

from app.config import get_settings

settings = get_settings()


class FaceEmbedder:
    """Real ArcFace embedder, run locally via onnxruntime."""

    _session: ort.InferenceSession | None = None

    def __init__(self, model_path: str | None = None):
        path = model_path or settings.arcface_model_path
        if FaceEmbedder._session is None:
            FaceEmbedder._session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        self.session = FaceEmbedder._session
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def preprocess(self, face_crop: np.ndarray) -> np.ndarray:
        """Prepare an aligned 112x112 face crop for ArcFace inference."""
        if not isinstance(face_crop, np.ndarray):
            return np.zeros((1, 3, 112, 112), dtype=np.float32)

        crop = face_crop
        if crop.ndim == 2:
            crop = np.stack([crop] * 3, axis=-1)
        if crop.shape[:2] != (112, 112):
            crop = cv2.resize(crop, (112, 112))

        # Pipeline hands us RGB crops; the insightface-trained model expects BGR,
        # raw pixel values (no mean/std normalization) per the ONNX Model Zoo
        # reference preprocessing for this ArcFace export.
        bgr = crop[:, :, ::-1].astype(np.float32)
        chw = bgr.transpose(2, 0, 1)
        return chw[np.newaxis, :, :, :].astype(np.float32)

    def embed(self, face_crop: np.ndarray) -> np.ndarray:
        """Generate a real, L2-normalized 512-d embedding for a single face."""
        input_tensor = self.preprocess(face_crop)
        output = self.session.run([self.output_name], {self.input_name: input_tensor})[0]
        embedding = output[0].astype(np.float32)

        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding

    def embed_batch(self, crops: List[np.ndarray]) -> np.ndarray:
        """Batch embed multiple faces."""
        return np.array([self.embed(crop) for crop in crops], dtype=np.float32)
