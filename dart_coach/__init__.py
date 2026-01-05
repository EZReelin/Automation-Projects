"""
Dart Performance Coach
======================

A comprehensive dart performance tracking and coaching system that integrates
multiple data sources to provide weekly analytical insights.

Components:
- scrapers: Web scrapers for Scolia and Dart Connect
- biomechanics: MediaPipe-based throw analysis
- voice: Voice observation recording and transcription
- data_pipeline: Data aggregation and validation
- analysis: Ollama-powered performance analysis
- calendar: Calendar integration for scheduling reports
"""

__version__ = "1.0.0"
__author__ = "Dart Performance Coach"

from pathlib import Path

# Package root directory
PACKAGE_ROOT = Path(__file__).parent

# Default data directory
DEFAULT_DATA_DIR = PACKAGE_ROOT / "data"
DEFAULT_CONFIG_DIR = PACKAGE_ROOT / "config"
DEFAULT_SCHEMA_DIR = PACKAGE_ROOT / "schemas"
