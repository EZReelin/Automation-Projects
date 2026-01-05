# 🎯 Dart Performance Coach

A comprehensive dart performance tracking and coaching system that integrates multiple data sources to provide weekly analytical insights. The system functions as a professional statistician and coach by synthesizing quantitative performance data, qualitative biomechanical insights, and contextual practice observations into actionable weekly feedback.

## 🌟 Features

### Data Collection
- **Scolia Web Client Scraper**: Captures practice session data, CPU matches, and online matches
- **Dart Connect Scraper**: Captures competitive league and bar match data
- **Biomechanical Analysis**: MediaPipe-powered pose estimation for throw analysis
- **Voice Observations**: Real-time verbal notes with timestamp synchronization

### Analysis
- **Unified Data Pipeline**: Consolidates all sources into structured JSON
- **Ollama Integration**: AI-powered performance analysis and coaching recommendations
- **Weekly Reports**: Comprehensive analysis comparing practice vs competition

### Automation
- **Sunday Scheduling**: Automated weekly analysis runs
- **Calendar Integration**: Google Calendar or iCal event creation

## 📁 Project Structure

```
dart_coach/
├── config/
│   ├── settings.yaml          # Main configuration
│   └── .env.example           # Environment variables template
├── schemas/
│   ├── scolia_schema.json     # Practice data schema
│   ├── dart_connect_schema.json # Competition data schema
│   ├── biomechanics_schema.json # Biomechanics data schema
│   ├── voice_observation_schema.json # Voice observation schema
│   └── weekly_analysis_schema.json # Report schema
├── scrapers/
│   ├── base_scraper.py        # Abstract base scraper
│   ├── scolia_scraper.py      # Scolia Web Client scraper
│   └── dart_connect_scraper.py # Dart Connect scraper
├── biomechanics/
│   ├── camera_handler.py      # OBSBOT camera integration
│   ├── pose_processor.py      # MediaPipe pose estimation
│   └── throw_analyzer.py      # Complete throw analysis
├── voice/
│   ├── voice_recorder.py      # Audio recording
│   ├── transcriber.py         # Whisper transcription
│   └── observation_processor.py # Observation processing
├── data_pipeline/
│   ├── loader.py              # Data loading utilities
│   ├── validator.py           # Schema validation
│   └── aggregator.py          # Data aggregation
├── analysis/
│   ├── prompts.py             # Ollama prompt templates
│   ├── ollama_analyzer.py     # Ollama integration
│   └── report_generator.py    # Report generation
├── calendar/
│   ├── google_calendar.py     # Google Calendar integration
│   └── ical_generator.py      # iCal file generation
├── data/                      # Data storage (gitignored)
│   ├── scolia/
│   ├── dart_connect/
│   ├── biomechanics/
│   ├── voice/
│   ├── aggregated/
│   └── reports/
├── main.py                    # Main orchestrator and CLI
├── scheduler.py               # Automated scheduling
├── requirements.txt           # Dependencies
└── setup.py                   # Package setup
```

## 🚀 Installation

### Prerequisites
- Python 3.9+
- Ollama (for AI analysis)
- Chrome/Chromium (for web scraping)
- OBSBOT Tiny Lite 2 (optional, for biomechanics)

### Install Dependencies

```bash
cd dart_coach
pip install -r requirements.txt
```

### Install as Package (Optional)

```bash
pip install -e .
```

### Setup Configuration

1. Copy the environment template:
```bash
cp config/.env.example config/.env
```

2. Edit `config/.env` with your credentials:
```env
SCOLIA_USERNAME=your_username
SCOLIA_PASSWORD=your_password
DART_CONNECT_USERNAME=your_username
DART_CONNECT_PASSWORD=your_password
```

3. For Google Calendar integration, follow [Google Calendar API setup](https://developers.google.com/calendar/api/quickstart/python) and place `credentials.json` in your config directory.

### Start Ollama

Make sure Ollama is running with a suitable model:

```bash
ollama pull llama3.1:8b
ollama serve
```

## 📖 Usage

### Command Line Interface

```bash
# Run complete weekly analysis
dart-coach weekly

# Scrape data only
dart-coach scrape --all
dart-coach scrape --scolia --days 7
dart-coach scrape --dart-connect

# Generate report from existing data
dart-coach report

# Schedule calendar event
dart-coach schedule
dart-coach schedule --ical  # Generate .ics file instead

# Run biomechanical analysis
dart-coach biomechanics --duration 300 --display

# Record voice observations
dart-coach voice --duration 1800
```

### Python API

```python
from dart_coach.main import DartCoach

# Initialize
coach = DartCoach()

# Run complete workflow
results = coach.run_weekly_workflow(
    scrape=True,
    schedule=True,
    use_google_calendar=True
)

# Or run individual steps
coach.scrape_scolia(days=7)
coach.scrape_dart_connect(days=7)
aggregated = coach.aggregate_weekly_data()
report = coach.generate_weekly_report(aggregated)
coach.schedule_calendar_event(report)
```

### Automated Scheduling

Run the scheduler to automatically analyze performance every Sunday:

```bash
python -m dart_coach.scheduler --day sun --hour 18 --minute 0
```

Or use cron:
```bash
0 18 * * 0 cd /path/to/dart_coach && python -m dart_coach.main weekly
```

### Biomechanical Analysis

```python
from dart_coach.biomechanics import ThrowAnalyzer

# Live analysis
with ThrowAnalyzer(data_dir="./data/biomechanics") as analyzer:
    analyzer.start_session(record_video=True)
    results = analyzer.process_live(duration_seconds=300, display=True)
    analyzer.stop_session()

# Analyze existing video
analyzer = ThrowAnalyzer(data_dir="./data/biomechanics")
results = analyzer.process_video_file("practice_video.mp4", display=True)
```

### Voice Observations

```python
from dart_coach.voice import ObservationProcessor

# Live recording
with ObservationProcessor(data_dir="./data/voice") as processor:
    processor.start_session()
    # ... practice and speak observations ...
    results = processor.stop_session()

# Process existing recording
processor = ObservationProcessor(data_dir="./data/voice")
results = processor.process_existing_recording("practice_notes.wav")
```

## 📊 Data Schemas

### Practice Data (Scolia)
- Session metadata and timestamps
- Game format (501, cricket, etc.)
- Performance metrics (average, checkout %, 180s)
- Match results for CPU/online matches
- Individual throw data when available

### Competition Data (Dart Connect)
- Match metadata and venue information
- Opponent details and head-to-head history
- Complete match statistics
- Pressure situation performance
- Leg-by-leg breakdown

### Biomechanics Data
- Throw-by-throw analysis
- Phase detection (setup, backswing, acceleration, release, follow-through)
- Body position tracking at key moments
- Form deviation detection
- Consistency scoring

### Voice Observations
- Timestamped transcriptions
- Automatic categorization (technique, mental, physical)
- Sentiment analysis
- Keyword extraction
- Action items identification

## 📈 Report Contents

Weekly reports include:

1. **Executive Summary**: Overall week assessment
2. **Key Findings**: Strengths, weaknesses, trends
3. **Practice vs Competition Analysis**: Performance gap analysis
4. **Trend Analysis**: Week-over-week comparisons
5. **Biomechanics Summary**: Form analysis and issues
6. **Mental Game Analysis**: Pressure performance and self-talk patterns
7. **Recommendations**: Prioritized improvement areas with specific drills
8. **Practice Plan**: Suggested focus areas for the coming week
9. **Goals**: SMART goals based on current performance

## ⚙️ Configuration

Edit `config/settings.yaml` to customize:

- Scraper settings (URLs, retry logic)
- Biomechanics parameters (camera, MediaPipe settings)
- Voice recording settings (sample rate, transcription model)
- Ollama model and parameters
- Calendar integration settings
- Analysis schedule

## 🔧 Troubleshooting

### Scraping Issues
- Ensure credentials are correct in `.env`
- Check if website structure has changed
- Try running with `--log-level DEBUG`

### Ollama Issues
- Verify Ollama is running: `curl http://localhost:11434/api/tags`
- Ensure model is downloaded: `ollama list`
- Check model name matches config

### Camera Issues
- List devices: `python -c "from dart_coach.biomechanics import CameraHandler; print(CameraHandler.list_cameras())"`
- Set correct device ID in `.env`

### Audio Issues
- List devices: `python -c "from dart_coach.voice import VoiceRecorder; print(VoiceRecorder.list_audio_devices())"`
- Set correct device ID in `.env`

## 📝 License

MIT License - See LICENSE file for details.

## 🤝 Contributing

Contributions welcome! Please read the contributing guidelines first.

## 🙏 Acknowledgments

- [Scolia](https://scolia.com) - Practice tracking hardware/software
- [Dart Connect](https://dartconnect.com) - League management platform
- [MediaPipe](https://mediapipe.dev) - Pose estimation
- [OpenAI Whisper](https://github.com/openai/whisper) - Speech recognition
- [Ollama](https://ollama.ai) - Local LLM inference
