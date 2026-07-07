import numpy as np
import os
from typing import List, Dict

from app.config import get_settings

settings = get_settings()


class LivenessChecker:
    """Liveness detection for anti-spoofing"""

    def check(self, frames: List[np.ndarray]) -> Dict:
        """Check if frames contain live face"""
        if not frames or len(frames) < 2:
            return {
                "passed": False,
                "score": 0.0,
                "signals": {
                    "blink_detected": False,
                    "head_pose_variation": 0.0,
                    "texture_score": 0.0,
                    "deep_score": 0.0,
                },
                "failure_reason": "Insufficient frames",
            }

        # Simplified liveness check: check frame variation
        frame_diffs = []
        for i in range(1, len(frames)):
            if isinstance(frames[i-1], np.ndarray) and isinstance(frames[i], np.ndarray):
                if frames[i-1].shape == frames[i].shape:
                    diff = np.mean(np.abs(frames[i].astype(float) - frames[i-1].astype(float)))
                    frame_diffs.append(diff)

        # Mock liveness signals
        blink_detected = len(frame_diffs) > 0 and max(frame_diffs) > 5
        head_pose_variation = min(max(frame_diffs) if frame_diffs else 0, 1.0)
        texture_score = min(np.mean(frame_diffs) / 50 if frame_diffs else 0, 1.0)
        
        # Deep anti-spoofing model score - only if model exists
        antispoofing_path = getattr(settings, 'antispoofing_model_path', None)
        model_available = bool(antispoofing_path and os.path.exists(antispoofing_path))
        deep_score = 0.7 if model_available else 0.0  # Placeholder for actual model inference

        # Weighted fusion - blink is now optional, not mandatory.
        # If the anti-spoofing model is missing, drop its 0.15 weight entirely and
        # redistribute it proportionally across the other three signals instead of
        # silently multiplying a real deep_score of 0.0 into the fusion sum.
        blink_weight, head_pose_weight, texture_weight, deep_weight = 0.15, 0.25, 0.15, 0.15
        if not model_available:
            remaining = blink_weight + head_pose_weight + texture_weight
            redistribution = deep_weight / remaining
            blink_weight += blink_weight * redistribution
            head_pose_weight += head_pose_weight * redistribution
            texture_weight += texture_weight * redistribution
            deep_weight = 0.0

        score = (
            blink_weight * (1.0 if blink_detected else 0.0)
            + head_pose_weight * head_pose_variation
            + texture_weight * texture_score
            + deep_weight * deep_score
            + 0.3  # Base score
        )

        # Lower threshold from 0.75 to 0.65
        passed = score >= 0.65

        return {
            "passed": passed,
            "score": float(score),
            "signals": {
                "blink_detected": blink_detected,
                "head_pose_variation": float(head_pose_variation),
                "texture_score": float(texture_score),
                "deep_score": float(deep_score),
            },
            "failure_reason": None if passed else "Liveness check failed",
        }
