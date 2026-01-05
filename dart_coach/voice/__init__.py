"""
Voice Observation Module
=======================
Voice recording and transcription for practice observations.
"""

from .voice_recorder import VoiceRecorder
from .transcriber import Transcriber
from .observation_processor import ObservationProcessor

__all__ = ['VoiceRecorder', 'Transcriber', 'ObservationProcessor']
