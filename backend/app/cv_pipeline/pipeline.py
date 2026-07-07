import numpy as np
import io
import logging
from typing import List, Dict
from PIL import Image

from app.config import get_settings
from app.cv_pipeline.detector import (
    INDEXING_CONFIDENCE_THRESHOLD,
    SCAN_CONFIDENCE_THRESHOLD,
    FaceDetector,
)
from app.cv_pipeline.embedder import FaceEmbedder
from app.cv_pipeline.aligner import align_face
from app.cv_pipeline.iqa import assess_quality
from app.cv_pipeline.liveness import LivenessChecker
from app.cv_pipeline.tracker import VideoFaceTracker

logger = logging.getLogger(__name__)
settings = get_settings()


class CVPipeline:
    """Orchestrates all computer vision processing"""

    def __init__(self):
        self.detector = FaceDetector()
        self.embedder = FaceEmbedder()
        self.liveness_checker = LivenessChecker()
        self.tracker = VideoFaceTracker()

    def process_image(
        self,
        image_bytes: bytes,
        mode: str = "scan",
        confidence_threshold: float | None = None,
    ) -> List[Dict]:
        """Process single image, return embeddings for all detected faces"""
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image_array = np.array(image)
        except Exception:
            return []

        # Use provided threshold or default from the requested mode
        threshold = confidence_threshold if confidence_threshold is not None else (
            INDEXING_CONFIDENCE_THRESHOLD if mode == "indexing" else SCAN_CONFIDENCE_THRESHOLD
        )

        # Detect faces
        faces = self.detector.detect(
            image_array,
            mode=mode,
            confidence_threshold=threshold,
        )
        logger.info(
            "Face detection completed",
            extra={
                "image_shape": tuple(image_array.shape),
                "threshold": threshold,
                "detections": len(faces),
            },
        )
        results = []

        for face in faces:
            bbox = face.get("bbox", [])
            landmarks = face.get("landmarks")

            if not bbox or len(bbox) < 4:
                continue

            # Crop face
            x1, y1, x2, y2 = [int(v) for v in bbox]
            x1, x2 = max(0, x1), min(image_array.shape[1], x2)
            y1, y2 = max(0, y1), min(image_array.shape[0], y2)

            face_crop = image_array[y1:y2, x1:x2]

            # Align face
            if landmarks is not None:
                aligned = align_face(image_array, landmarks)
            else:
                aligned = face_crop

            # Quality assessment
            quality = assess_quality(aligned)
            if not quality["passed"]:
                logger.info(
                    "IQA rejected face",
                    extra={
                        "bbox": bbox,
                        "quality": quality,
                        "reason": quality.get("reason"),
                    },
                )
                continue

            # Extract embedding
            embedding = self.embedder.embed(aligned)

            results.append({
                "embedding": embedding,
                "quality": quality,
                "bbox": bbox,
                "aligned_crop_shape": aligned.shape,
            })

        return results

    def process_video(self, video_bytes: bytes) -> List[Dict]:
        """Process video file"""
        return self.tracker.process_video(video_bytes, self.detector, self.embedder)

    def process_scan_frames(self, frames: List[bytes]) -> Dict:
        """Process user scan frames for face search - average embeddings from all good frames"""
        # Convert bytes to numpy arrays
        frame_arrays = []
        for frame_bytes in frames:
            try:
                img = Image.open(io.BytesIO(frame_bytes))
                frame_arrays.append(np.array(img))
            except Exception:
                continue

        if not frame_arrays:
            return {
                "embedding": None,
                "liveness": {"passed": False, "score": 0.0},
                "quality": {"passed": False},
                "success": False,
                "error": "No valid frames",
            }

        # Process all frames: detect, align, IQA, embed
        all_embeddings = []
        all_qualities = []
        all_liveness_results = []

        for frame in frame_arrays:
            # Detect and crop face
            faces = self.detector.detect(
                frame,
                mode="scan",
            )
            logger.info(
                "Scan frame face detection completed",
                extra={
                    "frame_shape": tuple(frame.shape),
                    "threshold": settings.face_detection_threshold,
                    "detections": len(faces),
                },
            )
            if not faces:
                continue

            face = faces[0]
            bbox = face.get("bbox", [])
            landmarks = face.get("landmarks")

            if not bbox or len(bbox) < 4:
                continue

            x1, y1, x2, y2 = [int(v) for v in bbox]
            x1, x2 = max(0, x1), min(frame.shape[1], x2)
            y1, y2 = max(0, y1), min(frame.shape[0], y2)

            face_crop = frame[y1:y2, x1:x2]

            if landmarks is not None:
                aligned = align_face(frame, landmarks)
            else:
                aligned = face_crop

            quality = assess_quality(aligned)

            if quality["passed"]:
                embedding = self.embedder.embed(aligned)
                all_embeddings.append(embedding)
                all_qualities.append(quality)
            else:
                logger.info(
                    "Scan IQA rejected face",
                    extra={
                        "bbox": bbox,
                        "quality": quality,
                        "reason": quality.get("reason"),
                    },
                )

        if not all_embeddings:
            return {
                "embedding": None,
                "liveness": {"passed": False, "score": 0.0},
                "quality": {"passed": False},
                "success": False,
                "error": "No usable face detected. Please scan in better lighting.",
            }

        # Check liveness on all original frames
        liveness_result = self.liveness_checker.check(frame_arrays)

        if not liveness_result["passed"]:
            return {
                "embedding": None,
                "liveness": liveness_result,
                "quality": all_qualities[0] if all_qualities else {"passed": False},
                "success": False,
                "error": liveness_result.get("failure_reason", "Liveness check failed"),
            }

        usable_frame_count = len(all_embeddings)
        logger.info("Averaging scan embeddings", extra={"usable_frames": usable_frame_count})

        if usable_frame_count == 1:
            avg_embedding = all_embeddings[0]
        else:
            embeddings_array = np.stack(all_embeddings, axis=0)  # (N, 512)
            avg_embedding = np.mean(embeddings_array, axis=0)
            norm = np.linalg.norm(avg_embedding)
            if norm > 0:
                avg_embedding = avg_embedding / norm

        # Average quality metrics
        avg_sharpness = float(np.mean([q.get("sharpness", 0) for q in all_qualities]))
        avg_brightness = float(np.mean([q.get("brightness", 0) for q in all_qualities]))
        avg_face_area = int(np.mean([q.get("face_area_px", 0) for q in all_qualities]))

        return {
            "embedding": avg_embedding.astype(np.float32),
            "liveness": liveness_result,
            "quality": {
                "passed": True,
                "sharpness": avg_sharpness,
                "brightness": avg_brightness,
                "face_area_px": avg_face_area,
            },
            "success": True,
            "error": None,
        }

