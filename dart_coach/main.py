"""
Main Orchestration Module
========================
Central orchestrator for the dart performance coaching system.
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from . import DEFAULT_CONFIG_DIR, DEFAULT_DATA_DIR, DEFAULT_SCHEMA_DIR
from .analysis.report_generator import ReportGenerator
from .calendar.google_calendar import GoogleCalendarIntegration
from .calendar.ical_generator import ICalGenerator
from .data_pipeline.aggregator import DataAggregator
from .scrapers.dart_connect_scraper import DartConnectScraper
from .scrapers.scolia_scraper import ScoliaScraper


class DartCoach:
    """
    Main orchestrator for the dart performance coaching system.
    
    Coordinates data collection, analysis, and reporting.
    """
    
    def __init__(
        self,
        config_path: Optional[Path] = None,
        data_dir: Optional[Path] = None,
        log_level: str = "INFO"
    ):
        """
        Initialize the Dart Coach system.
        
        Args:
            config_path: Path to configuration file
            data_dir: Base data directory
            log_level: Logging level
        """
        self.config = self._load_config(config_path)
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self._setup_logging(log_level)
        
        # Initialize components (lazy loading)
        self._scolia_scraper: Optional[ScoliaScraper] = None
        self._dart_connect_scraper: Optional[DartConnectScraper] = None
        self._aggregator: Optional[DataAggregator] = None
        self._report_generator: Optional[ReportGenerator] = None
        self._calendar: Optional[GoogleCalendarIntegration] = None
        self._ical: Optional[ICalGenerator] = None
        
        self.logger.info("Dart Coach initialized")
    
    def _load_config(self, config_path: Optional[Path]) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if config_path is None:
            config_path = DEFAULT_CONFIG_DIR / "settings.yaml"
        
        if config_path.exists():
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        
        return {}
    
    def _setup_logging(self, log_level: str):
        """Setup logging configuration."""
        self.logger = logging.getLogger("DartCoach")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
            
            # Also log to file
            log_dir = self.data_dir / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(
                log_dir / f"dart_coach_{datetime.now().strftime('%Y%m%d')}.log"
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(file_handler)
    
    @property
    def scolia_scraper(self) -> ScoliaScraper:
        """Get or create Scolia scraper."""
        if self._scolia_scraper is None:
            self._scolia_scraper = ScoliaScraper(
                data_dir=self.data_dir / "scolia",
                **self.config.get('scolia', {})
            )
        return self._scolia_scraper
    
    @property
    def dart_connect_scraper(self) -> DartConnectScraper:
        """Get or create Dart Connect scraper."""
        if self._dart_connect_scraper is None:
            self._dart_connect_scraper = DartConnectScraper(
                data_dir=self.data_dir / "dart_connect",
                **self.config.get('dart_connect', {})
            )
        return self._dart_connect_scraper
    
    @property
    def aggregator(self) -> DataAggregator:
        """Get or create data aggregator."""
        if self._aggregator is None:
            self._aggregator = DataAggregator(
                data_dir=self.data_dir,
                schema_dir=DEFAULT_SCHEMA_DIR,
                output_dir=self.data_dir / "aggregated"
            )
        return self._aggregator
    
    @property
    def report_generator(self) -> ReportGenerator:
        """Get or create report generator."""
        if self._report_generator is None:
            self._report_generator = ReportGenerator(
                data_dir=self.data_dir,
                output_dir=self.data_dir / "reports",
                ollama_config=self.config.get('ollama', {})
            )
        return self._report_generator
    
    @property
    def calendar(self) -> GoogleCalendarIntegration:
        """Get or create Google Calendar integration."""
        if self._calendar is None:
            self._calendar = GoogleCalendarIntegration(
                **self.config.get('calendar', {})
            )
        return self._calendar
    
    @property
    def ical(self) -> ICalGenerator:
        """Get or create iCal generator."""
        if self._ical is None:
            self._ical = ICalGenerator(
                output_dir=self.data_dir / "calendar"
            )
        return self._ical
    
    def scrape_scolia(
        self,
        days: int = 7,
        authenticate: bool = True
    ) -> int:
        """
        Scrape data from Scolia.
        
        Args:
            days: Number of days to scrape
            authenticate: Whether to authenticate first
            
        Returns:
            Number of sessions scraped
        """
        self.logger.info(f"Scraping Scolia data for last {days} days")
        
        if authenticate:
            if not self.scolia_scraper.authenticate():
                self.logger.error("Scolia authentication failed")
                return 0
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        files = self.scolia_scraper.scrape_and_save(start_date, end_date)
        
        self.logger.info(f"Scraped {len(files)} Scolia sessions")
        return len(files)
    
    def scrape_dart_connect(
        self,
        days: int = 7,
        authenticate: bool = True
    ) -> int:
        """
        Scrape data from Dart Connect.
        
        Args:
            days: Number of days to scrape
            authenticate: Whether to authenticate first
            
        Returns:
            Number of matches scraped
        """
        self.logger.info(f"Scraping Dart Connect data for last {days} days")
        
        if authenticate:
            if not self.dart_connect_scraper.authenticate():
                self.logger.error("Dart Connect authentication failed")
                return 0
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        files = self.dart_connect_scraper.scrape_and_save(start_date, end_date)
        
        self.logger.info(f"Scraped {len(files)} Dart Connect matches")
        return len(files)
    
    def aggregate_weekly_data(
        self,
        week_end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Aggregate all data for a week.
        
        Args:
            week_end_date: End date of the week
            
        Returns:
            Aggregated data dictionary
        """
        self.logger.info("Aggregating weekly data")
        
        aggregated = self.aggregator.aggregate_week(week_end_date)
        filepath = self.aggregator.save_aggregated(aggregated)
        
        self.logger.info(f"Aggregated data saved to {filepath}")
        return aggregated
    
    def generate_weekly_report(
        self,
        aggregated_data: Optional[Dict[str, Any]] = None,
        previous_week_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Generate the weekly analysis report.
        
        Args:
            aggregated_data: Pre-aggregated data (if None, will aggregate)
            previous_week_path: Path to previous week's aggregated data
            
        Returns:
            Generated report
        """
        self.logger.info("Generating weekly analysis report")
        
        if aggregated_data is None:
            aggregated_data = self.aggregate_weekly_data()
        
        # Load previous week if provided
        previous_week = None
        if previous_week_path and previous_week_path.exists():
            import json
            with open(previous_week_path) as f:
                previous_week = json.load(f)
        
        report = self.report_generator.generate_weekly_report(
            aggregated_data,
            previous_week
        )
        
        # Save both JSON and Markdown versions
        self.report_generator.save_report(report, format='json')
        self.report_generator.save_report(report, format='md')
        
        self.logger.info("Weekly report generated")
        return report
    
    def schedule_calendar_event(
        self,
        report: Dict[str, Any],
        use_google: bool = True
    ) -> Optional[str]:
        """
        Schedule the report as a calendar event.
        
        Args:
            report: Generated report
            use_google: Use Google Calendar (if False, generates iCal file)
            
        Returns:
            Event ID or file path
        """
        self.logger.info("Scheduling calendar event")
        
        if use_google:
            event_id = self.calendar.create_analysis_event(report)
            if event_id:
                self.logger.info(f"Created Google Calendar event: {event_id}")
            return event_id
        else:
            filepath = self.ical.generate_event(report)
            self.logger.info(f"Generated iCal file: {filepath}")
            return str(filepath)
    
    def run_weekly_workflow(
        self,
        scrape: bool = True,
        schedule: bool = True,
        use_google_calendar: bool = True
    ) -> Dict[str, Any]:
        """
        Run the complete weekly analysis workflow.
        
        Args:
            scrape: Whether to scrape new data
            schedule: Whether to schedule calendar event
            use_google_calendar: Use Google Calendar vs iCal
            
        Returns:
            Workflow results summary
        """
        self.logger.info("Starting weekly workflow")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'scraping': {'scolia': 0, 'dart_connect': 0},
            'aggregation': None,
            'report': None,
            'calendar': None,
            'success': False
        }
        
        try:
            # Step 1: Scrape data
            if scrape:
                results['scraping']['scolia'] = self.scrape_scolia()
                results['scraping']['dart_connect'] = self.scrape_dart_connect()
            
            # Step 2: Aggregate data
            aggregated = self.aggregate_weekly_data()
            results['aggregation'] = {
                'sources': aggregated.get('data_sources_included', {})
            }
            
            # Step 3: Generate report
            report = self.generate_weekly_report(aggregated)
            results['report'] = {
                'id': report.get('report_id'),
                'period': report.get('week_period')
            }
            
            # Step 4: Schedule calendar event
            if schedule:
                event_result = self.schedule_calendar_event(
                    report,
                    use_google=use_google_calendar
                )
                results['calendar'] = event_result
            
            results['success'] = True
            self.logger.info("Weekly workflow completed successfully")
            
        except Exception as e:
            self.logger.error(f"Weekly workflow failed: {e}")
            results['error'] = str(e)
        
        return results


def create_cli_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Dart Performance Coach - Automated Performance Analysis System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dart-coach weekly              Run complete weekly analysis
  dart-coach scrape --scolia     Scrape Scolia data only
  dart-coach scrape --all        Scrape all data sources
  dart-coach report              Generate report from existing data
  dart-coach schedule            Schedule calendar event from latest report
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=Path,
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '--data-dir', '-d',
        type=Path,
        help='Data directory path'
    )
    
    parser.add_argument(
        '--log-level', '-l',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Weekly command
    weekly_parser = subparsers.add_parser(
        'weekly',
        help='Run complete weekly analysis workflow'
    )
    weekly_parser.add_argument(
        '--no-scrape',
        action='store_true',
        help='Skip data scraping'
    )
    weekly_parser.add_argument(
        '--no-calendar',
        action='store_true',
        help='Skip calendar scheduling'
    )
    weekly_parser.add_argument(
        '--ical',
        action='store_true',
        help='Generate iCal file instead of Google Calendar event'
    )
    
    # Scrape command
    scrape_parser = subparsers.add_parser(
        'scrape',
        help='Scrape data from sources'
    )
    scrape_parser.add_argument(
        '--scolia',
        action='store_true',
        help='Scrape Scolia data'
    )
    scrape_parser.add_argument(
        '--dart-connect',
        action='store_true',
        help='Scrape Dart Connect data'
    )
    scrape_parser.add_argument(
        '--all',
        action='store_true',
        help='Scrape all sources'
    )
    scrape_parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days to scrape (default: 7)'
    )
    
    # Report command
    report_parser = subparsers.add_parser(
        'report',
        help='Generate analysis report'
    )
    report_parser.add_argument(
        '--previous',
        type=Path,
        help='Path to previous week data for comparison'
    )
    
    # Schedule command
    schedule_parser = subparsers.add_parser(
        'schedule',
        help='Schedule calendar event'
    )
    schedule_parser.add_argument(
        '--report',
        type=Path,
        help='Path to report JSON file'
    )
    schedule_parser.add_argument(
        '--ical',
        action='store_true',
        help='Generate iCal file instead of Google Calendar event'
    )
    
    # Biomechanics command
    bio_parser = subparsers.add_parser(
        'biomechanics',
        help='Run biomechanical analysis'
    )
    bio_parser.add_argument(
        '--duration',
        type=int,
        default=300,
        help='Analysis duration in seconds (default: 300)'
    )
    bio_parser.add_argument(
        '--display',
        action='store_true',
        help='Display video with annotations'
    )
    bio_parser.add_argument(
        '--video',
        type=Path,
        help='Process existing video file instead of live capture'
    )
    
    # Voice command
    voice_parser = subparsers.add_parser(
        'voice',
        help='Record voice observations'
    )
    voice_parser.add_argument(
        '--duration',
        type=int,
        default=1800,
        help='Recording duration in seconds (default: 1800)'
    )
    voice_parser.add_argument(
        '--audio',
        type=Path,
        help='Process existing audio file instead of live recording'
    )
    
    return parser


def main():
    """Main entry point for CLI."""
    parser = create_cli_parser()
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    # Initialize coach
    coach = DartCoach(
        config_path=args.config,
        data_dir=args.data_dir,
        log_level=args.log_level
    )
    
    if args.command == 'weekly':
        results = coach.run_weekly_workflow(
            scrape=not args.no_scrape,
            schedule=not args.no_calendar,
            use_google_calendar=not args.ical
        )
        print(f"\nWeekly workflow completed: {'SUCCESS' if results['success'] else 'FAILED'}")
        
    elif args.command == 'scrape':
        if args.all or args.scolia:
            count = coach.scrape_scolia(days=args.days)
            print(f"Scraped {count} Scolia sessions")
        
        if args.all or args.dart_connect:
            count = coach.scrape_dart_connect(days=args.days)
            print(f"Scraped {count} Dart Connect matches")
        
        if not (args.all or args.scolia or args.dart_connect):
            print("Specify --scolia, --dart-connect, or --all")
    
    elif args.command == 'report':
        report = coach.generate_weekly_report(previous_week_path=args.previous)
        print(f"Generated report: {report.get('report_id')}")
    
    elif args.command == 'schedule':
        import json
        
        if args.report:
            with open(args.report) as f:
                report = json.load(f)
        else:
            # Use latest report
            reports_dir = coach.data_dir / "reports"
            latest = sorted(reports_dir.glob("*.json"))[-1] if reports_dir.exists() else None
            if latest:
                with open(latest) as f:
                    report = json.load(f)
            else:
                print("No report found. Generate one first with 'dart-coach report'")
                return
        
        result = coach.schedule_calendar_event(report, use_google=not args.ical)
        print(f"Scheduled event: {result}")
    
    elif args.command == 'biomechanics':
        from .biomechanics import ThrowAnalyzer
        
        analyzer = ThrowAnalyzer(
            data_dir=coach.data_dir / "biomechanics"
        )
        
        if args.video:
            results = analyzer.process_video_file(args.video, display=args.display)
        else:
            analyzer.start_session()
            results = analyzer.process_live(args.duration, display=args.display)
            analyzer.stop_session()
        
        print(f"Analyzed {results.get('total_throws_analyzed', 0)} throws")
    
    elif args.command == 'voice':
        from .voice import ObservationProcessor
        
        processor = ObservationProcessor(
            data_dir=coach.data_dir / "voice"
        )
        
        if args.audio:
            results = processor.process_existing_recording(args.audio)
        else:
            processor.start_session()
            import time
            print(f"Recording for {args.duration} seconds... Press Ctrl+C to stop early.")
            try:
                time.sleep(args.duration)
            except KeyboardInterrupt:
                pass
            results = processor.stop_session()
        
        print(f"Processed {results.get('observations', []).__len__()} observations")


if __name__ == '__main__':
    main()
