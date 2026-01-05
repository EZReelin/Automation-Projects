"""
Pose Processor Module
====================
MediaPipe pose estimation and landmark processing for dart throws.
"""

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np


@dataclass
class Landmark:
    """Represents a pose landmark."""
    x: float
    y: float
    z: float
    visibility: float
    
    def to_dict(self) -> Dict[str, float]:
        return {
            'x': self.x,
            'y': self.y,
            'z': self.z,
            'visibility': self.visibility
        }


@dataclass
class PoseFrame:
    """Represents pose data for a single frame."""
    frame_number: int
    timestamp: float
    landmarks: Dict[str, Landmark]
    angles: Dict[str, float]
    is_throwing: bool = False
    throw_phase: Optional[str] = None


class PoseProcessor:
    """
    Processes video frames to extract pose landmarks using MediaPipe.
    
    Specialized for analyzing dart throwing mechanics.
    """
    
    # MediaPipe pose landmark indices
    LANDMARK_NAMES = {
        0: 'nose',
        11: 'left_shoulder',
        12: 'right_shoulder',
        13: 'left_elbow',
        14: 'right_elbow',
        15: 'left_wrist',
        16: 'right_wrist',
        23: 'left_hip',
        24: 'right_hip',
        25: 'left_knee',
        26: 'right_knee',
        27: 'left_ankle',
        28: 'right_ankle'
    }
    
    # Throw phases based on arm position
    THROW_PHASES = ['setup', 'backswing', 'acceleration', 'release', 'follow_through']
    
    def __init__(
        self,
        model_complexity: int = 2,
        min_detection_confidence: float = 0.7,
        min_tracking_confidence: float = 0.7,
        enable_segmentation: bool = False,
        throwing_hand: str = 'right',
        log_level: str = "INFO"
    ):
        """
        Initialize pose processor.
        
        Args:
            model_complexity: MediaPipe model complexity (0, 1, or 2)
            min_detection_confidence: Minimum detection confidence threshold
            min_tracking_confidence: Minimum tracking confidence threshold
            enable_segmentation: Enable body segmentation
            throwing_hand: 'right' or 'left' throwing hand
            log_level: Logging level
        """
        self.model_complexity = model_complexity
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.enable_segmentation = enable_segmentation
        self.throwing_hand = throwing_hand
        
        # Initialize MediaPipe
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        self.pose: Optional[mp.solutions.pose.Pose] = None
        
        # Throw detection state
        self._previous_elbow_angle: Optional[float] = None
        self._throw_state = 'idle'
        self._throw_start_frame: Optional[int] = None
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
    
    def initialize(self):
        """Initialize MediaPipe pose estimator."""
        self.pose = self.mp_pose.Pose(
            model_complexity=self.model_complexity,
            min_detection_confidence=self.min_detection_confidence,
            min_tracking_confidence=self.min_tracking_confidence,
            enable_segmentation=self.enable_segmentation,
            smooth_landmarks=True
        )
        self.logger.info("MediaPipe pose initialized")
    
    def process_frame(
        self,
        frame: np.ndarray,
        frame_number: int,
        timestamp: float
    ) -> Optional[PoseFrame]:
        """
        Process a single frame and extract pose data.
        
        Args:
            frame: BGR image frame
            frame_number: Frame number in sequence
            timestamp: Timestamp in seconds
            
        Returns:
            PoseFrame with extracted data, or None if no pose detected
        """
        if self.pose is None:
            self.initialize()
        
        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb_frame.flags.writeable = False
        
        # Process with MediaPipe
        results = self.pose.process(rgb_frame)
        
        if not results.pose_landmarks:
            return None
        
        # Extract landmarks
        landmarks = self._extract_landmarks(results.pose_landmarks)
        
        # Calculate angles
        angles = self._calculate_angles(landmarks)
        
        # Detect throw phase
        is_throwing, throw_phase = self._detect_throw_phase(angles, frame_number)
        
        return PoseFrame(
            frame_number=frame_number,
            timestamp=timestamp,
            landmarks=landmarks,
            angles=angles,
            is_throwing=is_throwing,
            throw_phase=throw_phase
        )
    
    def _extract_landmarks(
        self,
        pose_landmarks
    ) -> Dict[str, Landmark]:
        """Extract relevant landmarks from MediaPipe results."""
        landmarks = {}
        
        for idx, name in self.LANDMARK_NAMES.items():
            lm = pose_landmarks.landmark[idx]
            landmarks[name] = Landmark(
                x=lm.x,
                y=lm.y,
                z=lm.z,
                visibility=lm.visibility
            )
        
        return landmarks
    
    def _calculate_angles(self, landmarks: Dict[str, Landmark]) -> Dict[str, float]:
        """Calculate key angles for throw analysis."""
        angles = {}
        
        # Determine which side to analyze
        prefix = self.throwing_hand
        shoulder = landmarks.get(f'{prefix}_shoulder')
        elbow = landmarks.get(f'{prefix}_elbow')
        wrist = landmarks.get(f'{prefix}_wrist')
        hip = landmarks.get(f'{prefix}_hip')
        
        if all([shoulder, elbow, wrist]):
            # Elbow angle (shoulder-elbow-wrist)
            angles['elbow_angle'] = self._calculate_angle_3d(
                (shoulder.x, shoulder.y, shoulder.z),
                (elbow.x, elbow.y, elbow.z),
                (wrist.x, wrist.y, wrist.z)
            )
        
        if all([hip, shoulder, elbow]):
            # Shoulder angle (hip-shoulder-elbow)
            angles['shoulder_angle'] = self._calculate_angle_3d(
                (hip.x, hip.y, hip.z),
                (shoulder.x, shoulder.y, shoulder.z),
                (elbow.x, elbow.y, elbow.z)
            )
        
        # Calculate shoulder rotation (comparing both shoulders)
        left_shoulder = landmarks.get('left_shoulder')
        right_shoulder = landmarks.get('right_shoulder')
        
        if left_shoulder and right_shoulder:
            # Rotation relative to camera
            angles['shoulder_rotation'] = math.degrees(
                math.atan2(
                    right_shoulder.z - left_shoulder.z,
                    right_shoulder.x - left_shoulder.x
                )
            )
        
        # Calculate body lean
        nose = landmarks.get('nose')
        left_hip = landmarks.get('left_hip')
        right_hip = landmarks.get('right_hip')
        
        if nose and left_hip and right_hip:
            hip_center_x = (left_hip.x + right_hip.x) / 2
            hip_center_y = (left_hip.y + right_hip.y) / 2
            
            # Lean angle from vertical
            angles['body_lean'] = math.degrees(
                math.atan2(nose.x - hip_center_x, hip_center_y - nose.y)
            )
        
        # Calculate stance width
        left_ankle = landmarks.get('left_ankle')
        right_ankle = landmarks.get('right_ankle')
        
        if left_ankle and right_ankle:
            angles['stance_width'] = abs(left_ankle.x - right_ankle.x)
        
        # Wrist angle estimation (using elbow-wrist vector direction)
        if elbow and wrist:
            angles['wrist_angle'] = math.degrees(
                math.atan2(wrist.y - elbow.y, wrist.x - elbow.x)
            )
        
        return angles
    
    def _calculate_angle_3d(
        self,
        point1: Tuple[float, float, float],
        point2: Tuple[float, float, float],
        point3: Tuple[float, float, float]
    ) -> float:
        """
        Calculate angle at point2 formed by point1-point2-point3.
        
        Returns angle in degrees.
        """
        # Create vectors
        v1 = np.array([
            point1[0] - point2[0],
            point1[1] - point2[1],
            point1[2] - point2[2]
        ])
        v2 = np.array([
            point3[0] - point2[0],
            point3[1] - point2[1],
            point3[2] - point2[2]
        ])
        
        # Calculate angle using dot product
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        
        return math.degrees(math.acos(cos_angle))
    
    def _detect_throw_phase(
        self,
        angles: Dict[str, float],
        frame_number: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Detect if currently throwing and which phase.
        
        Uses elbow angle changes to detect throw phases:
        - Setup: Arm raised, elbow bent (~90-120 degrees)
        - Backswing: Elbow closing (angle decreasing)
        - Acceleration: Elbow extending rapidly (angle increasing)
        - Release: Full extension (~150-180 degrees)
        - Follow-through: Arm continuing forward
        """
        elbow_angle = angles.get('elbow_angle')
        if elbow_angle is None:
            return False, None
        
        is_throwing = False
        throw_phase = None
        
        # State machine for throw detection
        if self._throw_state == 'idle':
            # Looking for setup position
            if 80 <= elbow_angle <= 130:
                self._throw_state = 'setup'
                self._throw_start_frame = frame_number
                is_throwing = True
                throw_phase = 'setup'
        
        elif self._throw_state == 'setup':
            if self._previous_elbow_angle and elbow_angle < self._previous_elbow_angle - 5:
                # Elbow closing - backswing
                self._throw_state = 'backswing'
                is_throwing = True
                throw_phase = 'backswing'
            elif elbow_angle > 130:
                # Went straight to acceleration
                self._throw_state = 'acceleration'
                is_throwing = True
                throw_phase = 'acceleration'
        
        elif self._throw_state == 'backswing':
            if self._previous_elbow_angle and elbow_angle > self._previous_elbow_angle + 5:
                # Elbow opening - acceleration
                self._throw_state = 'acceleration'
                is_throwing = True
                throw_phase = 'acceleration'
            else:
                is_throwing = True
                throw_phase = 'backswing'
        
        elif self._throw_state == 'acceleration':
            if elbow_angle >= 150:
                # Near full extension - release
                self._throw_state = 'release'
                is_throwing = True
                throw_phase = 'release'
            else:
                is_throwing = True
                throw_phase = 'acceleration'
        
        elif self._throw_state == 'release':
            # Follow through
            self._throw_state = 'follow_through'
            is_throwing = True
            throw_phase = 'follow_through'
        
        elif self._throw_state == 'follow_through':
            # Check if throw is complete (arm returning)
            if self._previous_elbow_angle and elbow_angle < self._previous_elbow_angle - 10:
                # Throw complete, return to idle
                self._throw_state = 'idle'
                self._throw_start_frame = None
            else:
                is_throwing = True
                throw_phase = 'follow_through'
        
        # Timeout - reset if throw takes too long
        if self._throw_start_frame and frame_number - self._throw_start_frame > 60:
            self._throw_state = 'idle'
            self._throw_start_frame = None
        
        self._previous_elbow_angle = elbow_angle
        
        return is_throwing, throw_phase
    
    def draw_pose(
        self,
        frame: np.ndarray,
        pose_frame: PoseFrame,
        draw_angles: bool = True
    ) -> np.ndarray:
        """
        Draw pose landmarks and angles on frame.
        
        Args:
            frame: BGR image frame
            pose_frame: PoseFrame with landmark data
            draw_angles: Whether to draw angle annotations
            
        Returns:
            Annotated frame
        """
        annotated = frame.copy()
        h, w = annotated.shape[:2]
        
        # Draw landmarks
        for name, landmark in pose_frame.landmarks.items():
            if landmark.visibility > 0.5:
                x = int(landmark.x * w)
                y = int(landmark.y * h)
                
                # Color based on throwing arm
                if self.throwing_hand in name:
                    color = (0, 255, 0)  # Green for throwing arm
                else:
                    color = (255, 255, 255)  # White for other
                
                cv2.circle(annotated, (x, y), 5, color, -1)
        
        # Draw connections
        connections = [
            ('left_shoulder', 'right_shoulder'),
            ('left_shoulder', 'left_elbow'),
            ('left_elbow', 'left_wrist'),
            ('right_shoulder', 'right_elbow'),
            ('right_elbow', 'right_wrist'),
            ('left_shoulder', 'left_hip'),
            ('right_shoulder', 'right_hip'),
            ('left_hip', 'right_hip'),
        ]
        
        for start, end in connections:
            if start in pose_frame.landmarks and end in pose_frame.landmarks:
                lm1 = pose_frame.landmarks[start]
                lm2 = pose_frame.landmarks[end]
                
                if lm1.visibility > 0.5 and lm2.visibility > 0.5:
                    p1 = (int(lm1.x * w), int(lm1.y * h))
                    p2 = (int(lm2.x * w), int(lm2.y * h))
                    cv2.line(annotated, p1, p2, (200, 200, 200), 2)
        
        # Draw angles
        if draw_angles:
            y_offset = 30
            for angle_name, angle_value in pose_frame.angles.items():
                text = f"{angle_name}: {angle_value:.1f}"
                cv2.putText(
                    annotated, text, (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2
                )
                y_offset += 25
        
        # Draw throw phase
        if pose_frame.is_throwing and pose_frame.throw_phase:
            phase_text = f"Phase: {pose_frame.throw_phase.upper()}"
            cv2.putText(
                annotated, phase_text, (w - 250, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2
            )
        
        return annotated
    
    def reset_throw_state(self):
        """Reset throw detection state."""
        self._throw_state = 'idle'
        self._throw_start_frame = None
        self._previous_elbow_angle = None
    
    def release(self):
        """Release MediaPipe resources."""
        if self.pose is not None:
            self.pose.close()
            self.pose = None
    
    def __enter__(self):
        """Context manager entry."""
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
    
    def __del__(self):
        """Cleanup on deletion."""
        self.release()
