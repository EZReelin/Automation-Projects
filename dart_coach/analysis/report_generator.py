"""
Report Generator Module
======================
Generates comprehensive weekly analysis reports.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .ollama_analyzer import OllamaAnalyzer


class ReportGenerator:
    """
    Generates comprehensive weekly analysis reports.
    
    Combines Ollama analysis with structured data summaries
    into a complete coaching report.
    """
    
    def __init__(
        self,
        data_dir: Path,
        output_dir: Optional[Path] = None,
        ollama_config: Optional[Dict] = None,
        log_level: str = "INFO"
    ):
        """
        Initialize report generator.
        
        Args:
            data_dir: Base data directory
            output_dir: Directory for generated reports
            ollama_config: Ollama configuration
            log_level: Logging level
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir) if output_dir else self.data_dir / 'reports'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        ollama_config = ollama_config or {}
        self.analyzer = OllamaAnalyzer(**ollama_config)
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
    
    def generate_weekly_report(
        self,
        aggregated_data: Dict[str, Any],
        previous_week_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a complete weekly analysis report.
        
        Args:
            aggregated_data: Current week's aggregated data
            previous_week_data: Previous week's data (optional)
            
        Returns:
            Complete report dictionary
        """
        report_id = f"report_{datetime.now().strftime('%Y%m%d')}"
        
        self.logger.info(f"Generating weekly report: {report_id}")
        
        # Check Ollama connection
        if not self.analyzer.check_connection():
            self.logger.warning(
                "Ollama not available. Report will contain data summaries only."
            )
            use_ai = False
        else:
            use_ai = True
        
        # Generate report sections
        report = {
            "report_id": report_id,
            "generated_at": datetime.now().isoformat(),
            "week_period": aggregated_data.get('period', {}),
            "data_sources_included": aggregated_data.get('data_sources_included', {}),
        }
        
        # Practice summary
        report["practice_summary"] = self._build_practice_summary(
            aggregated_data.get('practice_data', {})
        )
        
        # Competition summary
        report["competition_summary"] = self._build_competition_summary(
            aggregated_data.get('competition_data', {})
        )
        
        # Practice vs competition comparison
        report["practice_vs_competition_comparison"] = self._build_comparison(
            aggregated_data.get('practice_data', {}),
            aggregated_data.get('competition_data', {})
        )
        
        # Biomechanics summary
        report["biomechanics_summary"] = self._build_biomechanics_summary(
            aggregated_data.get('biomechanics_data', {})
        )
        
        # Observation summary
        report["observation_summary"] = self._build_observation_summary(
            aggregated_data.get('observations_data', {})
        )
        
        # AI-generated analysis
        if use_ai:
            report["analysis"] = self._generate_ai_analysis(
                aggregated_data,
                previous_week_data
            )
        else:
            report["analysis"] = self._generate_basic_analysis(
                aggregated_data,
                previous_week_data
            )
        
        # Raw data references
        report["raw_data_references"] = aggregated_data.get('raw_file_references', {})
        
        return report
    
    def _build_practice_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build practice summary section."""
        metrics = data.get('metrics', {})
        
        return {
            "total_practice_time_minutes": data.get('total_duration_minutes', 0),
            "total_darts_thrown": data.get('total_darts', 0),
            "sessions_count": data.get('sessions', 0),
            "average_session_duration": (
                data.get('total_duration_minutes', 0) / data.get('sessions', 1)
                if data.get('sessions', 0) > 0 else 0
            ),
            "metrics": {
                "average_ppd": metrics.get('average_ppd', 0),
                "average_three_dart": metrics.get('average_three_dart', 0),
                "best_three_dart": metrics.get('best_three_dart', 0),
                "average_checkout_pct": metrics.get('average_checkout_pct', 0),
                "best_checkout_pct": metrics.get('best_checkout_pct', 0),
                "total_180s": metrics.get('total_180s', 0),
                "total_ton_plus": (
                    metrics.get('total_140_plus', 0) +
                    metrics.get('total_100_plus', 0) +
                    metrics.get('total_180s', 0)
                )
            },
            "cpu_matches": data.get('match_results', {}).get('cpu_matches', {}),
            "online_matches": data.get('match_results', {}).get('online_matches', {})
        }
    
    def _build_competition_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build competition summary section."""
        metrics = data.get('metrics', {})
        record = data.get('overall_record', {})
        pressure = data.get('pressure_performance', {})
        
        total_matches = data.get('matches', 0)
        wins = record.get('won', 0)
        
        return {
            "total_matches": total_matches,
            "matches_won": wins,
            "matches_lost": record.get('lost', 0),
            "win_rate": (wins / total_matches * 100) if total_matches > 0 else 0,
            "legs_won": record.get('legs_won', 0),
            "legs_lost": record.get('legs_lost', 0),
            "leg_win_rate": (
                record.get('legs_won', 0) /
                (record.get('legs_won', 0) + record.get('legs_lost', 0)) * 100
                if (record.get('legs_won', 0) + record.get('legs_lost', 0)) > 0 else 0
            ),
            "metrics": {
                "average_ppd": metrics.get('average_ppd', 0),
                "average_three_dart": metrics.get('average_three_dart', 0),
                "best_match_average": metrics.get('best_match_average', 0),
                "average_checkout_pct": metrics.get('average_checkout_pct', 0),
                "total_180s": metrics.get('total_180s', 0),
                "highest_checkout": metrics.get('highest_checkout', 0)
            },
            "pressure_performance": {
                "match_darts_conversion_rate": pressure.get('match_darts_conversion', 0),
                "deciding_legs_won": pressure.get('deciding_legs_won', 0),
                "deciding_legs_played": 0  # Would need to track this
            },
            "venue_breakdown": data.get('venue_breakdown', [])
        }
    
    def _build_comparison(
        self,
        practice: Dict[str, Any],
        competition: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build practice vs competition comparison."""
        practice_avg = practice.get('metrics', {}).get('average_three_dart', 0)
        comp_avg = competition.get('metrics', {}).get('average_three_dart', 0)
        
        practice_checkout = practice.get('metrics', {}).get('average_checkout_pct', 0)
        comp_checkout = competition.get('metrics', {}).get('average_checkout_pct', 0)
        
        insights = []
        
        if practice_avg > 0 and comp_avg > 0:
            diff = practice_avg - comp_avg
            if diff > 10:
                insights.append(
                    f"Significant drop from practice to competition ({diff:.1f} points). "
                    "Focus on pressure management and match simulation in practice."
                )
            elif diff > 5:
                insights.append(
                    f"Moderate practice-to-competition gap ({diff:.1f} points). "
                    "Consider adding more pressure scenarios to practice."
                )
            elif diff < -5:
                insights.append(
                    f"Performing better in competition than practice ({abs(diff):.1f} points higher). "
                    "May thrive under pressure or practice conditions need review."
                )
            else:
                insights.append(
                    "Good consistency between practice and competition performance."
                )
        
        return {
            "average_difference": practice_avg - comp_avg if practice_avg and comp_avg else 0,
            "checkout_difference": practice_checkout - comp_checkout,
            "insights": insights
        }
    
    def _build_biomechanics_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build biomechanics summary section."""
        trend_data = data.get('improvement_trends', {})
        trend = trend_data.get('overall', 'unknown')
        
        # Format deviation details
        deviations = data.get('deviation_summary', [])[:3]
        formatted_issues = []
        
        recommendations = {
            'elbow_drop': "Focus on keeping elbow stable during the throw",
            'shoulder_rotation': "Minimize shoulder movement, throw with the arm",
            'early_release': "Extend arm fully before releasing",
            'late_release': "Release at the optimal extension point",
            'body_sway': "Keep body still, movement should be in the arm only",
            'incomplete_follow_through': "Point at the target after release"
        }
        
        for dev in deviations:
            dev_type = dev['type']
            formatted_issues.append({
                'issue': dev_type.replace('_', ' ').title(),
                'frequency': dev['count'],
                'recommendation': recommendations.get(dev_type, "Work with coach on correction")
            })
        
        return {
            "sessions_analyzed": data.get('sessions', 0),
            "throws_analyzed": data.get('total_throws_analyzed', 0),
            "average_consistency_score": data.get('average_consistency_score', 0),
            "consistency_trend": trend,
            "most_common_issues": formatted_issues,
            "form_improvements": []  # Would be populated from trend analysis
        }
    
    def _build_observation_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build observation summary section."""
        sentiment = data.get('sentiment_breakdown', {})
        
        total = sum(sentiment.values()) if sentiment else 1
        
        return {
            "total_observations": data.get('total_observations', 0),
            "key_themes": data.get('key_themes', [])[:5],
            "mental_state_trends": {
                "overall_sentiment": (
                    "positive" if sentiment.get('positive', 0) > sentiment.get('negative', 0)
                    else "negative" if sentiment.get('negative', 0) > sentiment.get('positive', 0)
                    else "neutral"
                ),
                "confidence_mentions": sum(
                    1 for kw in data.get('top_keywords', [])
                    if 'confiden' in kw.get('keyword', '').lower()
                ),
                "frustration_mentions": sum(
                    1 for kw in data.get('top_keywords', [])
                    if 'frustrat' in kw.get('keyword', '').lower()
                ),
                "focus_mentions": sum(
                    1 for kw in data.get('top_keywords', [])
                    if 'focus' in kw.get('keyword', '').lower()
                )
            },
            "technique_feedback": data.get('action_items', [])[:5]
        }
    
    def _generate_ai_analysis(
        self,
        aggregated_data: Dict[str, Any],
        previous_week: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate AI-powered analysis sections."""
        # Get main analysis
        weekly_analysis = self.analyzer.analyze_weekly_performance(aggregated_data)
        
        # Get specific analyses
        trend_analysis = self.analyzer.analyze_trends(aggregated_data, previous_week)
        
        bio_data = aggregated_data.get('biomechanics_data', {})
        bio_analysis = ""
        if bio_data.get('sessions', 0) > 0:
            bio_analysis = self.analyzer.analyze_biomechanics(bio_data)
        
        mental_analysis = self.analyzer.analyze_mental_game(aggregated_data)
        
        # Get recommendations
        drill_recommendations = self.analyzer.recommend_drills(aggregated_data)
        goal_recommendations = self.analyzer.set_goals(aggregated_data, previous_week)
        
        # Parse into structured format
        return {
            "executive_summary": self._extract_section(weekly_analysis, "Executive Summary"),
            "key_findings": self._parse_findings(weekly_analysis),
            "trends": self._parse_trends(trend_analysis, aggregated_data),
            "week_over_week_comparison": self._parse_comparison(trend_analysis, previous_week),
            "recommendations": self._parse_recommendations(drill_recommendations),
            "practice_plan": self._parse_practice_plan(drill_recommendations, goal_recommendations),
            "goals_for_next_week": self._parse_goals(goal_recommendations),
            "raw_analysis": {
                "weekly": weekly_analysis,
                "trends": trend_analysis,
                "biomechanics": bio_analysis,
                "mental": mental_analysis,
                "drills": drill_recommendations,
                "goals": goal_recommendations
            }
        }
    
    def _generate_basic_analysis(
        self,
        aggregated_data: Dict[str, Any],
        previous_week: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate basic analysis without AI."""
        practice = aggregated_data.get('practice_data', {})
        competition = aggregated_data.get('competition_data', {})
        
        practice_avg = practice.get('metrics', {}).get('average_three_dart', 0)
        comp_avg = competition.get('metrics', {}).get('average_three_dart', 0)
        
        # Basic findings
        findings = []
        
        if practice.get('sessions', 0) > 0:
            findings.append({
                "finding": f"Completed {practice.get('sessions', 0)} practice sessions",
                "category": "observation",
                "supporting_data": f"Average: {practice_avg:.1f}"
            })
        
        if competition.get('matches', 0) > 0:
            record = competition.get('overall_record', {})
            findings.append({
                "finding": f"Competition record: {record.get('won', 0)}-{record.get('lost', 0)}",
                "category": "observation",
                "supporting_data": f"Average: {comp_avg:.1f}"
            })
        
        return {
            "executive_summary": (
                f"Week summary: {practice.get('sessions', 0)} practice sessions and "
                f"{competition.get('matches', 0)} competitive matches. "
                "AI analysis unavailable - Ollama not connected."
            ),
            "key_findings": findings,
            "trends": {
                "scoring": "unknown",
                "checkout": "unknown",
                "consistency": "unknown",
                "mental_game": "unknown"
            },
            "recommendations": [],
            "practice_plan": {},
            "goals_for_next_week": [],
            "note": "Full AI analysis requires Ollama to be running"
        }
    
    def _extract_section(self, text: str, section_name: str) -> str:
        """Extract a section from analysis text."""
        lines = text.split('\n')
        in_section = False
        content = []
        
        for line in lines:
            if section_name.lower() in line.lower() and ('**' in line or '#' in line):
                in_section = True
                continue
            elif in_section and ('**' in line or line.startswith('#')):
                break
            elif in_section:
                content.append(line)
        
        return ' '.join(content).strip() if content else text[:500]
    
    def _parse_findings(self, analysis_text: str) -> list:
        """Parse key findings from analysis text."""
        # Simple extraction - would be more sophisticated with structured output
        findings = []
        lines = analysis_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('- ') or line.startswith('* '):
                finding_text = line[2:].strip()
                category = "observation"
                
                if any(w in finding_text.lower() for w in ['strength', 'good', 'excellent']):
                    category = "strength"
                elif any(w in finding_text.lower() for w in ['weakness', 'improve', 'work on']):
                    category = "weakness"
                elif any(w in finding_text.lower() for w in ['trend', 'increasing', 'decreasing']):
                    category = "trend"
                
                findings.append({
                    "finding": finding_text[:200],
                    "category": category,
                    "supporting_data": ""
                })
        
        return findings[:10]
    
    def _parse_trends(
        self,
        trend_text: str,
        aggregated_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """Parse trend information."""
        text_lower = trend_text.lower()
        
        return {
            "scoring": (
                "improving" if "scoring" in text_lower and "improv" in text_lower
                else "declining" if "scoring" in text_lower and "declin" in text_lower
                else "stable"
            ),
            "checkout": (
                "improving" if "checkout" in text_lower and "improv" in text_lower
                else "declining" if "checkout" in text_lower and "declin" in text_lower
                else "stable"
            ),
            "consistency": (
                "improving" if "consisten" in text_lower and "improv" in text_lower
                else "declining" if "consisten" in text_lower and "declin" in text_lower
                else "stable"
            ),
            "mental_game": (
                "improving" if "mental" in text_lower and "improv" in text_lower
                else "declining" if "mental" in text_lower and "declin" in text_lower
                else "stable"
            )
        }
    
    def _parse_comparison(
        self,
        trend_text: str,
        previous_week: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Parse week-over-week comparison."""
        if not previous_week:
            return {
                "average_change": 0,
                "checkout_change": 0,
                "win_rate_change": 0,
                "notable_changes": ["No previous week data for comparison"]
            }
        
        return {
            "average_change": 0,  # Would calculate from actual data
            "checkout_change": 0,
            "win_rate_change": 0,
            "notable_changes": []
        }
    
    def _parse_recommendations(self, drill_text: str) -> list:
        """Parse recommendations from drill text."""
        recommendations = []
        lines = drill_text.split('\n')
        
        current_rec = None
        for line in lines:
            line = line.strip()
            
            if line.startswith('#') or line.startswith('**'):
                if current_rec:
                    recommendations.append(current_rec)
                current_rec = {
                    "area": line.replace('#', '').replace('*', '').strip(),
                    "recommendation": "",
                    "priority": "medium",
                    "specific_drills": []
                }
            elif current_rec and line:
                if line.startswith('- ') or line.startswith('* '):
                    current_rec["specific_drills"].append(line[2:])
                else:
                    current_rec["recommendation"] += " " + line
        
        if current_rec:
            recommendations.append(current_rec)
        
        return recommendations[:5]
    
    def _parse_practice_plan(
        self,
        drill_text: str,
        goal_text: str
    ) -> Dict[str, Any]:
        """Parse practice plan from recommendations."""
        return {
            "focus_areas": [],
            "suggested_sessions": [],
            "mental_exercises": []
        }
    
    def _parse_goals(self, goal_text: str) -> list:
        """Parse goals from goal text."""
        goals = []
        lines = goal_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('- ') or line.startswith('* '):
                goals.append({
                    "goal": line[2:].strip()[:200],
                    "metric": "",
                    "target": ""
                })
        
        return goals[:5]
    
    def save_report(
        self,
        report: Dict[str, Any],
        filename: Optional[str] = None,
        format: str = 'json'
    ) -> Path:
        """
        Save report to file.
        
        Args:
            report: Report data
            filename: Optional filename
            format: Output format ('json' or 'md')
            
        Returns:
            Path to saved file
        """
        if filename is None:
            filename = f"{report.get('report_id', 'report')}"
        
        if format == 'json':
            filepath = self.output_dir / f"{filename}.json"
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str)
        
        elif format == 'md':
            filepath = self.output_dir / f"{filename}.md"
            markdown = self._report_to_markdown(report)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown)
        
        self.logger.info(f"Saved report: {filepath}")
        return filepath
    
    def _report_to_markdown(self, report: Dict[str, Any]) -> str:
        """Convert report to markdown format."""
        period = report.get('week_period', {})
        analysis = report.get('analysis', {})
        
        md = f"""# Dart Performance Weekly Analysis

**Report ID:** {report.get('report_id', 'N/A')}  
**Generated:** {report.get('generated_at', 'N/A')}  
**Period:** {period.get('start_date', 'N/A')} to {period.get('end_date', 'N/A')}

---

## Executive Summary

{analysis.get('executive_summary', 'No summary available.')}

---

## Key Findings

"""
        for finding in analysis.get('key_findings', []):
            md += f"- **[{finding.get('category', 'observation').upper()}]** {finding.get('finding', '')}\n"
        
        practice = report.get('practice_summary', {})
        md += f"""

---

## Practice Performance

- **Sessions:** {practice.get('sessions_count', 0)}
- **Total Practice Time:** {practice.get('total_practice_time_minutes', 0):.0f} minutes
- **Darts Thrown:** {practice.get('total_darts_thrown', 0)}
- **Average:** {practice.get('metrics', {}).get('average_three_dart', 0):.1f}
- **Checkout %:** {practice.get('metrics', {}).get('average_checkout_pct', 0):.1f}%
- **180s:** {practice.get('metrics', {}).get('total_180s', 0)}

"""
        
        competition = report.get('competition_summary', {})
        md += f"""
---

## Competition Performance

- **Matches:** {competition.get('total_matches', 0)}
- **Record:** {competition.get('matches_won', 0)}-{competition.get('matches_lost', 0)}
- **Win Rate:** {competition.get('win_rate', 0):.1f}%
- **Average:** {competition.get('metrics', {}).get('average_three_dart', 0):.1f}
- **Checkout %:** {competition.get('metrics', {}).get('average_checkout_pct', 0):.1f}%

"""
        
        md += """
---

## Recommendations

"""
        for rec in analysis.get('recommendations', []):
            md += f"### {rec.get('area', 'General')}\n\n"
            md += f"{rec.get('recommendation', '')}\n\n"
            if rec.get('specific_drills'):
                md += "**Drills:**\n"
                for drill in rec['specific_drills']:
                    md += f"- {drill}\n"
                md += "\n"
        
        md += """
---

## Goals for Next Week

"""
        for goal in analysis.get('goals_for_next_week', []):
            md += f"- {goal.get('goal', '')}\n"
        
        md += """

---

*Generated by Dart Performance Coach*
"""
        
        return md
