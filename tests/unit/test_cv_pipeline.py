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


@pytest.fixture
def pipeline():
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
