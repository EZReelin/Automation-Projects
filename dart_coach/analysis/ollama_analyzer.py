"""
Ollama Analyzer Module
=====================
Integrates with Ollama for AI-powered performance analysis.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import requests

from .prompts import AnalysisPrompts


class OllamaAnalyzer:
    """
    Analyzes dart performance data using Ollama LLM.
    
    Generates comprehensive coaching insights and recommendations.
    """
    
    def __init__(
        self,
        base_url: str = None,
        model: str = "llama3.1:8b",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        log_level: str = "INFO"
    ):
        """
        Initialize Ollama analyzer.
        
        Args:
            base_url: Ollama API base URL
            model: Model to use for analysis
            temperature: Generation temperature
            max_tokens: Maximum tokens in response
            log_level: Logging level
        """
        self.base_url = base_url or os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
    
    def _call_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Make a request to Ollama API.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            
        Returns:
            Model response text
        """
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            self.logger.debug(f"Calling Ollama at {url}")
            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()
            
            result = response.json()
            return result.get('response', '')
            
        except requests.exceptions.ConnectionError:
            self.logger.error(
                f"Could not connect to Ollama at {self.base_url}. "
                "Make sure Ollama is running."
            )
            return ""
        except requests.exceptions.Timeout:
            self.logger.error("Ollama request timed out")
            return ""
        except Exception as e:
            self.logger.error(f"Ollama request failed: {e}")
            return ""
    
    def check_connection(self) -> bool:
        """Check if Ollama is available."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def list_models(self) -> List[str]:
        """List available Ollama models."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            response.raise_for_status()
            data = response.json()
            return [m['name'] for m in data.get('models', [])]
        except Exception as e:
            self.logger.error(f"Failed to list models: {e}")
            return []
    
    def analyze_weekly_performance(
        self,
        aggregated_data: Dict[str, Any]
    ) -> str:
        """
        Generate comprehensive weekly performance analysis.
        
        Args:
            aggregated_data: Aggregated data from DataAggregator
            
        Returns:
            Analysis text
        """
        # Format data summaries
        practice_summary = self._format_practice_summary(
            aggregated_data.get('practice_data', {})
        )
        competition_summary = self._format_competition_summary(
            aggregated_data.get('competition_data', {})
        )
        biomechanics_summary = self._format_biomechanics_summary(
            aggregated_data.get('biomechanics_data', {})
        )
        observations_summary = self._format_observations_summary(
            aggregated_data.get('observations_data', {})
        )
        
        # Build prompt
        prompt = AnalysisPrompts.WEEKLY_SUMMARY_PROMPT.format(
            practice_summary=practice_summary,
            competition_summary=competition_summary,
            biomechanics_summary=biomechanics_summary,
            observations_summary=observations_summary
        )
        
        self.logger.info("Generating weekly performance analysis...")
        return self._call_ollama(prompt, AnalysisPrompts.SYSTEM_PROMPT)
    
    def analyze_trends(
        self,
        current_week: Dict[str, Any],
        previous_week: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Analyze performance trends.
        
        Args:
            current_week: Current week's aggregated data
            previous_week: Previous week's aggregated data (optional)
            
        Returns:
            Trend analysis text
        """
        weekly_metrics = self._format_weekly_metrics(current_week)
        previous = self._format_previous_week(previous_week) if previous_week else "No previous week data available."
        daily = self._format_daily_breakdown(current_week)
        
        prompt = AnalysisPrompts.TREND_ANALYSIS_PROMPT.format(
            weekly_metrics=weekly_metrics,
            previous_week=previous,
            daily_breakdown=daily
        )
        
        self.logger.info("Generating trend analysis...")
        return self._call_ollama(prompt, AnalysisPrompts.SYSTEM_PROMPT)
    
    def analyze_biomechanics(
        self,
        biomechanics_data: Dict[str, Any]
    ) -> str:
        """
        Analyze biomechanical throw data.
        
        Args:
            biomechanics_data: Biomechanics aggregated data
            
        Returns:
            Biomechanics analysis text
        """
        bio_summary = self._format_biomechanics_detail(biomechanics_data)
        deviations = self._format_deviations(biomechanics_data)
        consistency = self._format_consistency(biomechanics_data)
        
        prompt = AnalysisPrompts.BIOMECHANICS_ANALYSIS_PROMPT.format(
            biomechanics_data=bio_summary,
            deviations=deviations,
            consistency=consistency
        )
        
        self.logger.info("Generating biomechanics analysis...")
        return self._call_ollama(prompt, AnalysisPrompts.SYSTEM_PROMPT)
    
    def analyze_mental_game(
        self,
        aggregated_data: Dict[str, Any]
    ) -> str:
        """
        Analyze mental game and performance under pressure.
        
        Args:
            aggregated_data: Full aggregated data
            
        Returns:
            Mental game analysis text
        """
        competition_data = aggregated_data.get('competition_data', {})
        observations_data = aggregated_data.get('observations_data', {})
        practice_data = aggregated_data.get('practice_data', {})
        
        pressure_stats = self._format_pressure_stats(competition_data)
        themes = self._format_observation_themes(observations_data)
        sentiment = self._format_sentiment(observations_data)
        
        practice_avg = practice_data.get('metrics', {}).get('average_three_dart', 0)
        competition_avg = competition_data.get('metrics', {}).get('average_three_dart', 0)
        
        prompt = AnalysisPrompts.MENTAL_GAME_PROMPT.format(
            pressure_stats=pressure_stats,
            observation_themes=themes,
            sentiment=sentiment,
            practice_avg=f"{practice_avg:.1f}",
            competition_avg=f"{competition_avg:.1f}"
        )
        
        self.logger.info("Generating mental game analysis...")
        return self._call_ollama(prompt, AnalysisPrompts.SYSTEM_PROMPT)
    
    def recommend_drills(
        self,
        aggregated_data: Dict[str, Any],
        practice_time_minutes: int = 60
    ) -> str:
        """
        Generate drill recommendations.
        
        Args:
            aggregated_data: Full aggregated data
            practice_time_minutes: Available practice time
            
        Returns:
            Drill recommendations text
        """
        # Identify improvement areas
        improvement_areas = self._identify_improvement_areas(aggregated_data)
        
        practice_data = aggregated_data.get('practice_data', {})
        metrics = practice_data.get('metrics', {})
        
        prompt = AnalysisPrompts.DRILL_RECOMMENDATION_PROMPT.format(
            improvement_areas=improvement_areas,
            average=f"{metrics.get('average_three_dart', 0):.1f}",
            checkout_pct=f"{metrics.get('average_checkout_pct', 0):.1f}%",
            first_nine=f"{metrics.get('average_first_nine', 0):.1f}",
            practice_time=practice_time_minutes
        )
        
        self.logger.info("Generating drill recommendations...")
        return self._call_ollama(prompt, AnalysisPrompts.SYSTEM_PROMPT)
    
    def set_goals(
        self,
        aggregated_data: Dict[str, Any],
        previous_week: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate goal recommendations.
        
        Args:
            aggregated_data: Current week's data
            previous_week: Previous week's data (optional)
            
        Returns:
            Goal recommendations text
        """
        current_performance = self._format_current_performance(aggregated_data)
        trends = self._format_trends(aggregated_data, previous_week)
        strengths = self._identify_strengths(aggregated_data)
        improvements = self._identify_improvement_areas(aggregated_data)
        
        prompt = AnalysisPrompts.GOAL_SETTING_PROMPT.format(
            current_performance=current_performance,
            trends=trends,
            strengths=strengths,
            improvements=improvements
        )
        
        self.logger.info("Generating goal recommendations...")
        return self._call_ollama(prompt, AnalysisPrompts.SYSTEM_PROMPT)
    
    # Formatting helper methods
    def _format_practice_summary(self, data: Dict[str, Any]) -> str:
        """Format practice data for prompt."""
        if not data or data.get('sessions', 0) == 0:
            return "No practice data available for this week."
        
        metrics = data.get('metrics', {})
        match_results = data.get('match_results', {})
        
        return f"""
Sessions: {data.get('sessions', 0)}
Total Practice Time: {data.get('total_duration_minutes', 0):.0f} minutes
Total Darts Thrown: {data.get('total_darts', 0)}

Performance Metrics:
- Three Dart Average: {metrics.get('average_three_dart', 0):.1f}
- Best Average: {metrics.get('best_three_dart', 0):.1f}
- First 9 Average: {metrics.get('average_first_nine', 0):.1f}
- Points Per Dart: {metrics.get('average_ppd', 0):.2f}
- Checkout Percentage: {metrics.get('average_checkout_pct', 0):.1f}%
- Highest Checkout: {metrics.get('highest_checkout', 0)}

Scoring:
- 180s: {metrics.get('total_180s', 0)}
- 140+: {metrics.get('total_140_plus', 0)}
- 100+: {metrics.get('total_100_plus', 0)}

CPU Matches: {match_results.get('cpu_matches', {}).get('played', 0)} played, {match_results.get('cpu_matches', {}).get('won', 0)} won
Online Matches: {match_results.get('online_matches', {}).get('played', 0)} played, {match_results.get('online_matches', {}).get('won', 0)} won
"""
    
    def _format_competition_summary(self, data: Dict[str, Any]) -> str:
        """Format competition data for prompt."""
        if not data or data.get('matches', 0) == 0:
            return "No competition data available for this week."
        
        metrics = data.get('metrics', {})
        record = data.get('overall_record', {})
        pressure = data.get('pressure_performance', {})
        
        return f"""
Total Matches: {data.get('matches', 0)}
- League Matches: {data.get('league_matches', 0)}
- Bar Matches: {data.get('bar_matches', 0)}

Overall Record: {record.get('won', 0)}-{record.get('lost', 0)}
Legs Won/Lost: {record.get('legs_won', 0)}-{record.get('legs_lost', 0)}

Performance Metrics:
- Three Dart Average: {metrics.get('average_three_dart', 0):.1f}
- Best Match Average: {metrics.get('best_match_average', 0):.1f}
- First 9 Average: {metrics.get('average_first_nine', 0):.1f}
- Checkout Percentage: {metrics.get('average_checkout_pct', 0):.1f}%
- Highest Checkout: {metrics.get('highest_checkout', 0)}
- 180s: {metrics.get('total_180s', 0)}

Pressure Performance:
- Match Dart Conversion: {pressure.get('match_darts_conversion', 0):.1f}%
- Deciding Legs Won: {pressure.get('deciding_legs_won', 0)}
"""
    
    def _format_biomechanics_summary(self, data: Dict[str, Any]) -> str:
        """Format biomechanics data for prompt."""
        if not data or data.get('sessions', 0) == 0:
            return "No biomechanics analysis data available for this week."
        
        deviations = data.get('deviation_summary', [])[:5]
        deviation_text = "\n".join([
            f"  - {d['type'].replace('_', ' ').title()}: {d['count']} occurrences ({d['percentage']:.1f}%)"
            for d in deviations
        ])
        
        return f"""
Analysis Sessions: {data.get('sessions', 0)}
Throws Analyzed: {data.get('total_throws_analyzed', 0)}
Average Quality Score: {data.get('average_quality_score', 0):.1f}/100
Average Consistency Score: {data.get('average_consistency_score', 0):.1f}/100

Top Form Deviations:
{deviation_text}

Trend: {data.get('improvement_trends', {}).get('overall', 'Unknown')}
"""
    
    def _format_observations_summary(self, data: Dict[str, Any]) -> str:
        """Format voice observations for prompt."""
        if not data or data.get('sessions', 0) == 0:
            return "No voice observation data available for this week."
        
        sentiment = data.get('sentiment_breakdown', {})
        categories = data.get('category_breakdown', {})
        keywords = data.get('top_keywords', [])[:10]
        
        keyword_text = ", ".join([kw['keyword'] for kw in keywords])
        action_items = "\n".join([f"  - {item}" for item in data.get('action_items', [])[:5]])
        
        return f"""
Recording Sessions: {data.get('sessions', 0)}
Total Observations: {data.get('total_observations', 0)}
Recording Time: {data.get('total_recording_time', 0) / 60:.1f} minutes

Sentiment:
- Positive: {sentiment.get('positive', 0)}
- Neutral: {sentiment.get('neutral', 0)}
- Negative: {sentiment.get('negative', 0)}

Top Discussion Topics: {keyword_text}

Action Items Mentioned:
{action_items if action_items else "  No specific action items recorded"}

Key Themes: {', '.join(data.get('key_themes', [])[:5])}
"""
    
    def _format_weekly_metrics(self, data: Dict[str, Any]) -> str:
        """Format weekly metrics for trend analysis."""
        practice = data.get('practice_data', {}).get('metrics', {})
        competition = data.get('competition_data', {}).get('metrics', {})
        
        return f"""
Practice Metrics:
- Average: {practice.get('average_three_dart', 0):.1f}
- Checkout %: {practice.get('average_checkout_pct', 0):.1f}%
- 180s: {practice.get('total_180s', 0)}

Competition Metrics:
- Average: {competition.get('average_three_dart', 0):.1f}
- Checkout %: {competition.get('average_checkout_pct', 0):.1f}%
- 180s: {competition.get('total_180s', 0)}
"""
    
    def _format_previous_week(self, data: Dict[str, Any]) -> str:
        """Format previous week data for comparison."""
        if not data:
            return "No previous week data available."
        
        practice = data.get('practice_data', {}).get('metrics', {})
        competition = data.get('competition_data', {}).get('metrics', {})
        
        return f"""
Previous Week Practice:
- Average: {practice.get('average_three_dart', 0):.1f}
- Checkout %: {practice.get('average_checkout_pct', 0):.1f}%

Previous Week Competition:
- Average: {competition.get('average_three_dart', 0):.1f}
- Checkout %: {competition.get('average_checkout_pct', 0):.1f}%
"""
    
    def _format_daily_breakdown(self, data: Dict[str, Any]) -> str:
        """Format daily breakdown."""
        practice_daily = data.get('practice_data', {}).get('daily_breakdown', {})
        
        if not practice_daily:
            return "No daily breakdown available."
        
        lines = []
        for date, info in sorted(practice_daily.items()):
            lines.append(f"- {date}: {info['count']} sessions")
        
        return "\n".join(lines)
    
    def _format_biomechanics_detail(self, data: Dict[str, Any]) -> str:
        """Format detailed biomechanics data."""
        return f"""
Sessions: {data.get('sessions', 0)}
Throws Analyzed: {data.get('total_throws_analyzed', 0)}
Quality Score: {data.get('average_quality_score', 0):.1f}/100
Consistency: {data.get('average_consistency_score', 0):.1f}/100
"""
    
    def _format_deviations(self, data: Dict[str, Any]) -> str:
        """Format deviation summary."""
        deviations = data.get('deviation_summary', [])
        if not deviations:
            return "No significant form deviations detected."
        
        lines = []
        for d in deviations[:5]:
            lines.append(f"- {d['type'].replace('_', ' ').title()}: {d['count']} times ({d['percentage']:.1f}%)")
        
        return "\n".join(lines)
    
    def _format_consistency(self, data: Dict[str, Any]) -> str:
        """Format consistency metrics."""
        return f"""
Consistency Score: {data.get('average_consistency_score', 0):.1f}/100
Improvement Trend: {data.get('improvement_trends', {}).get('overall', 'Unknown')}
"""
    
    def _format_pressure_stats(self, data: Dict[str, Any]) -> str:
        """Format pressure situation statistics."""
        pressure = data.get('pressure_performance', {})
        record = data.get('overall_record', {})
        
        return f"""
Match Results: {record.get('won', 0)}-{record.get('lost', 0)}
Match Dart Conversion: {pressure.get('match_darts_conversion', 0):.1f}%
Deciding Legs Won: {pressure.get('deciding_legs_won', 0)}
"""
    
    def _format_observation_themes(self, data: Dict[str, Any]) -> str:
        """Format observation themes."""
        themes = data.get('key_themes', [])
        if not themes:
            return "No key themes identified."
        
        return ", ".join(themes[:10])
    
    def _format_sentiment(self, data: Dict[str, Any]) -> str:
        """Format sentiment breakdown."""
        sentiment = data.get('sentiment_breakdown', {})
        total = sum(sentiment.values())
        
        if total == 0:
            return "No sentiment data available."
        
        return f"""
Positive: {sentiment.get('positive', 0)} ({sentiment.get('positive', 0)/total*100:.1f}%)
Neutral: {sentiment.get('neutral', 0)} ({sentiment.get('neutral', 0)/total*100:.1f}%)
Negative: {sentiment.get('negative', 0)} ({sentiment.get('negative', 0)/total*100:.1f}%)
"""
    
    def _identify_improvement_areas(self, data: Dict[str, Any]) -> str:
        """Identify areas needing improvement."""
        areas = []
        
        practice = data.get('practice_data', {}).get('metrics', {})
        competition = data.get('competition_data', {}).get('metrics', {})
        bio = data.get('biomechanics_data', {})
        
        # Check averages
        if practice.get('average_three_dart', 0) < 50:
            areas.append("Scoring average needs improvement (below 50)")
        
        # Check checkout
        if practice.get('average_checkout_pct', 0) < 30:
            areas.append("Checkout percentage needs work (below 30%)")
        
        # Check practice vs competition gap
        practice_avg = practice.get('average_three_dart', 0)
        comp_avg = competition.get('average_three_dart', 0)
        
        if practice_avg > 0 and comp_avg > 0 and practice_avg - comp_avg > 10:
            areas.append(f"Large practice-to-competition gap ({practice_avg - comp_avg:.1f} point drop)")
        
        # Check biomechanics
        deviations = bio.get('deviation_summary', [])
        for dev in deviations[:2]:
            if dev.get('percentage', 0) > 20:
                areas.append(f"Frequent {dev['type'].replace('_', ' ')} ({dev['percentage']:.0f}% of throws)")
        
        return "\n".join([f"- {area}" for area in areas]) if areas else "No major improvement areas identified."
    
    def _identify_strengths(self, data: Dict[str, Any]) -> str:
        """Identify player strengths."""
        strengths = []
        
        practice = data.get('practice_data', {}).get('metrics', {})
        bio = data.get('biomechanics_data', {})
        
        if practice.get('average_three_dart', 0) > 70:
            strengths.append("Strong scoring ability (70+ average)")
        
        if practice.get('average_checkout_pct', 0) > 40:
            strengths.append("Good checkout percentage (40%+)")
        
        if bio.get('average_consistency_score', 0) > 80:
            strengths.append("Consistent throwing form")
        
        if practice.get('total_180s', 0) > 3:
            strengths.append("Ability to hit maximum scores")
        
        return "\n".join([f"- {s}" for s in strengths]) if strengths else "Strengths to be identified with more data."
    
    def _format_current_performance(self, data: Dict[str, Any]) -> str:
        """Format current performance summary."""
        practice = data.get('practice_data', {})
        competition = data.get('competition_data', {})
        
        return f"""
Practice: {practice.get('sessions', 0)} sessions, {practice.get('metrics', {}).get('average_three_dart', 0):.1f} avg
Competition: {competition.get('matches', 0)} matches, {competition.get('overall_record', {}).get('won', 0)}-{competition.get('overall_record', {}).get('lost', 0)} record
"""
    
    def _format_trends(
        self,
        current: Dict[str, Any],
        previous: Optional[Dict[str, Any]]
    ) -> str:
        """Format trend information."""
        if not previous:
            return "First week of tracking - no trend data available."
        
        curr_avg = current.get('practice_data', {}).get('metrics', {}).get('average_three_dart', 0)
        prev_avg = previous.get('practice_data', {}).get('metrics', {}).get('average_three_dart', 0)
        
        diff = curr_avg - prev_avg
        trend = "improving" if diff > 0 else "declining" if diff < 0 else "stable"
        
        return f"Average trending {trend} ({diff:+.1f} from last week)"
