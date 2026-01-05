"""
Observation Processor Module
===========================
Processes transcribed voice observations and extracts insights.
"""

import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .transcriber import Transcriber
from .voice_recorder import VoiceRecorder


class ObservationProcessor:
    """
    Processes voice observations to extract structured insights.
    
    Categorizes observations, detects keywords, and synchronizes
    with throw data for contextual analysis.
    """
    
    # Keywords for categorization
    CATEGORY_KEYWORDS = {
        'technique': [
            'grip', 'stance', 'release', 'follow-through', 'follow through',
            'aim', 'rhythm', 'timing', 'elbow', 'wrist', 'shoulder', 'throw',
            'dart', 'arm', 'motion', 'smooth', 'snap', 'flick', 'pull',
            'push', 'position', 'alignment', 'setup', 'backswing'
        ],
        'mental_state': [
            'focus', 'focused', 'confident', 'confidence', 'nervous',
            'frustrated', 'frustrated', 'relaxed', 'concentration',
            'distracted', 'calm', 'pressure', 'stressed', 'anxious',
            'zone', 'flow', 'comfortable', 'uncomfortable', 'thinking',
            'overthinking', 'automatic', 'natural', 'forced'
        ],
        'physical_state': [
            'tired', 'fresh', 'sore', 'warmed-up', 'warm', 'cold', 'stiff',
            'loose', 'tight', 'fatigue', 'energy', 'strength', 'weak',
            'strong', 'eyes', 'vision', 'balance', 'stable', 'shaky'
        ],
        'target_selection': [
            'target', 'segment', 'double', 'triple', 'treble', 'bullseye',
            'bull', '20', '19', '18', '17', '16', 'checkout', 'finish',
            'setup shot', 'leave', 'out'
        ],
        'equipment': [
            'dart', 'flight', 'shaft', 'point', 'barrel', 'weight', 'grip',
            'board', 'lighting', 'oche', 'throw line'
        ],
        'environmental': [
            'light', 'lighting', 'noise', 'temperature', 'hot', 'humid',
            'draft', 'wind', 'crowded', 'quiet', 'distraction'
        ],
        'performance': [
            'hit', 'miss', 'close', 'grouping', 'tight', 'scattered',
            'consistent', 'inconsistent', 'average', 'good', 'bad',
            'great', 'terrible', 'improving', 'worse', 'better',
            '180', 'ton', 'ton-eighty', 'checkout', 'bust'
        ]
    }
    
    # Sentiment indicators
    POSITIVE_WORDS = [
        'good', 'great', 'excellent', 'perfect', 'nice', 'better',
        'improving', 'confident', 'relaxed', 'smooth', 'comfortable',
        'consistent', 'focused', 'strong', 'fresh', 'yes', 'beautiful'
    ]
    
    NEGATIVE_WORDS = [
        'bad', 'terrible', 'poor', 'worse', 'frustrated', 'nervous',
        'tight', 'stiff', 'tired', 'distracted', 'inconsistent',
        'miss', 'missed', 'off', 'wrong', 'problem', 'issue', 'no'
    ]
    
    def __init__(
        self,
        data_dir: Path,
        session_reference: Optional[str] = None,
        whisper_model: str = "base",
        log_level: str = "INFO"
    ):
        """
        Initialize observation processor.
        
        Args:
            data_dir: Directory for storing processed data
            session_reference: Reference to associated practice session
            whisper_model: Whisper model size for transcription
            log_level: Logging level
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_reference = session_reference
        
        self.recorder = VoiceRecorder(
            output_dir=self.data_dir / "recordings"
        )
        self.transcriber = Transcriber(model_name=whisper_model)
        
        self._observation_id: Optional[str] = None
        self._start_time: Optional[datetime] = None
        self._observations: List[Dict[str, Any]] = []
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
    
    def start_session(self, session_reference: Optional[str] = None) -> str:
        """
        Start a new observation session.
        
        Args:
            session_reference: Reference to associated practice session
            
        Returns:
            Observation session ID
        """
        self._observation_id = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._start_time = datetime.now()
        self._observations = []
        
        if session_reference:
            self.session_reference = session_reference
        
        # Start recording
        self.recorder.start_recording(self._observation_id)
        
        self.logger.info(f"Started observation session: {self._observation_id}")
        return self._observation_id
    
    def stop_session(self) -> Dict[str, Any]:
        """
        Stop session and process all recordings.
        
        Returns:
            Complete observation data
        """
        # Stop recording
        session_id, chunk_files = self.recorder.stop_recording()
        
        # Transcribe all chunks
        transcriptions = self.transcriber.transcribe_chunks(chunk_files)
        
        # Process observations
        self._process_transcriptions(transcriptions)
        
        # Generate session summary
        results = self._generate_results()
        
        # Save results
        self._save_results(results)
        
        self.logger.info(
            f"Session complete. Processed {len(self._observations)} observations."
        )
        
        return results
    
    def _process_transcriptions(self, transcriptions: List[Dict[str, Any]]):
        """Process transcriptions into structured observations."""
        observation_number = 0
        
        for trans in transcriptions:
            for segment in trans.get('segments', []):
                text = segment.get('text', '').strip()
                if not text:
                    continue
                
                observation_number += 1
                
                # Extract observation data
                observation = {
                    'observation_number': observation_number,
                    'timestamp_offset': segment['start'],
                    'timestamp_absolute': (
                        self._start_time.isoformat()
                        if self._start_time else None
                    ),
                    'transcription': text,
                    'duration_seconds': segment['end'] - segment['start'],
                    'confidence': self._convert_logprob_to_confidence(
                        segment.get('confidence', 0)
                    ),
                    'categories': self._categorize_observation(text),
                    'detected_keywords': self._extract_keywords(text),
                    'sentiment': self._analyze_sentiment(text),
                    'associated_throw': self._estimate_throw_number(
                        segment['start']
                    ),
                    'parsed_insights': self._parse_insights(text)
                }
                
                self._observations.append(observation)
    
    def _convert_logprob_to_confidence(self, logprob: float) -> float:
        """Convert log probability to 0-1 confidence score."""
        import math
        # Whisper returns negative log probs, higher is better
        # Typical range is -1 to 0, map to 0-1
        return min(1.0, max(0.0, math.exp(logprob)))
    
    def _categorize_observation(self, text: str) -> List[str]:
        """Categorize observation based on keywords."""
        text_lower = text.lower()
        categories = []
        
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    if category not in categories:
                        categories.append(category)
                    break
        
        if not categories:
            categories.append('general')
        
        return categories
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from observation."""
        text_lower = text.lower()
        found_keywords = []
        
        all_keywords = []
        for keywords in self.CATEGORY_KEYWORDS.values():
            all_keywords.extend(keywords)
        
        for keyword in set(all_keywords):
            if keyword in text_lower:
                found_keywords.append(keyword)
        
        return found_keywords
    
    def _analyze_sentiment(self, text: str) -> str:
        """Analyze sentiment of observation."""
        text_lower = text.lower()
        
        positive_count = sum(1 for word in self.POSITIVE_WORDS if word in text_lower)
        negative_count = sum(1 for word in self.NEGATIVE_WORDS if word in text_lower)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'
    
    def _estimate_throw_number(self, timestamp: float) -> Optional[int]:
        """
        Estimate which throw the observation relates to.
        
        Assumes approximately 10 seconds per throw cycle.
        """
        # This is a rough estimate; actual synchronization should
        # use biomechanics data timestamps
        throws_per_minute = 6  # Approximate
        estimated_throw = int(timestamp / 60 * throws_per_minute) + 1
        return estimated_throw if estimated_throw > 0 else None
    
    def _parse_insights(self, text: str) -> Dict[str, List[str]]:
        """Parse structured insights from observation text."""
        insights = {
            'technique_notes': [],
            'mental_notes': [],
            'physical_notes': [],
            'action_items': []
        }
        
        text_lower = text.lower()
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_lower = sentence.lower()
            
            # Categorize sentence
            if any(kw in sentence_lower for kw in self.CATEGORY_KEYWORDS['technique']):
                insights['technique_notes'].append(sentence)
            
            if any(kw in sentence_lower for kw in self.CATEGORY_KEYWORDS['mental_state']):
                insights['mental_notes'].append(sentence)
            
            if any(kw in sentence_lower for kw in self.CATEGORY_KEYWORDS['physical_state']):
                insights['physical_notes'].append(sentence)
            
            # Detect action items
            action_patterns = [
                r'need to', r'should', r'try to', r'remember to',
                r'focus on', r'work on', r"don't forget"
            ]
            
            if any(re.search(pattern, sentence_lower) for pattern in action_patterns):
                insights['action_items'].append(sentence)
        
        return insights
    
    def _generate_results(self) -> Dict[str, Any]:
        """Generate complete observation results."""
        duration = (
            (datetime.now() - self._start_time).total_seconds()
            if self._start_time else 0
        )
        
        # Generate session summary
        summary = self._generate_summary()
        
        return {
            'observation_id': self._observation_id,
            'timestamp': self._start_time.isoformat() if self._start_time else None,
            'data_source': 'voice_observation',
            'session_reference': self.session_reference,
            'recording_duration_seconds': duration,
            'audio_file_path': str(
                self.data_dir / "recordings" / f"{self._observation_id}_complete.wav"
            ),
            'transcription_model': self.transcriber.model_name,
            'observations': self._observations,
            'session_summary': summary
        }
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary statistics for the session."""
        if not self._observations:
            return {}
        
        # Category breakdown
        category_counts = defaultdict(int)
        for obs in self._observations:
            for cat in obs.get('categories', []):
                category_counts[cat] += 1
        
        # Sentiment breakdown
        sentiment_counts = {'positive': 0, 'neutral': 0, 'negative': 0}
        for obs in self._observations:
            sentiment = obs.get('sentiment', 'neutral')
            sentiment_counts[sentiment] += 1
        
        # Extract key themes
        all_keywords = []
        for obs in self._observations:
            all_keywords.extend(obs.get('detected_keywords', []))
        
        keyword_counts = defaultdict(int)
        for kw in all_keywords:
            keyword_counts[kw] += 1
        
        key_themes = [
            kw for kw, count in sorted(
                keyword_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        ]
        
        # Identify recurring issues (negative observations with similar keywords)
        negative_obs = [
            obs for obs in self._observations
            if obs.get('sentiment') == 'negative'
        ]
        
        issue_counts = defaultdict(int)
        for obs in negative_obs:
            for kw in obs.get('detected_keywords', []):
                issue_counts[kw] += 1
        
        recurring_issues = [
            {'issue': issue, 'frequency': count}
            for issue, count in sorted(
                issue_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            if count >= 2
        ]
        
        # Collect positive observations
        positive_obs = [
            obs['transcription'] for obs in self._observations
            if obs.get('sentiment') == 'positive'
        ][:5]
        
        # Identify focus areas from action items
        focus_areas = []
        for obs in self._observations:
            focus_areas.extend(obs.get('parsed_insights', {}).get('action_items', []))
        focus_areas = list(set(focus_areas))[:5]
        
        return {
            'total_observations': len(self._observations),
            'category_breakdown': dict(category_counts),
            'sentiment_breakdown': sentiment_counts,
            'key_themes': key_themes,
            'recurring_issues': recurring_issues,
            'positive_observations': positive_obs,
            'areas_for_focus': focus_areas
        }
    
    def _save_results(self, results: Dict[str, Any]) -> Path:
        """Save results to JSON file."""
        filename = f"{self._observation_id}.json"
        filepath = self.data_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)
        
        self.logger.info(f"Saved observation results: {filepath}")
        return filepath
    
    def process_existing_recording(
        self,
        audio_path: Path,
        session_reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process an existing audio recording.
        
        Args:
            audio_path: Path to audio file
            session_reference: Reference to associated session
            
        Returns:
            Observation data
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        self._observation_id = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._start_time = datetime.now()
        self._observations = []
        self.session_reference = session_reference
        
        # Transcribe
        transcription = self.transcriber.transcribe_file(audio_path)
        self._process_transcriptions([transcription])
        
        # Generate results
        results = self._generate_results()
        results['audio_file_path'] = str(audio_path)
        
        # Save
        self._save_results(results)
        
        return results
    
    def release(self):
        """Release resources."""
        self.transcriber.release()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
