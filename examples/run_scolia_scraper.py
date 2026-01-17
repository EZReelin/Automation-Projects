#!/usr/bin/env python3
"""
Scolia Comprehensive Scraper - Example Usage
============================================

This script demonstrates how to use the Scolia comprehensive scraper
to extract darts statistics for weekly performance assessments.

Usage:
    # First time setup (scrape all game types):
    python run_scolia_scraper.py --all

    # Incremental scraping (only new matches):
    python run_scolia_scraper.py --incremental

    # Scrape specific game types:
    python run_scolia_scraper.py --game-types x01 cricket

    # Export to JSON only:
    python run_scolia_scraper.py --format json

    # Export to CSV only:
    python run_scolia_scraper.py --format csv
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path to import dart_coach
sys.path.insert(0, str(Path(__file__).parent.parent))

from dart_coach.scrapers.scolia_comprehensive_scraper import ScoliaComprehensiveScraper


def setup_logging(level: str = "INFO"):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('scolia_scraper.log')
        ]
    )


def main():
    parser = argparse.ArgumentParser(
        description='Scolia Comprehensive Scraper - Extract darts statistics'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Scrape all game types (use for first run)'
    )

    parser.add_argument(
        '--incremental',
        action='store_true',
        help='Only scrape new matches since last run'
    )

    parser.add_argument(
        '--game-types',
        nargs='+',
        choices=['x01', 'cricket', 'around_the_world', 'bobs_27', 'shanghai'],
        help='Specific game types to scrape'
    )

    parser.add_argument(
        '--format',
        choices=['json', 'csv', 'both'],
        default='both',
        help='Export format (default: both)'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='./data/scolia',
        help='Output directory for scraped data'
    )

    parser.add_argument(
        '--headless',
        action='store_true',
        default=True,
        help='Run browser in headless mode (default: True)'
    )

    parser.add_argument(
        '--no-headless',
        action='store_false',
        dest='headless',
        help='Run browser with GUI (for debugging)'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    # Determine game types to scrape
    if args.all:
        game_types = None  # None means all game types
        logger.info("Scraping all game types")
    elif args.game_types:
        game_types = args.game_types
        logger.info(f"Scraping game types: {', '.join(game_types)}")
    else:
        # Default to X01 and Cricket
        game_types = ['x01', 'cricket']
        logger.info("Scraping default game types: X01, Cricket")

    # Check for credentials
    if not os.getenv('SCOLIA_USERNAME') or not os.getenv('SCOLIA_PASSWORD'):
        logger.error(
            "Scolia credentials not found!\n"
            "Please set environment variables:\n"
            "  export SCOLIA_USERNAME='your_email@example.com'\n"
            "  export SCOLIA_PASSWORD='your_password'"
        )
        sys.exit(1)

    try:
        # Initialize scraper
        logger.info("Initializing Scolia scraper...")
        data_dir = Path(args.output_dir)
        data_dir.mkdir(parents=True, exist_ok=True)

        scraper = ScoliaComprehensiveScraper(
            data_dir=data_dir,
            headless=args.headless,
            log_level=args.log_level
        )

        # Authenticate
        logger.info("Authenticating with Scolia...")
        if not scraper.authenticate():
            logger.error("Authentication failed!")
            sys.exit(1)

        logger.info("Authentication successful!")

        # Run scraping
        logger.info("Starting comprehensive data extraction...")
        json_path, csv_paths = scraper.run_full_scrape(
            game_types=game_types,
            export_format=args.format
        )

        # Report results
        logger.info("\n" + "="*60)
        logger.info("SCRAPING COMPLETED SUCCESSFULLY!")
        logger.info("="*60)

        if json_path:
            logger.info(f"JSON data saved to: {json_path}")

        if csv_paths:
            logger.info(f"CSV files saved ({len(csv_paths)} files):")
            for path in csv_paths:
                logger.info(f"  - {path}")

        logger.info("="*60)
        logger.info("\nYou can now use this data for LLM analysis!")
        logger.info("Next steps:")
        logger.info("  1. Review the exported data files")
        logger.info("  2. Feed the data to your local LLM for performance analysis")
        logger.info("  3. Run the scraper weekly for ongoing performance tracking")

    except KeyboardInterrupt:
        logger.info("\nScraping interrupted by user")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Error during scraping: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
