"""
Voice Recorder Module
====================
Audio recording for voice observations during practice.
"""

import logging
import os
import queue
import threading
import wave
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import sounddevice as sd


class VoiceRecorder:
    """
    Records audio for voice observations during practice sessions.
    
    Supports continuous recording with automatic chunking for
    real-time transcription.
    """
    
    def __init__(
        self,
        output_dir: Path,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_duration: int = 30,
        device_id: Optional[int] = None,
        log_level: str = "INFO"
    ):
        """
        Initialize voice recorder.
        
        Args:
            output_dir: Directory for saving recordings
            sample_rate: Audio sample rate in Hz
            channels: Number of audio channels
            chunk_duration: Duration of each audio chunk in seconds
            device_id: Audio device ID (None for default)
            log_level: Logging level
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_duration = chunk_duration
        
        # Get device from environment or parameter
        device_env = os.getenv('AUDIO_DEVICE_ID')
        if device_env and device_env != 'default':
            self.device_id = int(device_env)
        else:
            self.device_id = device_id
        
        # Recording state
        self._recording = False
        self._audio_queue: queue.Queue = queue.Queue()
        self._recording_thread: Optional[threading.Thread] = None
        self._chunks: List[Tuple[float, np.ndarray]] = []
        self._start_time: Optional[datetime] = None
        self._session_id: Optional[str] = None
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for audio stream."""
        if status:
            self.logger.warning(f"Audio callback status: {status}")
        
        if self._recording:
            elapsed = (datetime.now() - self._start_time).total_seconds()
            self._audio_queue.put((elapsed, indata.copy()))
    
    def _recording_worker(self):
        """Worker thread for processing audio chunks."""
        current_chunk = []
        chunk_start_time = 0
        
        while self._recording or not self._audio_queue.empty():
            try:
                elapsed, data = self._audio_queue.get(timeout=1.0)
                
                if not current_chunk:
                    chunk_start_time = elapsed
                
                current_chunk.append(data)
                
                # Calculate current chunk duration
                chunk_samples = sum(len(d) for d in current_chunk)
                chunk_duration = chunk_samples / self.sample_rate
                
                # Save chunk if duration exceeded
                if chunk_duration >= self.chunk_duration:
                    audio_data = np.concatenate(current_chunk, axis=0)
                    self._chunks.append((chunk_start_time, audio_data))
                    
                    # Save chunk to file
                    self._save_chunk(chunk_start_time, audio_data)
                    
                    current_chunk = []
                    
            except queue.Empty:
                continue
        
        # Save remaining audio
        if current_chunk:
            audio_data = np.concatenate(current_chunk, axis=0)
            self._chunks.append((chunk_start_time, audio_data))
            self._save_chunk(chunk_start_time, audio_data)
    
    def _save_chunk(self, start_time: float, audio_data: np.ndarray) -> Path:
        """Save audio chunk to WAV file."""
        filename = f"{self._session_id}_chunk_{int(start_time):04d}.wav"
        filepath = self.output_dir / filename
        
        # Convert to 16-bit PCM
        audio_int16 = (audio_data * 32767).astype(np.int16)
        
        with wave.open(str(filepath), 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_int16.tobytes())
        
        self.logger.debug(f"Saved audio chunk: {filepath}")
        return filepath
    
    def start_recording(self, session_id: Optional[str] = None) -> str:
        """
        Start recording audio.
        
        Args:
            session_id: Optional session identifier
            
        Returns:
            Session ID for this recording
        """
        if self._recording:
            self.logger.warning("Already recording")
            return self._session_id
        
        self._session_id = session_id or f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._start_time = datetime.now()
        self._chunks = []
        self._audio_queue = queue.Queue()
        
        # Start audio stream
        self._recording = True
        
        self._stream = sd.InputStream(
            device=self.device_id,
            channels=self.channels,
            samplerate=self.sample_rate,
            callback=self._audio_callback
        )
        self._stream.start()
        
        # Start worker thread
        self._recording_thread = threading.Thread(target=self._recording_worker)
        self._recording_thread.start()
        
        self.logger.info(f"Started recording: {self._session_id}")
        return self._session_id
    
    def stop_recording(self) -> Tuple[str, List[Path]]:
        """
        Stop recording and save all audio.
        
        Returns:
            Tuple of (session_id, list of chunk file paths)
        """
        if not self._recording:
            return self._session_id, []
        
        self._recording = False
        
        # Stop stream
        if hasattr(self, '_stream'):
            self._stream.stop()
            self._stream.close()
        
        # Wait for worker thread
        if self._recording_thread:
            self._recording_thread.join()
        
        # Collect chunk files
        chunk_files = list(self.output_dir.glob(f"{self._session_id}_chunk_*.wav"))
        chunk_files.sort()
        
        # Save complete recording
        if self._chunks:
            self._save_complete_recording()
        
        self.logger.info(
            f"Stopped recording. Saved {len(chunk_files)} chunks."
        )
        
        return self._session_id, chunk_files
    
    def _save_complete_recording(self) -> Path:
        """Save complete recording as single file."""
        if not self._chunks:
            return None
        
        # Concatenate all chunks
        all_audio = np.concatenate([chunk[1] for chunk in self._chunks], axis=0)
        
        filename = f"{self._session_id}_complete.wav"
        filepath = self.output_dir / filename
        
        audio_int16 = (all_audio * 32767).astype(np.int16)
        
        with wave.open(str(filepath), 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_int16.tobytes())
        
        self.logger.info(f"Saved complete recording: {filepath}")
        return filepath
    
    def get_recording_status(self) -> dict:
        """Get current recording status."""
        return {
            'recording': self._recording,
            'session_id': self._session_id,
            'start_time': self._start_time.isoformat() if self._start_time else None,
            'duration': (
                (datetime.now() - self._start_time).total_seconds()
                if self._start_time and self._recording else 0
            ),
            'chunks_saved': len(self._chunks)
        }
    
    @staticmethod
    def list_audio_devices() -> List[dict]:
        """List available audio input devices."""
        devices = sd.query_devices()
        input_devices = []
        
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append({
                    'id': i,
                    'name': device['name'],
                    'channels': device['max_input_channels'],
                    'sample_rate': device['default_samplerate']
                })
        
        return input_devices
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._recording:
            self.stop_recording()
