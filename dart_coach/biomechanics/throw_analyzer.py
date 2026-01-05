"""
Throw Analyzer Module
====================
Complete dart throw biomechanical analysis system.
"""

import json
import logging
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from .camera_handler import CameraHandler
from .pose_processor import PoseFrame, PoseProcessor


class ThrowAnalyzer:
    """
    Complete biomechanical throw analyzer.
    
    Integrates camera capture and pose processing to analyze
    dart throwing form and provide insights.
    """
    
    # Ideal form benchmarks (adjustable per player)
    IDEAL_FORM = {
        'elbow_angle_at_release': 160,  # degrees
        'shoulder_rotation_max': 20,     # degrees
        'body_lean_max': 15,             # degrees
        'release_height_ratio': 0.85,    # relative to shoulder height
        'follow_through_extension': 0.9  # arm extension ratio
    }
    
    # Deviation thresholds
    DEVIATION_THRESHOLDS = {
        'elbow_angle': {'minor': 10, 'moderate': 20, 'significant': 30},
        'shoulder_rotation': {'minor': 5, 'moderate': 10, 'significant': 15},
        'body_lean': {'minor': 5, 'moderate': 10, 'significant': 20},
    }
    
    def __init__(
        self,
        data_dir: Path,
        camera_config: Optional[Dict] = None,
        pose_config: Optional[Dict] = None,
        session_reference: Optional[str] = None,
        log_level: str = "INFO"
    ):
        """
        Initialize throw analyzer.
        
        Args:
            data_dir: Directory for storing analysis data
            camera_config: Camera configuration dict
            pose_config: Pose processor configuration dict
            session_reference: Reference to associated practice session
            log_level: Logging level
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_reference = session_reference
        
        # Initialize components with configs
        camera_config = camera_config or {}
        pose_config = pose_config or {}
        
        self.camera = CameraHandler(
            output_dir=self.data_dir / "recordings",
            **camera_config
        )
        self.pose_processor = PoseProcessor(**pose_config)
        
        # Analysis state
        self._analysis_id: Optional[str] = None
        self._start_time: Optional[datetime] = None
        self._throws: List[Dict[str, Any]] = []
        self._current_throw_frames: List[PoseFrame] = []
        self._throw_count = 0
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
    
    def start_session(self, record_video: bool = True) -> str:
        """
        Start a new analysis session.
        
        Args:
            record_video: Whether to record video during session
            
        Returns:
            Analysis session ID
        """
        self._analysis_id = f"bio_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._start_time = datetime.now()
        self._throws = []
        self._current_throw_frames = []
        self._throw_count = 0
        
        # Initialize camera
        if not self.camera.initialize():
            raise RuntimeError("Failed to initialize camera")
        
        # Start recording if requested
        if record_video:
            self.camera.start_recording(f"{self._analysis_id}.mp4")
        
        # Initialize pose processor
        self.pose_processor.initialize()
        self.pose_processor.reset_throw_state()
        
        self.logger.info(f"Started analysis session: {self._analysis_id}")
        return self._analysis_id
    
    def process_live(
        self,
        duration_seconds: float,
        display: bool = False,
        callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Process live camera feed for specified duration.
        
        Args:
            duration_seconds: Duration to capture and analyze
            display: Whether to display video with annotations
            callback: Optional callback for each processed frame
            
        Returns:
            Analysis results dictionary
        """
        if self._analysis_id is None:
            self.start_session()
        
        self.logger.info(f"Processing live feed for {duration_seconds} seconds")
        
        previous_throwing = False
        
        for frame_num, timestamp, frame in self.camera.stream_frames(
            duration_seconds=duration_seconds
        ):
            # Process frame
            pose_frame = self.pose_processor.process_frame(
                frame, frame_num, timestamp
            )
            
            if pose_frame:
                # Track throw state transitions
                if pose_frame.is_throwing:
                    self._current_throw_frames.append(pose_frame)
                    
                    # New throw started
                    if not previous_throwing:
                        self.logger.debug(f"Throw {self._throw_count + 1} started at frame {frame_num}")
                
                elif previous_throwing and not pose_frame.is_throwing:
                    # Throw completed
                    if len(self._current_throw_frames) >= 5:  # Minimum frames for valid throw
                        self._finalize_throw()
                    self._current_throw_frames = []
                
                previous_throwing = pose_frame.is_throwing
                
                # Display if requested
                if display:
                    annotated = self.pose_processor.draw_pose(frame, pose_frame)
                    cv2.imshow('Throw Analysis', annotated)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                
                # Callback
                if callback:
                    callback(frame_num, pose_frame)
            
            elif display:
                cv2.imshow('Throw Analysis', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        
        if display:
            cv2.destroyAllWindows()
        
        return self.get_analysis_results()
    
    def process_video_file(
        self,
        video_path: Path,
        display: bool = False
    ) -> Dict[str, Any]:
        """
        Process a pre-recorded video file.
        
        Args:
            video_path: Path to video file
            display: Whether to display video during processing
            
        Returns:
            Analysis results dictionary
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        self._analysis_id = f"bio_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._start_time = datetime.now()
        self._throws = []
        self._current_throw_frames = []
        self._throw_count = 0
        
        self.pose_processor.initialize()
        self.pose_processor.reset_throw_state()
        
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        frame_num = 0
        previous_throwing = False
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            timestamp = frame_num / fps
            
            pose_frame = self.pose_processor.process_frame(
                frame, frame_num, timestamp
            )
            
            if pose_frame:
                if pose_frame.is_throwing:
                    self._current_throw_frames.append(pose_frame)
                    if not previous_throwing:
                        self.logger.debug(f"Throw {self._throw_count + 1} started at frame {frame_num}")
                
                elif previous_throwing:
                    if len(self._current_throw_frames) >= 5:
                        self._finalize_throw()
                    self._current_throw_frames = []
                
                previous_throwing = pose_frame.is_throwing
                
                if display:
                    annotated = self.pose_processor.draw_pose(frame, pose_frame)
                    cv2.imshow('Video Analysis', annotated)
                    if cv2.waitKey(int(1000/fps)) & 0xFF == ord('q'):
                        break
            
            frame_num += 1
        
        cap.release()
        if display:
            cv2.destroyAllWindows()
        
        return self.get_analysis_results()
    
    def _finalize_throw(self):
        """Finalize analysis of completed throw."""
        if not self._current_throw_frames:
            return
        
        self._throw_count += 1
        
        # Extract throw data
        throw_data = self._analyze_throw_sequence(self._current_throw_frames)
        throw_data['throw_number'] = self._throw_count
        throw_data['timestamp'] = self._current_throw_frames[0].timestamp
        
        self._throws.append(throw_data)
        self.logger.info(
            f"Throw {self._throw_count} analyzed: "
            f"quality={throw_data.get('throw_quality_score', 0):.1f}"
        )
    
    def _analyze_throw_sequence(
        self,
        frames: List[PoseFrame]
    ) -> Dict[str, Any]:
        """
        Analyze a complete throw sequence.
        
        Args:
            frames: List of PoseFrame for the throw
            
        Returns:
            Throw analysis dictionary
        """
        # Group frames by phase
        phases = defaultdict(list)
        for frame in frames:
            if frame.throw_phase:
                phases[frame.throw_phase].append(frame)
        
        # Analyze each phase
        phase_analysis = {}
        
        for phase_name in ['setup', 'backswing', 'acceleration', 'release', 'follow_through']:
            phase_frames = phases.get(phase_name, [])
            if phase_frames:
                phase_analysis[phase_name] = self._analyze_phase(
                    phase_name, phase_frames
                )
            else:
                phase_analysis[phase_name] = {'detected': False}
        
        # Find release frame (most extended elbow in release/acceleration phase)
        release_frame = self._find_release_frame(frames)
        
        # Extract keypoints at release
        keypoints = {}
        if release_frame:
            for name, landmark in release_frame.landmarks.items():
                keypoints[name] = landmark.to_dict()
        
        # Detect deviations
        deviations = self._detect_deviations(phase_analysis, release_frame)
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(phase_analysis, deviations)
        
        return {
            'throw_quality_score': quality_score,
            'phases': phase_analysis,
            'keypoints': keypoints,
            'deviations': deviations
        }
    
    def _analyze_phase(
        self,
        phase_name: str,
        frames: List[PoseFrame]
    ) -> Dict[str, Any]:
        """Analyze a single throw phase."""
        if not frames:
            return {'detected': False}
        
        # Calculate duration
        duration_ms = (frames[-1].timestamp - frames[0].timestamp) * 1000
        
        # Get angle statistics
        elbow_angles = [f.angles.get('elbow_angle', 0) for f in frames]
        shoulder_angles = [f.angles.get('shoulder_angle', 0) for f in frames]
        
        analysis = {
            'detected': True,
            'duration_ms': duration_ms,
        }
        
        if phase_name == 'setup':
            analysis.update({
                'stance_width_cm': frames[0].angles.get('stance_width', 0) * 100,
                'body_alignment_degrees': frames[0].angles.get('body_lean', 0),
                'shoulder_position': frames[0].landmarks.get(
                    'right_shoulder', None
                ).to_dict() if frames[0].landmarks.get('right_shoulder') else None
            })
        
        elif phase_name == 'backswing':
            analysis.update({
                'elbow_angle_start': elbow_angles[0] if elbow_angles else 0,
                'elbow_angle_end': elbow_angles[-1] if elbow_angles else 0,
                'shoulder_movement': max(shoulder_angles) - min(shoulder_angles) if shoulder_angles else 0
            })
        
        elif phase_name == 'acceleration':
            if len(elbow_angles) >= 2:
                # Calculate extension rate
                angle_change = elbow_angles[-1] - elbow_angles[0]
                analysis['elbow_extension_rate'] = angle_change / (duration_ms / 1000) if duration_ms > 0 else 0
            analysis['wrist_snap_detected'] = self._detect_wrist_snap(frames)
        
        elif phase_name == 'release':
            analysis.update({
                'timestamp_ms': frames[0].timestamp * 1000,
                'elbow_angle': elbow_angles[0] if elbow_angles else 0,
                'shoulder_angle': shoulder_angles[0] if shoulder_angles else 0,
                'wrist_angle': frames[0].angles.get('wrist_angle', 0)
            })
            
            # Release point
            wrist = frames[0].landmarks.get('right_wrist')
            if wrist:
                analysis['release_point'] = wrist.to_dict()
        
        elif phase_name == 'follow_through':
            analysis.update({
                'arm_extension': max(elbow_angles) if elbow_angles else 0,
                'pointing_at_target': self._check_target_alignment(frames[-1])
            })
            
            wrist = frames[-1].landmarks.get('right_wrist')
            if wrist:
                analysis['hand_finish_position'] = wrist.to_dict()
        
        return analysis
    
    def _find_release_frame(self, frames: List[PoseFrame]) -> Optional[PoseFrame]:
        """Find the frame closest to the release point."""
        release_candidates = [f for f in frames if f.throw_phase in ['release', 'acceleration']]
        
        if not release_candidates:
            return None
        
        # Find frame with maximum elbow extension
        return max(
            release_candidates,
            key=lambda f: f.angles.get('elbow_angle', 0)
        )
    
    def _detect_wrist_snap(self, frames: List[PoseFrame]) -> bool:
        """Detect if wrist snap occurred during acceleration."""
        if len(frames) < 3:
            return False
        
        wrist_angles = [f.angles.get('wrist_angle', 0) for f in frames]
        
        # Look for rapid change in wrist angle
        for i in range(1, len(wrist_angles)):
            if abs(wrist_angles[i] - wrist_angles[i-1]) > 15:
                return True
        
        return False
    
    def _check_target_alignment(self, frame: PoseFrame) -> bool:
        """Check if follow-through is pointing at target."""
        wrist = frame.landmarks.get('right_wrist')
        elbow = frame.landmarks.get('right_elbow')
        
        if not wrist or not elbow:
            return False
        
        # Check if arm is roughly horizontal and forward
        vertical_diff = abs(wrist.y - elbow.y)
        forward_diff = wrist.z - elbow.z
        
        return vertical_diff < 0.1 and forward_diff < 0
    
    def _detect_deviations(
        self,
        phase_analysis: Dict[str, Dict],
        release_frame: Optional[PoseFrame]
    ) -> List[Dict[str, Any]]:
        """Detect form deviations from ideal."""
        deviations = []
        
        # Check elbow angle at release
        release = phase_analysis.get('release', {})
        if release.get('detected'):
            elbow_angle = release.get('elbow_angle', 0)
            ideal = self.IDEAL_FORM['elbow_angle_at_release']
            diff = abs(elbow_angle - ideal)
            
            if diff > self.DEVIATION_THRESHOLDS['elbow_angle']['significant']:
                if elbow_angle < ideal:
                    deviations.append({
                        'type': 'early_release',
                        'severity': 'significant',
                        'description': f'Early release - elbow not fully extended ({elbow_angle:.0f}°)'
                    })
                else:
                    deviations.append({
                        'type': 'late_release',
                        'severity': 'significant',
                        'description': f'Late release - over-extended ({elbow_angle:.0f}°)'
                    })
            elif diff > self.DEVIATION_THRESHOLDS['elbow_angle']['moderate']:
                deviations.append({
                    'type': 'elbow_angle_deviation',
                    'severity': 'moderate',
                    'description': f'Suboptimal elbow angle at release ({elbow_angle:.0f}°)'
                })
        
        # Check shoulder rotation
        setup = phase_analysis.get('setup', {})
        if setup.get('detected') and release_frame:
            shoulder_rotation = abs(release_frame.angles.get('shoulder_rotation', 0))
            if shoulder_rotation > self.IDEAL_FORM['shoulder_rotation_max']:
                severity = 'significant' if shoulder_rotation > 30 else 'moderate'
                deviations.append({
                    'type': 'shoulder_rotation',
                    'severity': severity,
                    'description': f'Excessive shoulder rotation ({shoulder_rotation:.0f}°)'
                })
        
        # Check body sway
        if release_frame:
            body_lean = abs(release_frame.angles.get('body_lean', 0))
            if body_lean > self.IDEAL_FORM['body_lean_max']:
                severity = 'significant' if body_lean > 25 else 'moderate'
                deviations.append({
                    'type': 'body_sway',
                    'severity': severity,
                    'description': f'Body lean during throw ({body_lean:.0f}°)'
                })
        
        # Check follow-through
        follow_through = phase_analysis.get('follow_through', {})
        if follow_through.get('detected'):
            if not follow_through.get('pointing_at_target', True):
                deviations.append({
                    'type': 'incomplete_follow_through',
                    'severity': 'minor',
                    'description': 'Follow-through not pointing at target'
                })
        
        return deviations
    
    def _calculate_quality_score(
        self,
        phase_analysis: Dict[str, Dict],
        deviations: List[Dict]
    ) -> float:
        """Calculate overall throw quality score (0-100)."""
        score = 100.0
        
        # Deduction for deviations
        severity_deductions = {
            'minor': 5,
            'moderate': 10,
            'significant': 20
        }
        
        for deviation in deviations:
            severity = deviation.get('severity', 'minor')
            score -= severity_deductions.get(severity, 5)
        
        # Bonus for complete phases
        phases_detected = sum(
            1 for p in phase_analysis.values()
            if p.get('detected', False)
        )
        score += (phases_detected / 5) * 10  # Up to 10 bonus points
        
        return max(0, min(100, score))
    
    def get_analysis_results(self) -> Dict[str, Any]:
        """Get complete analysis results for the session."""
        if not self._analysis_id:
            return {}
        
        duration = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
        
        # Calculate aggregate statistics
        aggregate = self._calculate_aggregate_stats()
        
        results = {
            'analysis_id': self._analysis_id,
            'timestamp': self._start_time.isoformat() if self._start_time else None,
            'data_source': 'biomechanics',
            'session_reference': self.session_reference,
            'camera_settings': self.camera.get_camera_info(),
            'analysis_duration_seconds': duration,
            'total_throws_analyzed': len(self._throws),
            'throws': self._throws,
            'aggregate_analysis': aggregate
        }
        
        return results
    
    def _calculate_aggregate_stats(self) -> Dict[str, Any]:
        """Calculate aggregate statistics across all throws."""
        if not self._throws:
            return {}
        
        # Collect quality scores
        quality_scores = [t.get('throw_quality_score', 0) for t in self._throws]
        
        # Count deviations
        deviation_counts = defaultdict(int)
        for throw in self._throws:
            for dev in throw.get('deviations', []):
                deviation_counts[dev['type']] += 1
        
        # Sort deviations by frequency
        most_common = sorted(
            deviation_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Calculate release point variance
        release_points = []
        elbow_angles = []
        
        for throw in self._throws:
            release = throw.get('phases', {}).get('release', {})
            if release.get('detected'):
                point = release.get('release_point')
                if point:
                    release_points.append((point['x'], point['y'], point['z']))
                angle = release.get('elbow_angle')
                if angle:
                    elbow_angles.append(angle)
        
        # Calculate variances
        release_variance = 0
        avg_release_point = {}
        if len(release_points) >= 2:
            xs, ys, zs = zip(*release_points)
            avg_release_point = {
                'x': statistics.mean(xs),
                'y': statistics.mean(ys),
                'z': statistics.mean(zs)
            }
            release_variance = (
                statistics.variance(xs) +
                statistics.variance(ys) +
                statistics.variance(zs)
            )
        
        elbow_variance = statistics.variance(elbow_angles) if len(elbow_angles) >= 2 else 0
        
        # Identify improvement areas
        improvement_areas = []
        for dev_type, count in most_common[:3]:
            if count >= 2:
                improvement_areas.append(dev_type.replace('_', ' ').title())
        
        return {
            'consistency_score': 100 - (release_variance * 100 + elbow_variance) / 2,
            'average_release_point': avg_release_point,
            'release_point_variance': release_variance,
            'average_elbow_angle_at_release': statistics.mean(elbow_angles) if elbow_angles else 0,
            'elbow_angle_variance': elbow_variance,
            'most_common_deviations': [
                {
                    'type': dev_type,
                    'frequency': count,
                    'percentage': (count / len(self._throws)) * 100
                }
                for dev_type, count in most_common[:5]
            ],
            'improvement_areas': improvement_areas
        }
    
    def save_results(self, filename: Optional[str] = None) -> Path:
        """
        Save analysis results to JSON file.
        
        Args:
            filename: Optional filename (defaults to analysis_id.json)
            
        Returns:
            Path to saved file
        """
        results = self.get_analysis_results()
        
        if filename is None:
            filename = f"{self._analysis_id}.json"
        
        filepath = self.data_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)
        
        self.logger.info(f"Saved analysis results to {filepath}")
        return filepath
    
    def stop_session(self) -> Path:
        """
        Stop the current analysis session.
        
        Returns:
            Path to saved results file
        """
        # Stop recording
        self.camera.stop_recording()
        
        # Save results
        filepath = self.save_results()
        
        # Cleanup
        self.camera.release()
        self.pose_processor.release()
        
        self.logger.info(f"Session stopped. Results saved to {filepath}")
        return filepath
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._analysis_id:
            self.stop_session()
