import threading
from typing import List

import cv2
import numpy as np

from app.config import get_settings

settings = get_settings()

# YuNet emits calibrated per-face confidences. Indexing leans toward recall:
# small/distant faces in group shots matter, and a false-positive "face" only
# adds a stray vector that sits near 0.0 cosine against any real probe, so it
# never surfaces in results. Live scans want one clean, confident face.
INDEXING_CONFIDENCE_THRESHOLD = 0.60
SCAN_CONFIDENCE_THRESHOLD = 0.80

# Longest edge fed to the detector. Detections are mapped back to original
# image coordinates so callers can crop/align from the full-resolution image.
MAX_DETECTION_EDGE = 1920


class FaceDetector:
    """Multi-face detection via YuNet (cv2.FaceDetectorYN).

    Chosen over MediaPipe FaceLandmarker after a head-to-head on real event
    photos: FaceLandmarker is a near-field model and found 0 faces on typical
    DSLR group shots where YuNet found every person. YuNet also returns the
    exact 5 landmarks (eyes, nose tip, mouth corners) the ArcFace alignment
    template needs, with real confidence scores.
    """

    _detector: "cv2.FaceDetectorYN | None" = None
    _lock = threading.Lock()

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path or settings.yunet_model_path
        if FaceDetector._detector is None:
            FaceDetector._detector = cv2.FaceDetectorYN.create(
                self.model_path,
                "",
                (320, 320),
                0.5,   # score threshold at the model level; per-mode filter below
                0.3,   # NMS threshold
                5000,  # top_k
            )
        self.model_loaded = True

    def detect(
        self,
        image: np.ndarray,
        mode: str = "scan",
        confidence_threshold: float | None = None,
    ) -> List[dict]:
        """Detect faces, returning bbox + 5-point landmarks per face.

        Coordinates are in the ORIGINAL image space regardless of any internal
        downscaling, so callers can crop and align from the full-res image.
        """
        if not isinstance(image, np.ndarray) or image.ndim < 2:
            return []

        orig_height, orig_width = image.shape[:2]
        if orig_height < 20 or orig_width < 20:
            return []

        threshold = confidence_threshold
        if threshold is None:
            threshold = INDEXING_CONFIDENCE_THRESHOLD if mode == "indexing" else SCAN_CONFIDENCE_THRESHOLD

        if image.ndim == 2:
            rgb = np.stack([image] * 3, axis=-1)
        elif image.shape[2] == 4:
            rgb = image[:, :, :3]
        else:
            rgb = image

        scale = 1.0
        longest_edge = max(orig_height, orig_width)
        if longest_edge > MAX_DETECTION_EDGE:
            scale = MAX_DETECTION_EDGE / float(longest_edge)
            rgb = cv2.resize(
                rgb,
                (max(1, int(round(orig_width * scale))), max(1, int(round(orig_height * scale)))),
                interpolation=cv2.INTER_AREA,
            )

        det_height, det_width = rgb.shape[:2]
        bgr = np.ascontiguousarray(rgb[:, :, ::-1].astype(np.uint8))

        with FaceDetector._lock:
            FaceDetector._detector.setInputSize((det_width, det_height))
            _, detections = FaceDetector._detector.detect(bgr)

        if detections is None:
            return []

        inv = 1.0 / scale
        faces = []
        for det in detections:
            confidence = float(det[14])
            if confidence < threshold:
                continue

            x, y, w, h = det[0] * inv, det[1] * inv, det[2] * inv, det[3] * inv
            x1 = max(0.0, x)
            y1 = max(0.0, y)
            x2 = min(float(orig_width), x + w)
            y2 = min(float(orig_height), y + h)

            # YuNet landmark order: right eye, left eye, nose tip, right mouth
            # corner, left mouth corner (subject-relative). The ArcFace template
            # expects image-left eye first, so sort each pair by x - robust for
            # upright faces and immune to naming-convention mistakes.
            points = det[4:14].reshape(5, 2) * inv
            eyes = sorted([points[0], points[1]], key=lambda p: p[0])
            mouth = sorted([points[3], points[4]], key=lambda p: p[0])
            landmarks = np.array(
                [eyes[0], eyes[1], points[2], mouth[0], mouth[1]],
                dtype=np.float32,
            )

            faces.append(
                {
                    "bbox": [x1, y1, x2, y2],
                    "confidence": confidence,
                    "landmarks": landmarks,
                    "kps": landmarks,
                }
            )

        # Largest/most confident faces first so scan paths that take faces[0]
        # get the dominant face in frame.
        faces.sort(key=lambda f: f["confidence"] * ((f["bbox"][2] - f["bbox"][0]) * (f["bbox"][3] - f["bbox"][1])), reverse=True)
        return faces
