"""
Analysis Module
==============
Ollama-powered performance analysis and coaching insights.
"""

from .ollama_analyzer import OllamaAnalyzer
from .report_generator import ReportGenerator
from .prompts import AnalysisPrompts

__all__ = ['OllamaAnalyzer', 'ReportGenerator', 'AnalysisPrompts']
