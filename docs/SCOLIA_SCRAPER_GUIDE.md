# Scolia Comprehensive Scraper - Complete Guide

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Authentication](#authentication)
6. [Usage](#usage)
7. [Data Structure](#data-structure)
8. [Incremental Scraping](#incremental-scraping)
9. [Troubleshooting](#troubleshooting)
10. [Advanced Usage](#advanced-usage)
11. [API Reference](#api-reference)

---

## Overview

The Scolia Comprehensive Scraper is a production-ready web scraper designed to extract complete darts statistics from the Scolia Web Client platform for weekly performance assessments. It captures data from high-level statistics pages down to granular turn-by-turn throw analysis.

### What It Extracts

- **Statistics Pages**: All metrics from main stats pages for each game type
- **Charts**: Numerical data from visualizations (not just screenshots)
- **Match History**: Complete match listings with incremental tracking
- **Match Details**: Comprehensive data from all tabs (Throw Analysis, Scoring, Score History/Marks)
- **Leg-Level Data**: Individual leg breakdowns
- **Turn-by-Turn Analysis**: Detailed throw history for every turn
- **Timeline Analysis**: X01-specific timeline data
- **Scoring Analysis**: X01-specific scoring breakdown

### Game Types Supported

- **X01** (301, 501, 701, etc.)
- **Cricket**
- **Around the World**
- **Bob's 27**
- **Shanghai**

---

## Features

### Core Features

✅ **Comprehensive Data Extraction**
- Extracts all statistics from main stats pages
- Captures numerical chart data (not images)
- Navigates through match history automatically
- Extracts data from all match tabs
- Captures turn-by-turn throw analysis

✅ **Incremental Scraping**
- Tracks last processed match per game type
- Only scrapes new matches on subsequent runs
- Maintains state between sessions
- Reduces scraping time and server load

✅ **Multi-Format Export**
- JSON output with hierarchical structure
- CSV export with separate files for different data types
- Configurable output formats

✅ **Robust Error Handling**
- Retry logic for transient failures
- Rate limiting to avoid server overload
- Detailed logging with multiple levels
- Screenshot capture on errors

✅ **Production-Ready**
- Configurable via YAML files
- Environment variable support for credentials
- Headless browser mode
- Comprehensive logging

---

## Installation

### Prerequisites

- Python 3.9 or higher
- Chrome or Chromium browser
- Scolia Web Client account

### Quick Setup

```bash
# Navigate to project directory
cd Automation-Projects

# Run setup script
./examples/setup_scolia_scraper.sh
```

### Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install package
cd dart_coach
pip install -e .

# Create directories
mkdir -p data/scolia logs logs/screenshots
```

---

## Configuration

### Using Configuration File

Copy the example configuration:

```bash
cp dart_coach/config/scolia_scraper_config.example.yaml \
   dart_coach/config/scolia_scraper_config.yaml
```

Edit `scolia_scraper_config.yaml` to customize:

```yaml
scolia:
  base_url: "https://web.scolia.app"
  headless: true

scraping:
  game_types:
    - x01
    - cricket
  incremental: true
  extract_legs: true
  extract_turns: true

export:
  format: "both"  # json, csv, or both
  output_dir: "./data/scolia"
```

### Configuration Options

#### Scolia Settings

| Option | Description | Default |
|--------|-------------|---------|
| `base_url` | Scolia web app URL | `https://web.scolia.app` |
| `headless` | Run browser without GUI | `true` |
| `timeout` | Page load timeout (seconds) | `20` |

#### Scraping Settings

| Option | Description | Default |
|--------|-------------|---------|
| `game_types` | List of game types to scrape | `[x01, cricket]` |
| `incremental` | Only scrape new matches | `true` |
| `extract_legs` | Extract leg-level data | `true` |
| `extract_turns` | Extract turn-by-turn data | `true` |
| `extract_charts` | Extract chart data | `true` |

#### Rate Limiting

| Option | Description | Default |
|--------|-------------|---------|
| `between_pages` | Delay between pages (seconds) | `1.0` |
| `between_matches` | Delay between matches (seconds) | `0.5` |
| `between_game_types` | Delay between game types (seconds) | `2.0` |

---

## Authentication

### Method 1: Environment Variables (Recommended)

Set your Scolia credentials as environment variables:

```bash
export SCOLIA_USERNAME="your_email@example.com"
export SCOLIA_PASSWORD="your_password"
```

To make them permanent, add to your `.bashrc` or `.bash_profile`:

```bash
echo 'export SCOLIA_USERNAME="your_email@example.com"' >> ~/.bashrc
echo 'export SCOLIA_PASSWORD="your_password"' >> ~/.bashrc
source ~/.bashrc
```

### Method 2: .env File

Create a `.env` file in the project root:

```
SCOLIA_USERNAME=your_email@example.com
SCOLIA_PASSWORD=your_password
```

### Method 3: Configuration File (Not Recommended)

You can set credentials in the config file, but this is less secure:

```yaml
scolia:
  username: "your_email@example.com"
  password: "your_password"
```

**Warning**: Never commit credentials to version control!

---

## Usage

### Command Line Interface

#### First Time Setup (Scrape All Game Types)

```bash
python examples/run_scolia_scraper.py --all
```

#### Incremental Scraping (Weekly Updates)

```bash
python examples/run_scolia_scraper.py --incremental
```

#### Scrape Specific Game Types

```bash
python examples/run_scolia_scraper.py --game-types x01 cricket
```

#### Export to JSON Only

```bash
python examples/run_scolia_scraper.py --format json
```

#### Export to CSV Only

```bash
python examples/run_scolia_scraper.py --format csv
```

#### Debug Mode (Show Browser)

```bash
python examples/run_scolia_scraper.py --no-headless --log-level DEBUG
```

### Python API

```python
from pathlib import Path
from dart_coach.scrapers.scolia_comprehensive_scraper import ScoliaComprehensiveScraper

# Initialize scraper
scraper = ScoliaComprehensiveScraper(
    data_dir=Path("./data/scolia"),
    headless=True,
    log_level="INFO"
)

# Authenticate
scraper.authenticate()

# Run full scrape
json_path, csv_paths = scraper.run_full_scrape(
    game_types=['x01', 'cricket'],
    export_format='both'
)

print(f"Data saved to: {json_path}")
```

### Advanced Python Usage

```python
# Extract statistics for specific game types
stats = scraper.extract_all_statistics(game_types=['x01'])

# Extract just match history
matches = scraper._extract_match_history('x01')

# Export to custom location
scraper.export_to_json(stats, "my_custom_data.json")
csv_files = scraper.export_to_csv(stats, "my_custom_data")
```

---

## Data Structure

### JSON Output Structure

```json
{
  "scrape_timestamp": "2026-01-17T10:30:00Z",
  "game_types": {
    "x01": {
      "game_type": "x01",
      "stats_page_data": {
        "Average": 85.5,
        "Total Matches": 150,
        "Win Rate": 65.5
      },
      "charts": [
        {
          "chart_id": "performance_over_time",
          "type": "line",
          "data": { ... }
        }
      ],
      "match_history": [
        {
          "match_id": "match_12345",
          "date": "2026-01-15",
          "opponent": "Player123",
          "result": "Won",
          "score": "3-2",
          "tabs": {
            "throw_analysis": { ... },
            "scoring": { ... },
            "score_history": { ... }
          },
          "timeline_analysis": { ... },
          "scoring_analysis": { ... },
          "legs": [
            {
              "leg_number": 1,
              "turns": [
                {
                  "turn_number": 1,
                  "throws": [
                    {
                      "target": "T20",
                      "score": 60,
                      "multiplier": "3"
                    }
                  ],
                  "total_score": 140,
                  "remaining": 361
                }
              ]
            }
          ]
        }
      ]
    }
  }
}
```

### CSV Output Files

The scraper generates multiple CSV files:

1. **`{filename}_summary.csv`**
   - Game Type | Metric | Value
   - Overall statistics per game type

2. **`{filename}_{game_type}_matches.csv`**
   - match_id | date | opponent | result | score | num_legs
   - One file per game type

3. **`{filename}_{game_type}_turns.csv`**
   - match_id | leg | turn | throw_num | target | score | multiplier | turn_total | remaining
   - Detailed turn-by-turn data

---

## Incremental Scraping

The scraper maintains state to track processed matches, enabling efficient incremental updates.

### How It Works

1. On first run, scrapes all available matches
2. Saves the last processed match ID per game type in `scraper_state.json`
3. On subsequent runs, only processes new matches
4. Updates state after each successful scrape

### State File Location

`data/scolia/scraper_state.json`

```json
{
  "last_scrape_time": "2026-01-17T10:30:00Z",
  "last_match_ids": {
    "x01": "match_12345",
    "cricket": "match_67890"
  },
  "total_matches_scraped": 75
}
```

### Resetting State

To force a full re-scrape, delete the state file:

```bash
rm data/scolia/scraper_state.json
```

---

## Troubleshooting

### Common Issues

#### 1. Authentication Fails

**Symptoms**: Login page doesn't redirect, error message about credentials

**Solutions**:
- Verify credentials are correct
- Check environment variables are set: `echo $SCOLIA_USERNAME`
- Try running with `--no-headless` to see the browser
- Check if Scolia website structure has changed

#### 2. Elements Not Found

**Symptoms**: `NoSuchElementException`, missing data in output

**Solutions**:
- Run with `--no-headless --log-level DEBUG` to inspect
- Scolia website structure may have changed - selectors need updating
- Increase timeout in config: `timeout: 30`
- Check if page requires scrolling to load content

#### 3. Slow Scraping

**Symptoms**: Scraping takes very long

**Solutions**:
- Use incremental mode: `--incremental`
- Reduce game types: `--game-types x01`
- Increase rate limits may help with timeouts
- Check internet connection speed

#### 4. Chrome Driver Issues

**Symptoms**: Browser won't start, driver errors

**Solutions**:
```bash
# Update Chrome driver
pip install --upgrade webdriver-manager

# Or manually install ChromeDriver matching your Chrome version
# Download from: https://chromedriver.chromium.org/
```

#### 5. Memory Issues

**Symptoms**: Out of memory errors, system slowdown

**Solutions**:
- Process fewer matches: set `max_matches_per_type` in config
- Run in headless mode: `headless: true`
- Close the scraper between runs: cleans up browser instances

### Debug Mode

Run with maximum verbosity:

```bash
python examples/run_scolia_scraper.py \
  --no-headless \
  --log-level DEBUG \
  --game-types x01
```

This will:
- Show the browser window
- Print detailed debug logs
- Process only X01 (faster for testing)

### Getting Help

1. Check logs in `logs/scolia_scraper.log`
2. Review screenshots in `logs/screenshots/` (if errors occurred)
3. Run with `--log-level DEBUG` for more details
4. Check Scolia website hasn't changed structure

---

## Advanced Usage

### Custom Selectors

If Scolia website structure changes, update selectors in `scolia_comprehensive_scraper.py`:

```python
SELECTORS = {
    'stats_page': {
        'stat_cards': '.stat-card',  # Update this
        'charts': '.chart-container'  # And this
    },
    # ... more selectors
}
```

### Processing Specific Date Ranges

```python
from datetime import datetime, timedelta

scraper = ScoliaComprehensiveScraper(data_dir=Path("./data"))
scraper.authenticate()

# Process last week only
start_date = datetime.now() - timedelta(days=7)
end_date = datetime.now()

matches = scraper._extract_match_history('x01')
# Filter by date and process...
```

### Custom Data Processing

```python
import json

# Load scraped data
with open('data/scolia/scolia_data_20260117_103000.json') as f:
    data = json.load(f)

# Process X01 matches
for match in data['game_types']['x01']['match_history']:
    if match['result'] == 'Won':
        print(f"Won match {match['match_id']} on {match['date']}")

        # Analyze leg performance
        for leg in match['legs']:
            avg_score = sum(t['total_score'] for t in leg['turns']) / len(leg['turns'])
            print(f"  Leg {leg['leg_number']}: {avg_score:.1f} average")
```

### Integration with LLM

```python
import json
import ollama  # or your LLM library

# Load data
with open('data/scolia/scolia_data_latest.json') as f:
    stats_data = json.load(f)

# Format for LLM
prompt = f"""
Analyze this darts performance data and provide insights:

{json.dumps(stats_data, indent=2)}

Please identify:
1. Performance trends
2. Strengths and weaknesses
3. Areas for improvement
4. Comparison with previous weeks
"""

# Send to LLM
response = ollama.generate(model='llama2', prompt=prompt)
print(response['response'])
```

---

## API Reference

### ScoliaComprehensiveScraper

#### Constructor

```python
ScoliaComprehensiveScraper(
    data_dir: Path,
    base_url: str = "https://web.scolia.app",
    headless: bool = True,
    **kwargs
)
```

**Parameters:**
- `data_dir`: Directory to store scraped data
- `base_url`: Scolia web app URL
- `headless`: Run browser in headless mode
- `**kwargs`: Additional arguments for BaseScraper

#### Methods

##### authenticate()

```python
def authenticate(
    username: str = None,
    password: str = None
) -> bool
```

Authenticate with Scolia. Returns `True` if successful.

##### extract_all_statistics()

```python
def extract_all_statistics(
    game_types: List[str] = None
) -> Dict[str, Any]
```

Extract comprehensive statistics for specified game types.

##### run_full_scrape()

```python
def run_full_scrape(
    game_types: List[str] = None,
    export_format: str = 'both'
) -> Tuple[Path, List[Path]]
```

Run complete scraping session. Returns tuple of (json_path, csv_paths).

##### export_to_json()

```python
def export_to_json(
    data: Dict[str, Any],
    filename: str
) -> Path
```

Export data to JSON file.

##### export_to_csv()

```python
def export_to_csv(
    data: Dict[str, Any],
    base_filename: str
) -> List[Path]
```

Export data to CSV files.

---

## Best Practices

### Weekly Performance Assessment Workflow

1. **Week 1 (Setup)**
   ```bash
   python examples/run_scolia_scraper.py --all --format both
   ```

2. **Subsequent Weeks (Incremental)**
   ```bash
   python examples/run_scolia_scraper.py --incremental
   ```

3. **Analyze with LLM**
   - Feed JSON data to your local LLM
   - Compare week-over-week performance
   - Identify improvement areas

4. **Automate** (Optional)
   ```bash
   # Add to crontab for weekly runs
   0 9 * * MON cd /path/to/project && ./run_weekly_scrape.sh
   ```

### Data Management

- Keep raw JSON files for complete data
- Use CSV files for spreadsheet analysis
- Archive old data periodically
- Back up state file to preserve incremental tracking

### Performance Optimization

- Use incremental mode for regular updates
- Limit game types to what you actively play
- Set reasonable rate limits (don't be too aggressive)
- Run during off-peak hours to avoid server load

---

## Schema Reference

See `dart_coach/schemas/scolia_comprehensive_schema.json` for the complete JSON schema definition.

---

## Support and Contributing

### Issues

Report issues or request features in the project issue tracker.

### Updating Selectors

If Scolia updates their website:

1. Run with `--no-headless --log-level DEBUG`
2. Inspect the page structure
3. Update selectors in `SELECTORS` dictionary
4. Test with a small scrape
5. Submit improvements

### License

See LICENSE file in project root.

---

**Happy Darting! 🎯**
