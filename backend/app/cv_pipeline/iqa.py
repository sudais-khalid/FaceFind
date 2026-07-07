import logging

import numpy as np

logger = logging.getLogger(__name__)


def assess_quality(face_crop: np.ndarray) -> dict:
    """Assess face image quality"""
    if not isinstance(face_crop, np.ndarray):
        return {
            "sharpness": 0,
            "brightness": 0,
            "face_area_px": 0,
            "passed": False,
            "reason": "Invalid input"
        }

    # Compute Laplacian variance (sharpness)
    if len(face_crop.shape) == 3:
        gray = np.mean(face_crop, axis=2)
    else:
        gray = face_crop

    laplacian = np.array([[0, -1, 0], [-1, 4, -1], [0, -1, 0]])
    sharpness = np.var(np.convolve(gray.flatten(), laplacian.flatten(), mode='valid'))

    # Compute brightness
    brightness = np.mean(face_crop)

    # Face area
    face_area_px = face_crop.shape[0] * face_crop.shape[1] if len(face_crop.shape) >= 2 else 0

    # Check thresholds
    passed = sharpness > 40 and 30 < brightness < 220 and face_area_px > 400
    reason = None
    if not passed:
        if sharpness <= 40:
            reason = "Image too blurry"
            logger.debug(
                "IQA rejected face",
                extra={
                    "threshold": "sharpness",
                    "actual": float(sharpness),
                    "required": "> 40",
                },
            )
        elif not (30 < brightness < 220):
            reason = "Image too bright or dark"
            logger.debug(
                "IQA rejected face",
                extra={
                    "threshold": "brightness",
                    "actual": float(brightness),
                    "required": "30 < brightness < 220",
                },
            )
        elif face_area_px <= 400:
            reason = "Face too small"
            logger.debug(
                "IQA rejected face",
                extra={
                    "threshold": "face_area_px",
                    "actual": int(face_area_px),
                    "required": "> 400",
                },
            )

    return {
        "sharpness": float(sharpness),
        "brightness": float(brightness),
        "face_area_px": int(face_area_px),
        "passed": bool(passed),
        "reason": reason,
    }
