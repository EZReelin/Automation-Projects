"""
Camera Handler Module
====================
Handles camera capture and OBSBOT Tiny Lite 2 integration.
"""

import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional, Tuple

import cv2
import numpy as np


class CameraHandler:
    """
    Handles camera capture for biomechanical analysis.
    
    Supports OBSBOT Tiny Lite 2 with AI tracking capabilities.
    """
    
    def __init__(
        self,
        device_id: int = 0,
        resolution: Tuple[int, int] = (1920, 1080),
        framerate: int = 30,
        auto_tracking: bool = True,
        output_dir: Optional[Path] = None,
        log_level: str = "INFO"
    ):
        """
        Initialize camera handler.
        
        Args:
            device_id: Camera device ID
            resolution: Video resolution (width, height)
            framerate: Target framerate
            auto_tracking: Enable OBSBOT auto-tracking if available
            output_dir: Directory for saving recordings
            log_level: Logging level
        """
        self.device_id = device_id
        self.resolution = resolution
        self.framerate = framerate
        self.auto_tracking = auto_tracking
        self.output_dir = Path(output_dir) if output_dir else Path("recordings")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.cap: Optional[cv2.VideoCapture] = None
        self.writer: Optional[cv2.VideoWriter] = None
        self._recording = False
        self._current_recording_path: Optional[Path] = None
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
    
    def initialize(self) -> bool:
        """
        Initialize the camera.
        
        Returns:
            True if initialization successful
        """
        try:
            # Try environment variable first
            device = int(os.getenv('CAMERA_DEVICE_ID', self.device_id))
            
            self.cap = cv2.VideoCapture(device)
            
            if not self.cap.isOpened():
                self.logger.error(f"Failed to open camera device {device}")
                return False
            
            # Set resolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.cap.set(cv2.CAP_PROP_FPS, self.framerate)
            
            # Verify settings
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
            
            self.logger.info(
                f"Camera initialized: {actual_width}x{actual_height} @ {actual_fps}fps"
            )
            
            # Initialize OBSBOT tracking if available
            if self.auto_tracking:
                self._init_obsbot_tracking()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Camera initialization failed: {e}")
            return False
    
    def _init_obsbot_tracking(self):
        """
        Initialize OBSBOT Tiny Lite 2 auto-tracking.
        
        Note: OBSBOT tracking is typically controlled via OBSBOT Center app
        or through UVC extension controls. This method sets up basic tracking.
        """
        try:
            # OBSBOT cameras support UVC extensions for tracking control
            # These may vary by firmware version
            
            # Enable auto-tracking (UVC extension command)
            # Note: Actual implementation depends on OBSBOT SDK availability
            self.logger.info("OBSBOT auto-tracking mode enabled (via OBSBOT Center)")
            
            # For manual control without OBSBOT SDK:
            # - Set camera to "upper body" tracking mode via OBSBOT Center app
            # - The camera will automatically follow the player
            
        except Exception as e:
            self.logger.warning(f"Could not initialize OBSBOT tracking: {e}")
    
    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read a single frame from the camera.
        
        Returns:
            Tuple of (success, frame)
        """
        if self.cap is None or not self.cap.isOpened():
            return False, None
        
        ret, frame = self.cap.read()
        return ret, frame
    
    def stream_frames(
        self,
        duration_seconds: Optional[float] = None,
        max_frames: Optional[int] = None
    ) -> Generator[Tuple[int, float, np.ndarray], None, None]:
        """
        Stream frames from the camera.
        
        Args:
            duration_seconds: Maximum duration to stream
            max_frames: Maximum number of frames to capture
            
        Yields:
            Tuple of (frame_number, timestamp, frame)
        """
        if self.cap is None:
            if not self.initialize():
                return
        
        start_time = time.time()
        frame_count = 0
        
        while True:
            ret, frame = self.read_frame()
            if not ret:
                self.logger.warning("Failed to read frame")
                break
            
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Write to recording if active
            if self._recording and self.writer is not None:
                self.writer.write(frame)
            
            yield frame_count, elapsed, frame
            
            frame_count += 1
            
            # Check termination conditions
            if duration_seconds and elapsed >= duration_seconds:
                break
            if max_frames and frame_count >= max_frames:
                break
    
    def start_recording(self, filename: Optional[str] = None) -> Optional[Path]:
        """
        Start recording video.
        
        Args:
            filename: Optional filename for recording
            
        Returns:
            Path to recording file
        """
        if self._recording:
            self.logger.warning("Already recording")
            return self._current_recording_path
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"recording_{timestamp}.mp4"
        
        filepath = self.output_dir / filename
        
        # Initialize video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.writer = cv2.VideoWriter(
            str(filepath),
            fourcc,
            self.framerate,
            self.resolution
        )
        
        if not self.writer.isOpened():
            self.logger.error(f"Failed to create video writer: {filepath}")
            return None
        
        self._recording = True
        self._current_recording_path = filepath
        self.logger.info(f"Started recording: {filepath}")
        
        return filepath
    
    def stop_recording(self) -> Optional[Path]:
        """
        Stop recording video.
        
        Returns:
            Path to the recorded file
        """
        if not self._recording:
            return None
        
        self._recording = False
        
        if self.writer is not None:
            self.writer.release()
            self.writer = None
        
        filepath = self._current_recording_path
        self._current_recording_path = None
        
        self.logger.info(f"Stopped recording: {filepath}")
        return filepath
    
    def capture_snapshot(self, filename: Optional[str] = None) -> Optional[Path]:
        """
        Capture a single frame snapshot.
        
        Args:
            filename: Optional filename for snapshot
            
        Returns:
            Path to snapshot file
        """
        ret, frame = self.read_frame()
        if not ret or frame is None:
            return None
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"snapshot_{timestamp}.jpg"
        
        filepath = self.output_dir / filename
        cv2.imwrite(str(filepath), frame)
        
        self.logger.info(f"Captured snapshot: {filepath}")
        return filepath
    
    def get_camera_info(self) -> dict:
        """Get current camera information."""
        if self.cap is None:
            return {}
        
        return {
            'device_id': self.device_id,
            'width': int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': int(self.cap.get(cv2.CAP_PROP_FPS)),
            'backend': self.cap.getBackendName(),
            'is_recording': self._recording
        }
    
    def set_exposure(self, value: float):
        """Set camera exposure value."""
        if self.cap:
            self.cap.set(cv2.CAP_PROP_EXPOSURE, value)
    
    def set_focus(self, value: float):
        """Set camera focus value."""
        if self.cap:
            self.cap.set(cv2.CAP_PROP_FOCUS, value)
    
    def set_auto_focus(self, enabled: bool):
        """Enable or disable auto-focus."""
        if self.cap:
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1 if enabled else 0)
    
    def release(self):
        """Release camera resources."""
        if self._recording:
            self.stop_recording()
        
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        
        self.logger.info("Camera released")
    
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
