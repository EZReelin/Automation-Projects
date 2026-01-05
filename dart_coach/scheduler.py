"""
Scheduler Module
===============
Automated scheduling for weekly analysis runs.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

from .main import DartCoach


def run_scheduled_analysis(
    config_path: Optional[Path] = None,
    data_dir: Optional[Path] = None
):
    """
    Run the scheduled weekly analysis.
    
    This function is called by the scheduler on Sundays.
    """
    logger = logging.getLogger("DartCoachScheduler")
    
    logger.info("Starting scheduled weekly analysis")
    
    try:
        coach = DartCoach(
            config_path=config_path,
            data_dir=data_dir
        )
        
        results = coach.run_weekly_workflow(
            scrape=True,
            schedule=True,
            use_google_calendar=True
        )
        
        if results['success']:
            logger.info("Scheduled analysis completed successfully")
        else:
            logger.error(f"Scheduled analysis failed: {results.get('error')}")
            
    except Exception as e:
        logger.error(f"Scheduled analysis exception: {e}")


def start_scheduler(
    config_path: Optional[Path] = None,
    data_dir: Optional[Path] = None,
    day: str = 'sun',
    hour: int = 18,
    minute: int = 0
):
    """
    Start the background scheduler for automated weekly analysis.
    
    Args:
        config_path: Path to configuration file
        data_dir: Base data directory
        day: Day of week to run (mon, tue, wed, thu, fri, sat, sun)
        hour: Hour to run (0-23)
        minute: Minute to run (0-59)
    """
    if not SCHEDULER_AVAILABLE:
        print("APScheduler not installed. Install with: pip install apscheduler")
        sys.exit(1)
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("DartCoachScheduler")
    
    scheduler = BlockingScheduler()
    
    # Schedule the weekly analysis
    trigger = CronTrigger(
        day_of_week=day,
        hour=hour,
        minute=minute
    )
    
    scheduler.add_job(
        run_scheduled_analysis,
        trigger=trigger,
        kwargs={
            'config_path': config_path,
            'data_dir': data_dir
        },
        id='weekly_analysis',
        name='Weekly Dart Performance Analysis'
    )
    
    logger.info(f"Scheduler started. Weekly analysis will run on {day} at {hour:02d}:{minute:02d}")
    logger.info("Press Ctrl+C to stop")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Dart Coach Scheduler - Run automated weekly analysis"
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
        '--day',
        default='sun',
        choices=['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'],
        help='Day of week to run (default: sun)'
    )
    
    parser.add_argument(
        '--hour',
        type=int,
        default=18,
        help='Hour to run (0-23, default: 18)'
    )
    
    parser.add_argument(
        '--minute',
        type=int,
        default=0,
        help='Minute to run (0-59, default: 0)'
    )
    
    args = parser.parse_args()
    
    start_scheduler(
        config_path=args.config,
        data_dir=args.data_dir,
        day=args.day,
        hour=args.hour,
        minute=args.minute
    )
