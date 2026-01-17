# Scolia Comprehensive Scraper - Examples

This directory contains example scripts and documentation for using the Scolia comprehensive scraper.

## Files

### Scripts

- **`run_scolia_scraper.py`** - Main CLI script for running the scraper
- **`setup_scolia_scraper.sh`** - Setup script for initial installation

### Configuration

Configuration files are located in `dart_coach/config/`:
- `scolia_scraper_config.yaml` - Main configuration file
- `scolia_scraper_config.example.yaml` - Example configuration template

## Quick Start

### 1. Initial Setup

```bash
# Run setup script
./setup_scolia_scraper.sh

# Set credentials
export SCOLIA_USERNAME="your_email@example.com"
export SCOLIA_PASSWORD="your_password"
```

### 2. First Run

```bash
# Activate virtual environment
source venv/bin/activate

# Run scraper for all game types
python run_scolia_scraper.py --all
```

### 3. Weekly Updates

```bash
# Incremental scraping (only new matches)
python run_scolia_scraper.py --incremental
```

## Common Use Cases

### Scrape Specific Game Types

```bash
# Only X01 games
python run_scolia_scraper.py --game-types x01

# X01 and Cricket
python run_scolia_scraper.py --game-types x01 cricket

# All game types
python run_scolia_scraper.py --game-types x01 cricket around_the_world bobs_27 shanghai
```

### Export Formats

```bash
# JSON only
python run_scolia_scraper.py --format json

# CSV only
python run_scolia_scraper.py --format csv

# Both (default)
python run_scolia_scraper.py --format both
```

### Debugging

```bash
# Show browser window and debug output
python run_scolia_scraper.py --no-headless --log-level DEBUG

# Debug with specific game type
python run_scolia_scraper.py --no-headless --log-level DEBUG --game-types x01
```

### Custom Output Directory

```bash
python run_scolia_scraper.py --output-dir ./my_data/scolia
```

## Output Structure

After running, you'll find data in the output directory:

```
data/scolia/
├── scolia_data_20260117_103000.json          # Complete hierarchical data
├── scolia_data_20260117_103000_summary.csv   # Summary statistics
├── scolia_data_20260117_103000_x01_matches.csv
├── scolia_data_20260117_103000_x01_turns.csv
├── scolia_data_20260117_103000_cricket_matches.csv
├── scolia_data_20260117_103000_cricket_turns.csv
└── scraper_state.json                         # State tracking for incremental scraping
```

## Using the Data

### Load JSON Data

```python
import json

with open('data/scolia/scolia_data_20260117_103000.json') as f:
    data = json.load(f)

# Access X01 statistics
x01_stats = data['game_types']['x01']
print(f"Total matches: {len(x01_stats['match_history'])}")

# Iterate through matches
for match in x01_stats['match_history']:
    print(f"Match {match['match_id']}: {match['result']}")
```

### Load CSV Data

```python
import pandas as pd

# Load match data
matches = pd.read_csv('data/scolia/scolia_data_20260117_103000_x01_matches.csv')
print(matches.head())

# Load turn-by-turn data
turns = pd.read_csv('data/scolia/scolia_data_20260117_103000_x01_turns.csv')

# Calculate average score per turn
avg_score = turns.groupby('match_id')['turn_total'].mean()
print(avg_score)
```

### LLM Analysis Example

```python
import json
import ollama

# Load scraped data
with open('data/scolia/scolia_data_latest.json') as f:
    stats_data = json.load(f)

# Extract X01 performance
x01_data = stats_data['game_types']['x01']

# Create analysis prompt
prompt = f"""
Analyze this darts performance data from X01 games:

Overall Stats: {x01_data['stats_page_data']}

Recent Matches: {len(x01_data['match_history'])} matches

Please provide:
1. Performance trends
2. Strengths and weaknesses
3. Specific areas for improvement
4. Recommendations for practice
"""

# Get LLM analysis
response = ollama.generate(model='llama2', prompt=prompt)
print(response['response'])
```

## Automation

### Weekly Cron Job

Add to crontab for automatic weekly scraping:

```bash
# Edit crontab
crontab -e

# Add line (runs every Monday at 9 AM)
0 9 * * MON cd /path/to/Automation-Projects && source venv/bin/activate && python examples/run_scolia_scraper.py --incremental
```

### Shell Script Wrapper

Create `run_weekly_scrape.sh`:

```bash
#!/bin/bash
cd /path/to/Automation-Projects
source venv/bin/activate

# Load credentials
export SCOLIA_USERNAME="your_email@example.com"
export SCOLIA_PASSWORD="your_password"

# Run scraper
python examples/run_scolia_scraper.py --incremental --format both

# Optional: Analyze with LLM
# python analyze_performance.py
```

Make it executable:
```bash
chmod +x run_weekly_scrape.sh
```

## Troubleshooting

### Common Issues

**Authentication Fails**
- Verify credentials are correct
- Check environment variables: `echo $SCOLIA_USERNAME`
- Try with `--no-headless` to see the browser

**No Data Extracted**
- Check logs: `cat logs/scolia_scraper.log`
- Run with `--log-level DEBUG`
- Verify Scolia website is accessible

**Slow Performance**
- Use `--incremental` mode for updates
- Limit game types: `--game-types x01`
- Check internet connection

**ChromeDriver Errors**
```bash
# Update ChromeDriver
pip install --upgrade webdriver-manager
```

### Getting Help

1. Check the complete guide: `docs/SCOLIA_SCRAPER_GUIDE.md`
2. Review logs in `logs/scolia_scraper.log`
3. Run with `--log-level DEBUG` for detailed output
4. Check if screenshots were captured: `logs/screenshots/`

## Documentation

- **Quick Start**: `docs/SCOLIA_QUICK_START.md`
- **Complete Guide**: `docs/SCOLIA_SCRAPER_GUIDE.md`
- **Schema**: `dart_coach/schemas/scolia_comprehensive_schema.json`

## Advanced Usage

### Python API

```python
from pathlib import Path
from dart_coach.scrapers import ScoliaComprehensiveScraper

# Initialize
scraper = ScoliaComprehensiveScraper(
    data_dir=Path("./data/scolia"),
    headless=True,
    log_level="INFO"
)

# Authenticate
if scraper.authenticate():
    # Extract all statistics
    stats = scraper.extract_all_statistics(game_types=['x01', 'cricket'])

    # Export data
    scraper.export_to_json(stats, "my_stats.json")
    scraper.export_to_csv(stats, "my_stats")

# Cleanup
del scraper
```

### Custom Processing

```python
# Load and process data
import json

with open('data/scolia/scolia_data_latest.json') as f:
    data = json.load(f)

# Find best scoring leg
best_avg = 0
best_leg = None

for match in data['game_types']['x01']['match_history']:
    for leg in match.get('legs', []):
        turns = leg.get('turns', [])
        if turns:
            avg = sum(t['total_score'] for t in turns) / len(turns)
            if avg > best_avg:
                best_avg = avg
                best_leg = (match['match_id'], leg['leg_number'])

print(f"Best leg: Match {best_leg[0]}, Leg {best_leg[1]} with {best_avg:.1f} average")
```

## License

See LICENSE file in project root.

---

**Happy scraping! 🎯**
