# Scolia Scraper - Quick Start Guide

Get up and running with the Scolia comprehensive scraper in 5 minutes!

## Prerequisites

- Python 3.9+
- Chrome/Chromium browser
- Scolia account

## 5-Minute Setup

### Step 1: Clone and Setup (2 minutes)

```bash
cd Automation-Projects
./examples/setup_scolia_scraper.sh
```

### Step 2: Set Credentials (1 minute)

```bash
export SCOLIA_USERNAME="your_email@example.com"
export SCOLIA_PASSWORD="your_password"
```

Or create a `.env` file:

```bash
cat > .env << EOF
SCOLIA_USERNAME=your_email@example.com
SCOLIA_PASSWORD=your_password
EOF
```

### Step 3: Run First Scrape (2 minutes)

```bash
# Activate virtual environment
source venv/bin/activate

# Run scraper
python examples/run_scolia_scraper.py --game-types x01 cricket
```

## What You'll Get

After running, you'll find:

```
data/scolia/
├── scolia_data_20260117_103000.json          # Complete hierarchical data
├── scolia_data_20260117_103000_summary.csv   # Summary statistics
├── scolia_data_20260117_103000_x01_matches.csv
├── scolia_data_20260117_103000_x01_turns.csv
├── scolia_data_20260117_103000_cricket_matches.csv
└── scolia_data_20260117_103000_cricket_turns.csv
```

## Next Steps

### Weekly Updates

For incremental scraping (only new matches):

```bash
python examples/run_scolia_scraper.py --incremental
```

### LLM Analysis

Feed the JSON data to your local LLM:

```python
import json
import ollama

with open('data/scolia/scolia_data_latest.json') as f:
    data = json.load(f)

response = ollama.generate(
    model='llama2',
    prompt=f"Analyze this darts performance data: {json.dumps(data)}"
)
print(response['response'])
```

## Common Commands

```bash
# Scrape all game types (first time)
python examples/run_scolia_scraper.py --all

# Scrape only X01
python examples/run_scolia_scraper.py --game-types x01

# JSON only
python examples/run_scolia_scraper.py --format json

# CSV only
python examples/run_scolia_scraper.py --format csv

# Debug mode (show browser)
python examples/run_scolia_scraper.py --no-headless --log-level DEBUG
```

## Troubleshooting

### Authentication Fails

- Double-check credentials
- Try with `--no-headless` to see what's happening

### Slow Performance

- Use `--incremental` for updates
- Limit game types: `--game-types x01`

### Missing Data

- Check `logs/scolia_scraper.log`
- Run with `--log-level DEBUG`

## Get More Help

See the complete guide: `docs/SCOLIA_SCRAPER_GUIDE.md`

---

**Ready to improve your darts game! 🎯**
