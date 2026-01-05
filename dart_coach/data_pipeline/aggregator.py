"""
Data Aggregator Module
=====================
Aggregates data from all sources for weekly analysis.
"""

import json
import logging
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .loader import DataLoader
from .validator import DataValidator


class DataAggregator:
    """
    Aggregates dart performance data from all sources.
    
    Combines scraped statistics, biomechanical analysis, and
    voice observations into a unified dataset for analysis.
    """
    
    def __init__(
        self,
        data_dir: Path,
        schema_dir: Path,
        output_dir: Optional[Path] = None,
        log_level: str = "INFO"
    ):
        """
        Initialize data aggregator.
        
        Args:
            data_dir: Base directory containing source data
            schema_dir: Directory containing JSON schemas
            output_dir: Directory for aggregated output
            log_level: Logging level
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir) if output_dir else self.data_dir / 'aggregated'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.loader = DataLoader(self.data_dir)
        self.validator = DataValidator(schema_dir)
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
    
    def aggregate_week(
        self,
        week_end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Aggregate all data for a week.
        
        Args:
            week_end_date: End date of the week (defaults to today)
            
        Returns:
            Aggregated data dictionary
        """
        if week_end_date is None:
            week_end_date = datetime.now()
        
        start_date = week_end_date - timedelta(days=7)
        
        self.logger.info(
            f"Aggregating data from {start_date.date()} to {week_end_date.date()}"
        )
        
        # Load all data for the week
        raw_data = self.loader.load_all(start_date, week_end_date)
        
        # Aggregate each source
        aggregated = {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': week_end_date.isoformat(),
                'week_number': week_end_date.isocalendar()[1]
            },
            'data_sources_included': {
                source: len(records) for source, records in raw_data.items()
            },
            'practice_data': self._aggregate_scolia(raw_data.get('scolia', [])),
            'competition_data': self._aggregate_dart_connect(raw_data.get('dart_connect', [])),
            'biomechanics_data': self._aggregate_biomechanics(raw_data.get('biomechanics', [])),
            'observations_data': self._aggregate_voice(raw_data.get('voice_observation', [])),
            'cross_references': self._create_cross_references(raw_data),
            'raw_file_references': self._collect_file_references(raw_data)
        }
        
        return aggregated
    
    def _aggregate_scolia(
        self,
        sessions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Aggregate Scolia practice data."""
        if not sessions:
            return {'sessions': 0}
        
        # Separate by session type
        practice_sessions = [
            s for s in sessions
            if s.get('session_type', '').endswith('practice')
        ]
        cpu_matches = [
            s for s in sessions
            if s.get('session_type') == 'cpu_match'
        ]
        online_matches = [
            s for s in sessions
            if s.get('session_type') == 'online_match'
        ]
        
        # Calculate aggregate metrics
        all_metrics = [s.get('metrics', {}) for s in sessions]
        
        def safe_avg(values):
            filtered = [v for v in values if v is not None and v > 0]
            return statistics.mean(filtered) if filtered else 0
        
        def safe_sum(values):
            return sum(v for v in values if v is not None)
        
        return {
            'sessions': len(sessions),
            'practice_sessions': len(practice_sessions),
            'cpu_matches': len(cpu_matches),
            'online_matches': len(online_matches),
            'total_darts': safe_sum(m.get('total_darts', 0) for m in all_metrics),
            'total_duration_minutes': safe_sum(
                s.get('duration_minutes', 0) for s in sessions
            ),
            'metrics': {
                'average_ppd': safe_avg(
                    m.get('points_per_dart', 0) for m in all_metrics
                ),
                'average_three_dart': safe_avg(
                    m.get('three_dart_average', 0) for m in all_metrics
                ),
                'best_three_dart': max(
                    (m.get('three_dart_average', 0) for m in all_metrics),
                    default=0
                ),
                'average_first_nine': safe_avg(
                    m.get('first_nine_average', 0) for m in all_metrics
                ),
                'average_checkout_pct': safe_avg(
                    m.get('checkout_percentage', 0) for m in all_metrics
                ),
                'highest_checkout': max(
                    (m.get('highest_checkout', 0) for m in all_metrics),
                    default=0
                ),
                'total_180s': safe_sum(
                    m.get('scoring', {}).get('180s', 0) for m in all_metrics
                ),
                'total_140_plus': safe_sum(
                    m.get('scoring', {}).get('140_plus', 0) for m in all_metrics
                ),
                'total_100_plus': safe_sum(
                    m.get('scoring', {}).get('100_plus', 0) for m in all_metrics
                )
            },
            'match_results': {
                'cpu_matches': {
                    'played': len(cpu_matches),
                    'won': sum(
                        1 for m in cpu_matches
                        if m.get('match_result', {}).get('won', False)
                    ),
                    'lost': sum(
                        1 for m in cpu_matches
                        if not m.get('match_result', {}).get('won', True)
                    )
                },
                'online_matches': {
                    'played': len(online_matches),
                    'won': sum(
                        1 for m in online_matches
                        if m.get('match_result', {}).get('won', False)
                    ),
                    'lost': sum(
                        1 for m in online_matches
                        if not m.get('match_result', {}).get('won', True)
                    )
                }
            },
            'daily_breakdown': self._daily_breakdown(sessions, 'timestamp')
        }
    
    def _aggregate_dart_connect(
        self,
        matches: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Aggregate Dart Connect competition data."""
        if not matches:
            return {'matches': 0}
        
        # Separate by match type
        league_matches = [
            m for m in matches
            if m.get('match_type') == 'league_match'
        ]
        bar_matches = [
            m for m in matches
            if m.get('match_type') == 'bar_match'
        ]
        tournament_matches = [
            m for m in matches
            if 'tournament' in m.get('match_type', '')
        ]
        
        all_metrics = [m.get('metrics', {}) for m in matches]
        all_results = [m.get('result', {}) for m in matches]
        
        def safe_avg(values):
            filtered = [v for v in values if v is not None and v > 0]
            return statistics.mean(filtered) if filtered else 0
        
        def safe_sum(values):
            return sum(v for v in values if v is not None)
        
        # Calculate pressure stats
        pressure_stats = [m.get('pressure_situations', {}) for m in matches]
        
        total_match_darts_thrown = safe_sum(
            p.get('match_darts_thrown', 0) for p in pressure_stats
        )
        total_match_darts_converted = safe_sum(
            p.get('match_darts_converted', 0) for p in pressure_stats
        )
        
        return {
            'matches': len(matches),
            'league_matches': len(league_matches),
            'bar_matches': len(bar_matches),
            'tournament_matches': len(tournament_matches),
            'overall_record': {
                'won': sum(1 for r in all_results if r.get('won', False)),
                'lost': sum(1 for r in all_results if not r.get('won', True)),
                'legs_won': safe_sum(r.get('legs_won', 0) for r in all_results),
                'legs_lost': safe_sum(r.get('legs_lost', 0) for r in all_results)
            },
            'metrics': {
                'average_ppd': safe_avg(
                    m.get('points_per_dart', 0) for m in all_metrics
                ),
                'average_three_dart': safe_avg(
                    m.get('three_dart_average', 0) for m in all_metrics
                ),
                'best_match_average': max(
                    (m.get('three_dart_average', 0) for m in all_metrics),
                    default=0
                ),
                'average_first_nine': safe_avg(
                    m.get('first_nine_average', 0) for m in all_metrics
                ),
                'average_checkout_pct': safe_avg(
                    m.get('checkout_percentage', 0) for m in all_metrics
                ),
                'highest_checkout': max(
                    (m.get('highest_checkout', 0) for m in all_metrics),
                    default=0
                ),
                'total_180s': safe_sum(
                    m.get('scoring', {}).get('180s', 0) for m in all_metrics
                )
            },
            'pressure_performance': {
                'match_darts_conversion': (
                    (total_match_darts_converted / total_match_darts_thrown * 100)
                    if total_match_darts_thrown > 0 else 0
                ),
                'deciding_legs_won': sum(
                    1 for m in matches
                    if m.get('result', {}).get('match_deciding_leg', False)
                    and m.get('result', {}).get('won', False)
                )
            },
            'venue_breakdown': self._venue_breakdown(matches),
            'opponent_analysis': self._opponent_analysis(matches)
        }
    
    def _aggregate_biomechanics(
        self,
        analyses: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Aggregate biomechanics analysis data."""
        if not analyses:
            return {'sessions': 0}
        
        all_throws = []
        for analysis in analyses:
            all_throws.extend(analysis.get('throws', []))
        
        # Collect quality scores
        quality_scores = [
            t.get('throw_quality_score', 0) for t in all_throws
        ]
        
        # Count deviations
        deviation_counts = defaultdict(int)
        for throw in all_throws:
            for dev in throw.get('deviations', []):
                deviation_counts[dev['type']] += 1
        
        # Get aggregate stats from each session
        consistency_scores = [
            a.get('aggregate_analysis', {}).get('consistency_score', 0)
            for a in analyses
        ]
        
        def safe_avg(values):
            filtered = [v for v in values if v is not None and v > 0]
            return statistics.mean(filtered) if filtered else 0
        
        return {
            'sessions': len(analyses),
            'total_throws_analyzed': len(all_throws),
            'average_quality_score': safe_avg(quality_scores),
            'best_quality_score': max(quality_scores, default=0),
            'average_consistency_score': safe_avg(consistency_scores),
            'deviation_summary': [
                {
                    'type': dev_type,
                    'count': count,
                    'percentage': (count / len(all_throws) * 100) if all_throws else 0
                }
                for dev_type, count in sorted(
                    deviation_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            ],
            'improvement_trends': self._calculate_improvement_trend(analyses)
        }
    
    def _aggregate_voice(
        self,
        observations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Aggregate voice observation data."""
        if not observations:
            return {'sessions': 0}
        
        all_obs = []
        for session in observations:
            all_obs.extend(session.get('observations', []))
        
        # Category breakdown
        category_counts = defaultdict(int)
        for obs in all_obs:
            for cat in obs.get('categories', []):
                category_counts[cat] += 1
        
        # Sentiment breakdown
        sentiment_counts = {'positive': 0, 'neutral': 0, 'negative': 0}
        for obs in all_obs:
            sentiment = obs.get('sentiment', 'neutral')
            sentiment_counts[sentiment] += 1
        
        # Collect all keywords
        keyword_counts = defaultdict(int)
        for obs in all_obs:
            for kw in obs.get('detected_keywords', []):
                keyword_counts[kw] += 1
        
        # Collect action items
        all_action_items = []
        for obs in all_obs:
            items = obs.get('parsed_insights', {}).get('action_items', [])
            all_action_items.extend(items)
        
        return {
            'sessions': len(observations),
            'total_observations': len(all_obs),
            'total_recording_time': sum(
                s.get('recording_duration_seconds', 0) for s in observations
            ),
            'category_breakdown': dict(category_counts),
            'sentiment_breakdown': sentiment_counts,
            'top_keywords': [
                {'keyword': kw, 'count': count}
                for kw, count in sorted(
                    keyword_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:20]
            ],
            'action_items': list(set(all_action_items)),
            'key_themes': self._extract_key_themes(all_obs)
        }
    
    def _daily_breakdown(
        self,
        records: List[Dict[str, Any]],
        timestamp_field: str
    ) -> Dict[str, Any]:
        """Create daily breakdown of activity."""
        daily = defaultdict(lambda: {'count': 0, 'records': []})
        
        for record in records:
            ts = record.get(timestamp_field)
            if ts:
                try:
                    if isinstance(ts, str):
                        date = datetime.fromisoformat(ts.replace('Z', '+00:00')).date()
                    else:
                        date = ts.date()
                    
                    day_str = date.strftime('%Y-%m-%d')
                    daily[day_str]['count'] += 1
                    daily[day_str]['records'].append(
                        record.get('session_id') or record.get('match_id')
                    )
                except (ValueError, TypeError):
                    continue
        
        return dict(daily)
    
    def _venue_breakdown(
        self,
        matches: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Create breakdown by venue."""
        venue_stats = defaultdict(lambda: {'matches': 0, 'won': 0})
        
        for match in matches:
            venue = match.get('competition_details', {}).get('venue', 'Unknown')
            venue_stats[venue]['matches'] += 1
            if match.get('result', {}).get('won', False):
                venue_stats[venue]['won'] += 1
        
        return [
            {
                'venue': venue,
                'matches': stats['matches'],
                'wins': stats['won'],
                'win_rate': (stats['won'] / stats['matches'] * 100) if stats['matches'] > 0 else 0
            }
            for venue, stats in venue_stats.items()
        ]
    
    def _opponent_analysis(
        self,
        matches: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze performance against different opponents."""
        opponent_stats = defaultdict(lambda: {'matches': 0, 'won': 0, 'averages': []})
        
        for match in matches:
            opponent = match.get('opponent', {}).get('name', 'Unknown')
            opponent_stats[opponent]['matches'] += 1
            
            if match.get('result', {}).get('won', False):
                opponent_stats[opponent]['won'] += 1
            
            avg = match.get('metrics', {}).get('three_dart_average', 0)
            if avg > 0:
                opponent_stats[opponent]['averages'].append(avg)
        
        # Calculate per-opponent stats
        results = []
        for opponent, stats in opponent_stats.items():
            avg_against = (
                statistics.mean(stats['averages'])
                if stats['averages'] else 0
            )
            results.append({
                'opponent': opponent,
                'matches': stats['matches'],
                'record': f"{stats['won']}-{stats['matches'] - stats['won']}",
                'average_against': avg_against
            })
        
        return {
            'unique_opponents': len(opponent_stats),
            'opponent_details': sorted(
                results,
                key=lambda x: x['matches'],
                reverse=True
            )
        }
    
    def _calculate_improvement_trend(
        self,
        analyses: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Calculate improvement trends in biomechanics."""
        if len(analyses) < 2:
            return {'overall': 'insufficient_data'}
        
        # Sort by timestamp
        sorted_analyses = sorted(
            analyses,
            key=lambda x: x.get('timestamp', '')
        )
        
        # Compare first half to second half
        mid = len(sorted_analyses) // 2
        
        first_half_scores = [
            a.get('aggregate_analysis', {}).get('consistency_score', 0)
            for a in sorted_analyses[:mid]
        ]
        second_half_scores = [
            a.get('aggregate_analysis', {}).get('consistency_score', 0)
            for a in sorted_analyses[mid:]
        ]
        
        first_avg = statistics.mean(first_half_scores) if first_half_scores else 0
        second_avg = statistics.mean(second_half_scores) if second_half_scores else 0
        
        if second_avg > first_avg + 5:
            trend = 'improving'
        elif second_avg < first_avg - 5:
            trend = 'declining'
        else:
            trend = 'stable'
        
        return {
            'overall': trend,
            'first_half_avg': first_avg,
            'second_half_avg': second_avg
        }
    
    def _extract_key_themes(
        self,
        observations: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract key themes from observations."""
        themes = []
        
        # Collect technique notes
        technique_mentions = defaultdict(int)
        for obs in observations:
            for kw in obs.get('detected_keywords', []):
                technique_mentions[kw] += 1
        
        # Top themes
        sorted_themes = sorted(
            technique_mentions.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [theme for theme, _ in sorted_themes[:10]]
    
    def _create_cross_references(
        self,
        raw_data: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Create cross-references between data sources."""
        cross_refs = {
            'session_links': [],
            'timestamp_correlations': []
        }
        
        # Link biomechanics sessions to practice sessions
        for bio in raw_data.get('biomechanics', []):
            session_ref = bio.get('session_reference')
            if session_ref:
                for scolia in raw_data.get('scolia', []):
                    if scolia.get('session_id') == session_ref:
                        cross_refs['session_links'].append({
                            'biomechanics_id': bio.get('analysis_id'),
                            'scolia_id': session_ref
                        })
        
        # Link voice observations to sessions
        for voice in raw_data.get('voice_observation', []):
            session_ref = voice.get('session_reference')
            if session_ref:
                cross_refs['session_links'].append({
                    'voice_id': voice.get('observation_id'),
                    'session_reference': session_ref
                })
        
        return cross_refs
    
    def _collect_file_references(
        self,
        raw_data: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[str]]:
        """Collect all source file references."""
        refs = {}
        
        for source, records in raw_data.items():
            refs[source] = [
                r.get('_source_file', '')
                for r in records
                if r.get('_source_file')
            ]
        
        return refs
    
    def save_aggregated(
        self,
        aggregated_data: Dict[str, Any],
        filename: Optional[str] = None
    ) -> Path:
        """
        Save aggregated data to file.
        
        Args:
            aggregated_data: Data to save
            filename: Optional filename
            
        Returns:
            Path to saved file
        """
        if filename is None:
            end_date = aggregated_data.get('period', {}).get('end_date', '')
            if end_date:
                date_str = end_date[:10].replace('-', '')
            else:
                date_str = datetime.now().strftime('%Y%m%d')
            filename = f"aggregated_{date_str}.json"
        
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(aggregated_data, f, indent=2, default=str)
        
        self.logger.info(f"Saved aggregated data: {filepath}")
        return filepath
