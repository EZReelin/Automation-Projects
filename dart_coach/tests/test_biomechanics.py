"""
Tests for the biomechanics module.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from dart_coach.biomechanics.pose_processor import PoseProcessor, Landmark, PoseFrame


class TestLandmark:
    """Tests for Landmark dataclass."""
    
    def test_landmark_creation(self):
        """Test creating a landmark."""
        landmark = Landmark(x=0.5, y=0.5, z=0.0, visibility=0.9)
        
        assert landmark.x == 0.5
        assert landmark.y == 0.5
        assert landmark.z == 0.0
        assert landmark.visibility == 0.9
    
    def test_landmark_to_dict(self):
        """Test converting landmark to dictionary."""
        landmark = Landmark(x=0.5, y=0.5, z=0.1, visibility=0.95)
        d = landmark.to_dict()
        
        assert d['x'] == 0.5
        assert d['y'] == 0.5
        assert d['z'] == 0.1
        assert d['visibility'] == 0.95


class TestPoseProcessor:
    """Tests for PoseProcessor class."""
    
    @pytest.fixture
    def processor(self):
        """Create pose processor instance."""
        return PoseProcessor(
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            throwing_hand='right'
        )
    
    def test_calculate_angle_3d(self, processor):
        """Test 3D angle calculation."""
        # Right angle test
        point1 = (0, 1, 0)
        point2 = (0, 0, 0)
        point3 = (1, 0, 0)
        
        angle = processor._calculate_angle_3d(point1, point2, point3)
        
        # Should be approximately 90 degrees
        assert 85 < angle < 95
    
    def test_calculate_angle_straight(self, processor):
        """Test angle calculation for straight line."""
        point1 = (0, 0, 0)
        point2 = (1, 0, 0)
        point3 = (2, 0, 0)
        
        angle = processor._calculate_angle_3d(point1, point2, point3)
        
        # Should be approximately 180 degrees
        assert 175 < angle < 185
    
    def test_throw_phase_detection_idle(self, processor):
        """Test throw phase detection in idle state."""
        angles = {'elbow_angle': 90}
        
        is_throwing, phase = processor._detect_throw_phase(angles, 0)
        
        # First detection with bent elbow should start setup
        assert is_throwing
        assert phase == 'setup'
    
    def test_throw_phase_reset(self, processor):
        """Test resetting throw state."""
        # Put into some state
        processor._throw_state = 'acceleration'
        processor._throw_start_frame = 10
        
        processor.reset_throw_state()
        
        assert processor._throw_state == 'idle'
        assert processor._throw_start_frame is None
    
    def test_landmark_names(self, processor):
        """Test landmark name mapping."""
        assert 0 in processor.LANDMARK_NAMES
        assert processor.LANDMARK_NAMES[0] == 'nose'
        assert processor.LANDMARK_NAMES[14] == 'right_elbow'
    
    def test_throw_phases(self, processor):
        """Test throw phases list."""
        expected_phases = ['setup', 'backswing', 'acceleration', 'release', 'follow_through']
        assert processor.THROW_PHASES == expected_phases


class TestPoseFrame:
    """Tests for PoseFrame dataclass."""
    
    def test_pose_frame_creation(self):
        """Test creating a pose frame."""
        landmarks = {
            'nose': Landmark(0.5, 0.3, 0.0, 0.9),
            'right_elbow': Landmark(0.6, 0.5, 0.1, 0.85)
        }
        
        frame = PoseFrame(
            frame_number=42,
            timestamp=1.5,
            landmarks=landmarks,
            angles={'elbow_angle': 120},
            is_throwing=True,
            throw_phase='acceleration'
        )
        
        assert frame.frame_number == 42
        assert frame.timestamp == 1.5
        assert frame.is_throwing
        assert frame.throw_phase == 'acceleration'
        assert 'nose' in frame.landmarks


class TestThrowAnalyzerLogic:
    """Tests for ThrowAnalyzer analysis logic."""
    
    def test_deviation_detection_early_release(self):
        """Test early release deviation detection."""
        from dart_coach.biomechanics.throw_analyzer import ThrowAnalyzer
        
        # Create analyzer instance
        analyzer = ThrowAnalyzer.__new__(ThrowAnalyzer)
        analyzer.IDEAL_FORM = ThrowAnalyzer.IDEAL_FORM
        analyzer.DEVIATION_THRESHOLDS = ThrowAnalyzer.DEVIATION_THRESHOLDS
        
        # Phase analysis with early release (elbow not fully extended)
        phase_analysis = {
            'release': {
                'detected': True,
                'elbow_angle': 120  # Should be ~160
            }
        }
        
        # Mock release frame
        release_frame = Mock()
        release_frame.angles = {'shoulder_rotation': 5, 'body_lean': 5}
        
        deviations = analyzer._detect_deviations(phase_analysis, release_frame)
        
        # Should detect early release
        dev_types = [d['type'] for d in deviations]
        assert 'early_release' in dev_types
    
    def test_quality_score_calculation(self):
        """Test throw quality score calculation."""
        from dart_coach.biomechanics.throw_analyzer import ThrowAnalyzer
        
        analyzer = ThrowAnalyzer.__new__(ThrowAnalyzer)
        
        # No deviations, all phases detected
        phase_analysis = {
            'setup': {'detected': True},
            'backswing': {'detected': True},
            'acceleration': {'detected': True},
            'release': {'detected': True},
            'follow_through': {'detected': True}
        }
        deviations = []
        
        score = analyzer._calculate_quality_score(phase_analysis, deviations)
        
        # Should be high score (100 base + 10 for all phases)
        assert score > 95
    
    def test_quality_score_with_deviations(self):
        """Test quality score with deviations."""
        from dart_coach.biomechanics.throw_analyzer import ThrowAnalyzer
        
        analyzer = ThrowAnalyzer.__new__(ThrowAnalyzer)
        
        phase_analysis = {
            'setup': {'detected': True},
            'release': {'detected': True}
        }
        
        deviations = [
            {'type': 'early_release', 'severity': 'significant'},
            {'type': 'body_sway', 'severity': 'moderate'}
        ]
        
        score = analyzer._calculate_quality_score(phase_analysis, deviations)
        
        # Score should be reduced
        assert score < 90


class TestCameraHandler:
    """Tests for CameraHandler class."""
    
    def test_camera_info_not_initialized(self):
        """Test getting camera info when not initialized."""
        from dart_coach.biomechanics.camera_handler import CameraHandler
        
        handler = CameraHandler.__new__(CameraHandler)
        handler.cap = None
        handler.device_id = 0
        handler._recording = False
        
        info = handler.get_camera_info()
        
        assert info == {}


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
