# GoDartsPro Scraper Documentation

## Overview

The GoDartsPro scraper is a production-ready web scraping solution designed to extract comprehensive dart training statistics from the GoDartsPro platform. It uses Playwright for browser automation, implements state management for incremental scraping, and outputs structured data suitable for LLM analysis.

## Features

- ✅ **Playwright-based automation** - Handles JavaScript-heavy websites
- ✅ **State management** - Remembers last processed date to avoid duplicate scraping
- ✅ **Incremental scraping** - Resumes from where it left off
- ✅ **Comprehensive data extraction** - Dashboard stats, training logs, and detailed session statistics
- ✅ **Rate limiting** - Respects the platform with configurable delays
- ✅ **Error handling** - Robust retry logic and graceful degradation
- ✅ **Structured output** - JSON format with schema validation
- ✅ **Logging** - Detailed logging for debugging and monitoring

## Architecture

### Components

1. **GoDartsProScraper** - Main scraper class
2. **ScraperStateManager** - State persistence for incremental scraping
3. **Configuration** - YAML-based configuration in `settings.yaml`
4. **Schema** - JSON schema for data validation in `schemas/godartspro_schema.json`

### Data Flow

```
GoDartsPro Platform
       ↓
    Login/Auth
       ↓
  Dashboard Stats ──→ Extract overall statistics
       ↓
  Training Log ──────→ List of drill sessions
       ↓
  Individual Drills ─→ Click into each drill
       ↓
  Game Played Page ──→ Navigate to game details
       ↓
  Your Stats Ribbon ─→ Click to reveal statistics
       ↓
  Session Statistics → Extract individual & averaged stats
       ↓
  Structured JSON ───→ Save to file
       ↓
  State Update ──────→ Track last processed date
```

## Installation

### 1. Install Python Dependencies

```bash
cd /home/user/Automation-Projects
pip install -r dart_coach/requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install chromium
```

### 3. Configure Credentials

```bash
# Copy the example environment file
cp dart_coach/config/.env.example dart_coach/config/.env

# Edit the .env file and add your credentials
nano dart_coach/config/.env
```

Add your GoDartsPro credentials:
```bash
GODARTSPRO_USERNAME=your_username
GODARTSPRO_PASSWORD=your_password
```

### 4. Configure Selectors (Important!)

The scraper includes placeholder CSS selectors that **MUST** be updated based on the actual GoDartsPro website structure.

Edit `dart_coach/config/settings.yaml` and update the `godartspro.selectors` section:

```yaml
godartspro:
  selectors:
    # Update these based on actual GoDartsPro HTML structure
    login_username: "#username"              # Login username field
    login_password: "#password"              # Login password field
    login_submit: "button[type='submit']"    # Login submit button
    dashboard_stats: ".dashboard-stats"      # Dashboard stats container
    training_log: ".training-log"            # Training log container
    drill_entry: ".drill-entry"              # Individual drill entries
    your_stats_ribbon: ".stats-ribbon.red, button:has-text('Your Stats')"  # Stats ribbon
    session_date: ".session-date"            # Session date elements
    stats_table: ".stats-table"              # Statistics table
```

**How to find correct selectors:**
1. Open GoDartsPro in Chrome/Firefox
2. Right-click on elements → "Inspect"
3. Find the CSS class, ID, or tag name
4. Update the selectors in `settings.yaml`

## Usage

### Basic Usage (Recommended)

```python
import asyncio
from pathlib import Path
from dart_coach.scrapers import scrape_godartspro
from dotenv import load_dotenv
import os

# Load credentials
load_dotenv('dart_coach/config/.env')

# Run scraper
async def main():
    result_file = await scrape_godartspro(
        username=os.getenv('GODARTSPRO_USERNAME'),
        password=os.getenv('GODARTSPRO_PASSWORD'),
        config_file=Path('dart_coach/config/settings.yaml'),
        data_dir=Path('data/godartspro'),
        incremental=True  # Resume from last processed date
    )
    print(f"Data saved to: {result_file}")

asyncio.run(main())
```

### Advanced Usage

```python
import asyncio
from datetime import date, timedelta
from pathlib import Path
from dart_coach.scrapers import GoDartsProScraper
import yaml
import os

async def main():
    # Load configuration
    with open('dart_coach/config/settings.yaml') as f:
        config = yaml.safe_load(f)['godartspro']

    # Create scraper with custom settings
    async with GoDartsProScraper(
        username=os.getenv('GODARTSPRO_USERNAME'),
        password=os.getenv('GODARTSPRO_PASSWORD'),
        config=config,
        data_dir=Path('data/godartspro'),
        log_level='DEBUG'
    ) as scraper:

        # Scrape last 30 days
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        sessions = await scraper.scrape_all(
            start_date=start_date,
            end_date=end_date,
            incremental=False
        )

        # Save results
        result_file = scraper.save_results()

        # Get statistics
        stats = scraper.get_scrape_statistics()
        print(f"Scraped {len(sessions)} sessions")
        print(f"Total sessions (all time): {stats['total_sessions_scraped']}")

asyncio.run(main())
```

### Running the Example Script

```bash
cd /home/user/Automation-Projects
python examples/godartspro_scraper_example.py
```

## State Management

The scraper maintains state to enable incremental scraping:

### State File Location
- Default: `data/godartspro/godartspro_scraper_state.json`
- Configurable in `settings.yaml`

### State Contents
```json
{
  "created_at": "2026-01-17T10:00:00",
  "last_updated": "2026-01-17T11:30:00",
  "last_processed_date": "2026-01-15",
  "total_sessions_scraped": 45,
  "last_successful_scrape": "2026-01-17T11:30:00",
  "scrape_history": [
    {
      "timestamp": "2026-01-17T11:30:00",
      "sessions_scraped": 5,
      "success": true,
      "error_message": null
    }
  ],
  "metadata": {}
}
```

### Inspecting State

```python
from dart_coach.scrapers import ScraperStateManager

with ScraperStateManager('data/godartspro/godartspro_scraper_state.json') as state:
    print(f"Last processed: {state.get_last_processed_date()}")
    print(f"Statistics: {state.get_scrape_statistics()}")
```

### Resetting State

```python
from dart_coach.scrapers import ScraperStateManager

with ScraperStateManager('data/godartspro/godartspro_scraper_state.json') as state:
    state.reset_state()
    print("State reset - next scrape will start from beginning")
```

## Configuration Reference

### Browser Settings

```yaml
godartspro:
  browser:
    headless: true           # Run browser in headless mode
    timeout: 30000          # Page load timeout (ms)
    viewport:
      width: 1920
      height: 1080
```

### Rate Limiting

```yaml
godartspro:
  rate_limit_seconds: 2.0   # Delay between page navigations (seconds)
  retry_attempts: 3         # Number of retry attempts on failure
  retry_delay: 5            # Delay between retries (seconds)
```

### Data Collection

```yaml
godartspro:
  data_types:
    - dashboard_statistics      # Overall dashboard stats
    - training_log_entries      # Training log drill list
    - session_statistics        # Detailed session stats

  metrics_to_capture:
    - three_dart_average
    - first_nine_average
    - checkout_percentage
    - doubles_percentage
    - triples_percentage
    - 180s_count
    - 140_plus_count
    - 100_plus_count
    - highest_checkout
    - total_darts
    - session_count
```

## Output Format

### Data Structure

```json
{
  "session_id": "godartspro_20260117_113000",
  "timestamp": "2026-01-17T11:30:00",
  "data_source": "godartspro",
  "context": "practice",
  "scrape_metadata": {
    "scrape_timestamp": "2026-01-17T11:30:00",
    "scraper_version": "1.0.0",
    "last_processed_date": "2026-01-15"
  },
  "dashboard_statistics": {
    "total_sessions": 120,
    "total_drills_completed": 450,
    "overall_average": 65.5,
    "best_average": 85.2,
    "total_practice_hours": 45.5,
    "current_streak": 7,
    "longest_streak": 21
  },
  "training_log_entry": {
    "drill_date": "2026-01-15",
    "drill_name": "501 Practice",
    "drill_type": "x01",
    "completion_status": "completed"
  },
  "session_statistics": {
    "session_date": "2026-01-15",
    "individual_session_stats": [
      {
        "date": "2026-01-15",
        "game_number": 1,
        "metrics": {
          "three_dart_average": 67.5,
          "first_nine_average": 72.0,
          "checkout_percentage": 45.5,
          "doubles_percentage": 38.2,
          "triples_percentage": 22.1
        }
      }
    ],
    "averaged_statistics": {
      "period": "all_time",
      "number_of_sessions": 120,
      "avg_three_dart_average": 65.5,
      "avg_checkout_percentage": 42.3,
      "total_180s": 15
    }
  }
}
```

### Schema Validation

Data conforms to the JSON schema defined in:
`dart_coach/schemas/godartspro_schema.json`

## Troubleshooting

### Common Issues

#### 1. Authentication Fails

**Problem:** Login unsuccessful

**Solutions:**
- Verify credentials in `.env` file
- Check if selectors are correct for login form
- Ensure GoDartsPro account is active
- Try running with `headless: false` to see browser

#### 2. Elements Not Found

**Problem:** `Timeout waiting for selector`

**Solutions:**
- Update selectors in `settings.yaml` to match actual site
- Increase `browser.timeout` in config
- Increase `rate_limit_seconds` to allow more time for page loads
- Run with `headless: false` and `log_level: DEBUG`

#### 3. Empty or Partial Data

**Problem:** Scraper runs but extracts incomplete data

**Solutions:**
- Verify selectors match actual HTML structure
- Check if site requires JavaScript rendering (Playwright handles this)
- Increase timeouts for dynamic content
- Implement custom extraction logic for specific stats

#### 4. State File Corruption

**Problem:** State file becomes corrupted

**Solutions:**
```python
# Reset state
from dart_coach.scrapers import ScraperStateManager
state = ScraperStateManager('data/godartspro/godartspro_scraper_state.json')
state.reset_state()
```

### Debug Mode

Run with debug logging to see detailed execution:

```python
async with GoDartsProScraper(
    username=username,
    password=password,
    config=config,
    data_dir=data_dir,
    log_level='DEBUG'  # Enable debug logging
) as scraper:
    await scraper.scrape_all()
```

### Visual Debugging

Run browser in non-headless mode to watch execution:

```yaml
# In settings.yaml
godartspro:
  browser:
    headless: false  # Set to false to see browser
```

## Customization

### Adding Custom Metrics

To extract additional metrics not currently captured:

1. Update the schema in `schemas/godartspro_schema.json`
2. Modify extraction methods in `godartspro_scraper.py`:
   - `_extract_individual_session_stats()`
   - `_extract_averaged_statistics()`
3. Add selectors to `settings.yaml` if needed

### Custom Extraction Logic

Example: Extract a specific stat by label

```python
async def _extract_stat_by_label(self, label: str) -> Optional[float]:
    """Extract a statistic by its label."""
    try:
        # Find element containing label
        element = await self.page.query_selector(f"text={label}")
        if element:
            # Find adjacent value element (customize based on HTML structure)
            value_element = await element.query_selector("xpath=following-sibling::*[1]")
            if value_element:
                value_text = await value_element.text_content()
                # Parse numeric value
                return float(value_text.strip())
    except Exception as e:
        self.logger.debug(f"Could not extract stat '{label}': {e}")
    return None
```

## Best Practices

### 1. Rate Limiting
- Keep `rate_limit_seconds` at 2.0 or higher
- Don't scrape too frequently (once per day is usually sufficient)

### 2. Error Handling
- Always use async context manager (`async with`)
- Check scrape statistics after each run
- Monitor state file for failures

### 3. Data Storage
- Organize data by date: `data/godartspro/2026-01-17.json`
- Keep historical data for trend analysis
- Backup state file periodically

### 4. Selector Maintenance
- Document selector updates in version control
- Test selectors after site updates
- Use multiple selector options (e.g., class and text)

### 5. Scheduling
- Use cron or systemd timers for automated scraping
- Run during off-peak hours
- Add random delays between scheduled runs

## Integration with Analysis Pipeline

The scraped data is designed for LLM analysis. Example integration:

```python
import json
from pathlib import Path

# Load scraped data
with open('data/godartspro/godartspro_data_20260117.json') as f:
    sessions = json.load(f)

# Prepare for LLM analysis
prompt = f"""
Analyze the following dart training sessions and provide insights:

Total sessions: {len(sessions)}
Date range: {sessions[0]['timestamp']} to {sessions[-1]['timestamp']}

Session data:
{json.dumps(sessions, indent=2)}

Please provide:
1. Performance trends
2. Areas for improvement
3. Strengths and weaknesses
4. Recommendations for next week
"""

# Send to LLM for analysis
# (use Ollama, OpenAI, or other LLM)
```

## Support

For issues, questions, or contributions:
- Check the troubleshooting section above
- Review example scripts in `examples/`
- Consult the code documentation in `scrapers/godartspro_scraper.py`

## License

Part of the Dart Performance Coach project.
