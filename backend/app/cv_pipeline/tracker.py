import os
import tempfile
from typing import Dict, List

import cv2

from app.cv_pipeline.aligner import align_face
from app.cv_pipeline.iqa import assess_quality

MAX_SAMPLED_FRAMES = 10


class VideoFaceTracker:
    """Samples frames from a video and extracts real face embeddings from each."""

    def process_video(self, video_bytes: bytes, detector, embedder) -> List[Dict]:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(video_bytes)
            temp_path = f.name

        results: List[Dict] = []
        try:
            capture = cv2.VideoCapture(temp_path)
            try:
                total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
                if total_frames <= 0:
                    return []

                sample_count = min(MAX_SAMPLED_FRAMES, total_frames)
                frame_indices = {
                    int(i * total_frames / sample_count) for i in range(sample_count)
                }

                current_index = 0
                while True:
                    ok, frame_bgr = capture.read()
                    if not ok:
                        break
                    if current_index in frame_indices:
                        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                        faces = detector.detect(frame_rgb, mode="indexing")
                        for face in faces:
                            bbox = face.get("bbox")
                            landmarks = face.get("landmarks")
                            if not bbox or len(bbox) < 4:
                                continue

                            x1, y1, x2, y2 = [int(v) for v in bbox]
                            x1, x2 = max(0, x1), min(frame_rgb.shape[1], x2)
                            y1, y2 = max(0, y1), min(frame_rgb.shape[0], y2)
                            crop = frame_rgb[y1:y2, x1:x2]

                            aligned = align_face(frame_rgb, landmarks) if landmarks is not None else crop
                            quality = assess_quality(aligned)
                            if not quality["passed"]:
                                continue

                            embedding = embedder.embed(aligned)
                            results.append(
                                {
                                    "embedding": embedding,
                                    "quality": quality,
                                    "bbox": bbox,
                                    "frame_index": current_index,
                                }
                            )
                    current_index += 1
            finally:
                capture.release()
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        return results
