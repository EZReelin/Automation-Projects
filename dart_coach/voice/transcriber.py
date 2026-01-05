"""
Transcriber Module
=================
Audio transcription using Whisper for voice observations.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


class Transcriber:
    """
    Transcribes audio recordings using OpenAI Whisper model.
    
    Provides timestamped transcriptions for synchronization
    with throw data.
    """
    
    def __init__(
        self,
        model_name: str = "base",
        language: str = "en",
        log_level: str = "INFO"
    ):
        """
        Initialize transcriber.
        
        Args:
            model_name: Whisper model size (tiny, base, small, medium, large)
            language: Language code for transcription
            log_level: Logging level
        """
        self.model_name = model_name
        self.language = language
        self.model = None
        
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
        """Initialize the Whisper model."""
        try:
            import whisper
            
            self.logger.info(f"Loading Whisper model: {self.model_name}")
            self.model = whisper.load_model(self.model_name)
            self.logger.info("Whisper model loaded successfully")
            
        except ImportError:
            self.logger.error(
                "Whisper not installed. Install with: pip install openai-whisper"
            )
            raise
        except Exception as e:
            self.logger.error(f"Failed to load Whisper model: {e}")
            raise
    
    def transcribe_file(
        self,
        audio_path: Path,
        start_offset: float = 0
    ) -> Dict[str, Any]:
        """
        Transcribe an audio file.
        
        Args:
            audio_path: Path to audio file
            start_offset: Time offset for timestamps (seconds)
            
        Returns:
            Transcription result with timestamps
        """
        if self.model is None:
            self.initialize()
        
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        self.logger.info(f"Transcribing: {audio_path}")
        
        try:
            # Transcribe with word-level timestamps
            result = self.model.transcribe(
                str(audio_path),
                language=self.language,
                word_timestamps=True,
                verbose=False
            )
            
            # Process segments
            segments = []
            for segment in result.get('segments', []):
                processed_segment = {
                    'start': segment['start'] + start_offset,
                    'end': segment['end'] + start_offset,
                    'text': segment['text'].strip(),
                    'confidence': segment.get('avg_logprob', 0),
                    'words': []
                }
                
                # Add word-level timestamps if available
                for word in segment.get('words', []):
                    processed_segment['words'].append({
                        'word': word['word'],
                        'start': word['start'] + start_offset,
                        'end': word['end'] + start_offset,
                        'probability': word.get('probability', 0)
                    })
                
                segments.append(processed_segment)
            
            return {
                'text': result['text'].strip(),
                'language': result.get('language', self.language),
                'segments': segments,
                'duration': result.get('duration', 0)
            }
            
        except Exception as e:
            self.logger.error(f"Transcription failed: {e}")
            return {
                'text': '',
                'language': self.language,
                'segments': [],
                'duration': 0,
                'error': str(e)
            }
    
    def transcribe_chunks(
        self,
        chunk_files: List[Path],
        chunk_duration: float = 30
    ) -> List[Dict[str, Any]]:
        """
        Transcribe multiple audio chunks.
        
        Args:
            chunk_files: List of chunk file paths
            chunk_duration: Duration of each chunk in seconds
            
        Returns:
            List of transcription results
        """
        results = []
        
        for i, chunk_file in enumerate(sorted(chunk_files)):
            # Calculate time offset based on chunk number
            # Extract chunk number from filename if possible
            try:
                chunk_num = int(chunk_file.stem.split('_')[-1])
                offset = chunk_num
            except (ValueError, IndexError):
                offset = i * chunk_duration
            
            result = self.transcribe_file(chunk_file, start_offset=offset)
            result['chunk_file'] = str(chunk_file)
            result['chunk_number'] = i
            results.append(result)
        
        self.logger.info(f"Transcribed {len(results)} chunks")
        return results
    
    def transcribe_array(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        start_offset: float = 0
    ) -> Dict[str, Any]:
        """
        Transcribe audio from numpy array.
        
        Args:
            audio_data: Audio data as numpy array
            sample_rate: Sample rate of audio
            start_offset: Time offset for timestamps
            
        Returns:
            Transcription result
        """
        if self.model is None:
            self.initialize()
        
        try:
            import whisper
            
            # Ensure correct format
            if audio_data.ndim > 1:
                audio_data = audio_data.flatten()
            
            # Convert to float32 if needed
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # Pad or trim to expected length
            audio_data = whisper.pad_or_trim(audio_data)
            
            # Make log-Mel spectrogram
            mel = whisper.log_mel_spectrogram(audio_data).to(self.model.device)
            
            # Decode
            options = whisper.DecodingOptions(language=self.language)
            result = whisper.decode(self.model, mel, options)
            
            return {
                'text': result.text.strip(),
                'language': result.language,
                'segments': [{
                    'start': start_offset,
                    'end': start_offset + len(audio_data) / sample_rate,
                    'text': result.text.strip(),
                    'confidence': 0
                }],
                'duration': len(audio_data) / sample_rate
            }
            
        except Exception as e:
            self.logger.error(f"Array transcription failed: {e}")
            return {
                'text': '',
                'language': self.language,
                'segments': [],
                'duration': 0,
                'error': str(e)
            }
    
    def release(self):
        """Release model resources."""
        if self.model is not None:
            del self.model
            self.model = None
            self.logger.info("Whisper model released")
    
    def __enter__(self):
        """Context manager entry."""
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
