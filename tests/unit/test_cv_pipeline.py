import pytest
import numpy as np
import sys
import os
from PIL import Image
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))

from app.cv_pipeline.pipeline import CVPipeline
from app.cv_pipeline.iqa import assess_quality
from app.cv_pipeline.aligner import align_face
from app.cv_pipeline.detector import FaceDetector
from app.cv_pipeline.embedder import FaceEmbedder


def _fake_detect(self, image, mode="scan", confidence_threshold=None):
    """Stand-in for MediaPipe detection: one centered face, fixed landmarks."""
    if not isinstance(image, np.ndarray) or image.ndim < 2:
        return []
    height, width = image.shape[:2]
    if height < 20 or width < 20:
        return []
    landmarks = np.array(
        [
            [width * 0.35, height * 0.35],
            [width * 0.65, height * 0.35],
            [width * 0.50, height * 0.55],
            [width * 0.35, height * 0.70],
            [width * 0.65, height * 0.70],
        ],
        dtype=np.float32,
    )
    return [
        {
            "bbox": [width * 0.2, height * 0.2, width * 0.8, height * 0.8],
            "confidence": 0.95,
            "landmarks": landmarks,
            "kps": landmarks,
        }
    ]


def _fake_embed(self, face_crop):
    """Stand-in for ArcFace inference: deterministic, L2-normalized vector."""
    seed = hash(face_crop.tobytes()) % (2**32) if isinstance(face_crop, np.ndarray) else 0
    rng = np.random.default_rng(seed)
    embedding = rng.standard_normal(512).astype(np.float32)
    norm = np.linalg.norm(embedding)
    return embedding / norm if norm > 0 else embedding


@pytest.fixture
def pipeline(monkeypatch):
    """CVPipeline with detection/embedding mocked out.

    These are unit tests for pipeline orchestration (detect -> align -> IQA ->
    embed -> assemble results), not the real MediaPipe/ArcFace models - those
    models are ~265MB and gitignored on purpose, so tests must not depend on
    them being present on disk.
    """
    monkeypatch.setattr(FaceDetector, "__init__", lambda self, model_path=None: None)
    monkeypatch.setattr(FaceDetector, "detect", _fake_detect)
    monkeypatch.setattr(FaceEmbedder, "__init__", lambda self, model_path=None: None)
    monkeypatch.setattr(FaceEmbedder, "embed", _fake_embed)
    return CVPipeline()


@pytest.fixture
def test_image():
    """Create synthetic test image"""
    img = Image.new("RGB", (224, 224), color=(100, 100, 100))
    return img


def test_face_quality_assessment():
    """Test IQA module"""
    # Test good face
    good_face = np.ones((112, 112, 3), dtype=np.uint8) * 128
    result = assess_quality(good_face)
    assert "sharpness" in result
    assert "brightness" in result
    assert "passed" in result


def test_face_alignment():
    """Test face alignment"""
    img = np.ones((224, 224, 3), dtype=np.uint8) * 128
    landmarks = np.array([
        [56, 56], [168, 56], [112, 112],
        [56, 168], [168, 168]
    ], dtype=np.float32)

    aligned = align_face(img, landmarks)
    assert aligned.shape == (112, 112, 3)


def test_pipeline_process_image(pipeline, test_image):
    """Test full image processing"""
    img_bytes = io.BytesIO()
    test_image.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    results = pipeline.process_image(img_bytes.getvalue())
    assert isinstance(results, list)
    # Mock detector returns results
    for result in results:
        assert "embedding" in result
        assert result["embedding"].shape == (512,)


def test_pipeline_scan_frames(pipeline):
    """Test scan frame processing"""
    # Create synthetic frame
    img = Image.new("RGB", (224, 224), color=(100, 100, 100))
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    frames = [img_bytes.getvalue()] * 3

    result = pipeline.process_scan_frames(frames)
    assert "embedding" in result
    assert "liveness" in result
    assert "quality" in result
    assert "success" in result
