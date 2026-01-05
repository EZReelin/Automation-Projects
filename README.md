# 🎯 Dart Performance Coach System

A comprehensive dart performance tracking and coaching system that integrates multiple data sources to provide weekly analytical insights.

## Overview

This system functions as a professional statistician and coach by synthesizing:
- **Quantitative performance data** from practice and competition
- **Qualitative biomechanical insights** from video analysis
- **Contextual practice observations** from voice notes

The result is actionable weekly feedback that drives measurable improvement in dart performance.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DATA COLLECTION LAYER                            │
├─────────────────┬─────────────────┬─────────────────┬──────────────────┤
│  Scolia Scraper │ Dart Connect    │ Biomechanics    │ Voice            │
│  (Practice)     │ Scraper         │ (MediaPipe +    │ Observations     │
│                 │ (Competition)   │ OBSBOT Camera)  │ (Whisper)        │
└────────┬────────┴────────┬────────┴────────┬────────┴────────┬─────────┘
         │                 │                 │                 │
         ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        DATA PIPELINE LAYER                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   JSON      │  │   Schema    │  │   Data      │  │   Cross-    │   │
│  │   Storage   │  │   Validator │  │   Loader    │  │   Reference │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
│                              │                                          │
│                    ┌─────────▼─────────┐                               │
│                    │   Aggregator      │                               │
│                    └─────────┬─────────┘                               │
└──────────────────────────────┼──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         ANALYSIS LAYER                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      Ollama LLM                                  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │   │
│  │  │ Weekly   │ │ Trend    │ │ Bio-     │ │ Mental   │           │   │
│  │  │ Summary  │ │ Analysis │ │ mechanics│ │ Game     │           │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                    ┌─────────▼─────────┐                               │
│                    │ Report Generator  │                               │
│                    └─────────┬─────────┘                               │
└──────────────────────────────┼──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         OUTPUT LAYER                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │
│  │  JSON Report    │  │  Markdown       │  │  Calendar       │        │
│  │                 │  │  Report         │  │  Event          │        │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘        │
└─────────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Data Collection

| Component | Source | Data Type |
|-----------|--------|-----------|
| Scolia Scraper | Scolia Web Client | Practice sessions, CPU matches, online matches |
| Dart Connect Scraper | Dart Connect | League matches, bar matches, tournament data |
| Biomechanics | OBSBOT + MediaPipe | Throwing form, body positioning, movement |
| Voice | Microphone + Whisper | Verbal observations, technique notes |

### 2. Data Schemas

All data is stored in structured JSON files with consistent schemas:
- `scolia_schema.json` - Practice session data
- `dart_connect_schema.json` - Competition match data
- `biomechanics_schema.json` - Throw analysis data
- `voice_observation_schema.json` - Voice observation data
- `weekly_analysis_schema.json` - Final report format

### 3. Analysis

The Ollama-powered analysis generates:
- Executive summaries
- Key findings (strengths, weaknesses, trends)
- Practice vs. competition gap analysis
- Biomechanical form assessment
- Mental game insights
- Specific drill recommendations
- Practice plans and goals

### 4. Automation

- **Scheduler**: Runs automatically every Sunday at 6 PM
- **Calendar Integration**: Creates Google Calendar or iCal events
- **Full Pipeline**: Scrape → Aggregate → Analyze → Report → Schedule

## Quick Start

```bash
# Navigate to project
cd dart_coach

# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp config/.env.example config/.env
# Edit config/.env with your credentials

# Run weekly analysis
python -m dart_coach.main weekly

# Or run individual components
python -m dart_coach.main scrape --all
python -m dart_coach.main report
python -m dart_coach.main schedule
```

## Configuration

Edit `config/settings.yaml` to customize:
- Scraper URLs and credentials
- Camera and MediaPipe settings
- Ollama model and parameters
- Analysis schedule
- Calendar integration

## Data Context

The system distinguishes between:

| Context | Source | Description |
|---------|--------|-------------|
| **Practice** | Scolia | Controlled environment, solo practice, CPU opponents |
| **Casual Competition** | Scolia | Online matches against other players |
| **Competition** | Dart Connect | Real league/bar matches against human opponents |

This distinction is critical for analysis - practice performance under controlled conditions often differs significantly from competitive performance under pressure.

## Report Output

Weekly reports include:
1. 📊 Executive summary
2. 🎯 Key performance metrics
3. 📈 Trend analysis
4. ⚖️ Practice vs. competition comparison
5. 🏋️ Biomechanics assessment
6. 🧠 Mental game analysis
7. 📝 Specific recommendations
8. 📅 Practice plan for next week
9. 🎯 SMART goals

## Requirements

- Python 3.9+
- Ollama (with llama3.1:8b or similar model)
- Chrome/Chromium (for web scraping)
- OBSBOT Tiny Lite 2 (optional, for biomechanics)
- Microphone (optional, for voice observations)

## License

MIT License

---

For detailed documentation, see [dart_coach/README.md](dart_coach/README.md)
