import numpy as np
import cv2


ARCFACE_TEMPLATE = np.array([
    [38.2946, 51.6963],
    [73.5318, 51.5014],
    [56.0252, 71.7366],
    [41.5493, 92.3655],
    [70.7299, 92.2041],
], dtype=np.float32)


def align_face(image: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
    """Align face using landmark-based affine transform"""
    if not isinstance(image, np.ndarray) or len(image.shape) < 2:
        return np.zeros((112, 112, 3), dtype=np.uint8)

    if not isinstance(landmarks, np.ndarray) or landmarks.shape[0] < 5:
        # Fallback: simple crop and resize
        h, w = image.shape[:2]
        crop_size = min(h, w)
        crop = image[:crop_size, :crop_size]
        return cv2.resize(crop, (112, 112))

    try:
        # Estimate affine transform
        transform, _ = cv2.estimateAffinePartial2D(
            landmarks[:5].astype(np.float32),
            ARCFACE_TEMPLATE,
            method=cv2.RANSAC,
            ransacReprojThreshold=10.0,
        )

        if transform is None:
            # Fallback
            h, w = image.shape[:2]
            crop_size = min(h, w)
            crop = image[:crop_size, :crop_size]
            return cv2.resize(crop, (112, 112))

        # Apply warp affine
        aligned = cv2.warpAffine(image, transform, (112, 112))
        return aligned

    except Exception:
        # Fallback
        h, w = image.shape[:2]
        crop_size = min(h, w)
        crop = image[:crop_size, :crop_size]
        return cv2.resize(crop, (112, 112))
