#!/usr/bin/env python3
"""
GoDartsPro Scraper Usage Example
=================================
Demonstrates how to use the GoDartsPro scraper to extract dart training statistics.
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import date, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dart_coach.scrapers import GoDartsProScraper, scrape_godartspro
from dotenv import load_dotenv
import yaml


async def example_basic_scraping():
    """Example 1: Basic scraping using the convenience function."""
    print("=" * 60)
    print("Example 1: Basic Scraping (Incremental)")
    print("=" * 60)

    # Load environment variables
    load_dotenv(Path(__file__).parent.parent / 'dart_coach' / 'config' / '.env')

    username = os.getenv('GODARTSPRO_USERNAME')
    password = os.getenv('GODARTSPRO_PASSWORD')

    if not username or not password:
        print("ERROR: GODARTSPRO_USERNAME and GODARTSPRO_PASSWORD must be set in .env file")
        return

    # Setup paths
    config_file = Path(__file__).parent.parent / 'dart_coach' / 'config' / 'settings.yaml'
    data_dir = Path(__file__).parent.parent / 'data' / 'godartspro'
    data_dir.mkdir(parents=True, exist_ok=True)

    # Run scraper
    try:
        result_file = await scrape_godartspro(
            username=username,
            password=password,
            config_file=config_file,
            data_dir=data_dir,
            incremental=True  # Resume from last processed date
        )
        print(f"\n✓ Data saved to: {result_file}")
    except Exception as e:
        print(f"\n✗ Error: {e}")


async def example_advanced_scraping():
    """Example 2: Advanced scraping with custom date range and options."""
    print("\n" + "=" * 60)
    print("Example 2: Advanced Scraping (Custom Date Range)")
    print("=" * 60)

    # Load environment variables
    load_dotenv(Path(__file__).parent.parent / 'dart_coach' / 'config' / '.env')

    username = os.getenv('GODARTSPRO_USERNAME')
    password = os.getenv('GODARTSPRO_PASSWORD')

    if not username or not password:
        print("ERROR: Credentials not found")
        return

    # Load configuration
    config_file = Path(__file__).parent.parent / 'dart_coach' / 'config' / 'settings.yaml'
    with open(config_file, 'r') as f:
        settings = yaml.safe_load(f)

    config = settings.get('godartspro', {})
    data_dir = Path(__file__).parent.parent / 'data' / 'godartspro'
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create scraper instance with custom configuration
    async with GoDartsProScraper(
        username=username,
        password=password,
        config=config,
        data_dir=data_dir,
        log_level='DEBUG'
    ) as scraper:

        # Define custom date range (last 30 days)
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        print(f"\nScraping data from {start_date} to {end_date}")

        # Scrape with custom date range
        sessions = await scraper.scrape_all(
            start_date=start_date,
            end_date=end_date,
            incremental=False  # Don't use state management for this run
        )

        print(f"\n✓ Scraped {len(sessions)} sessions")

        # Save results
        result_file = scraper.save_results()
        print(f"✓ Data saved to: {result_file}")

        # Show statistics
        stats = scraper.get_scrape_statistics()
        print("\nScrape Statistics:")
        print(f"  Total sessions scraped (all time): {stats['total_sessions_scraped']}")
        print(f"  Last successful scrape: {stats['last_successful_scrape']}")
        print(f"  Success rate: {stats['success_rate']:.1f}%")


async def example_inspect_state():
    """Example 3: Inspect scraper state."""
    print("\n" + "=" * 60)
    print("Example 3: Inspect Scraper State")
    print("=" * 60)

    from dart_coach.scrapers.scraper_state_manager import ScraperStateManager

    state_dir = Path(__file__).parent.parent / 'data' / 'godartspro'
    state_file = state_dir / 'godartspro_scraper_state.json'

    if not state_file.exists():
        print(f"No state file found at {state_file}")
        print("Run the scraper first to create state.")
        return

    # Load state manager
    with ScraperStateManager(state_file) as state_mgr:
        stats = state_mgr.get_scrape_statistics()

        print("\nState Information:")
        print(f"  Last processed date: {stats['last_processed_date']}")
        print(f"  Total sessions scraped: {stats['total_sessions_scraped']}")
        print(f"  Last successful scrape: {stats['last_successful_scrape']}")
        print(f"  Total scrape runs: {stats['total_scrape_runs']}")
        print(f"  Successful runs: {stats['successful_runs']}")
        print(f"  Failed runs: {stats['failed_runs']}")
        print(f"  Success rate: {stats['success_rate']:.1f}%")

        # Show recent scrape history
        print("\nRecent Scrape History:")
        history = state_mgr.state.get('scrape_history', [])
        for entry in history[-5:]:  # Last 5 entries
            timestamp = entry.get('timestamp', 'Unknown')
            sessions = entry.get('sessions_scraped', 0)
            success = '✓' if entry.get('success', False) else '✗'
            print(f"  {success} {timestamp}: {sessions} sessions")


async def example_reset_state():
    """Example 4: Reset scraper state (use carefully!)."""
    print("\n" + "=" * 60)
    print("Example 4: Reset Scraper State")
    print("=" * 60)

    from dart_coach.scrapers.scraper_state_manager import ScraperStateManager

    state_dir = Path(__file__).parent.parent / 'data' / 'godartspro'
    state_file = state_dir / 'godartspro_scraper_state.json'

    if not state_file.exists():
        print(f"No state file found at {state_file}")
        return

    # Confirm reset
    response = input("\nWARNING: This will reset all scraper state. Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Reset cancelled.")
        return

    # Reset state
    with ScraperStateManager(state_file) as state_mgr:
        state_mgr.reset_state()
        print("\n✓ State has been reset")
        print("  Next scrape will start from the beginning")


async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("GoDartsPro Scraper Examples")
    print("=" * 60)

    # Check for credentials
    load_dotenv(Path(__file__).parent.parent / 'dart_coach' / 'config' / '.env')
    if not os.getenv('GODARTSPRO_USERNAME') or not os.getenv('GODARTSPRO_PASSWORD'):
        print("\nERROR: GoDartsPro credentials not configured!")
        print("\nSetup Instructions:")
        print("1. Copy dart_coach/config/.env.example to dart_coach/config/.env")
        print("2. Edit .env and add your GoDartsPro credentials:")
        print("   GODARTSPRO_USERNAME=your_username")
        print("   GODARTSPRO_PASSWORD=your_password")
        print("3. Run this script again")
        return

    # Run examples (comment out examples you don't want to run)

    # Example 1: Basic incremental scraping
    await example_basic_scraping()

    # Example 2: Advanced scraping with custom date range
    # await example_advanced_scraping()

    # Example 3: Inspect state
    await example_inspect_state()

    # Example 4: Reset state (commented out for safety)
    # await example_reset_state()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == '__main__':
    # Run the async main function
    asyncio.run(main())
