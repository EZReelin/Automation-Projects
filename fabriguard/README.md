# FabriGuard - AI Predictive Maintenance Platform

## Overview

FabriGuard is a turnkey AI-powered predictive maintenance platform specifically designed for small-to-medium metal fabrication shops ($10M-$100M revenue). It predicts equipment failures before they occur, requires zero IT infrastructure or expertise to deploy, and delivers measurable ROI within 90 days.

## Problem We Solve

Metal fabricators face $125,000+ per hour in downtime costs when critical equipment fails unexpectedly. Current predictive maintenance solutions target enterprise customers with $100K+ implementations. FabriGuard brings enterprise-grade predictive maintenance to shops that:
- Have no dedicated IT staff
- Need plug-and-play solutions
- Want transparent, predictable pricing

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│   Sensors   │───▶│ Edge Gateway │───▶│    Cloud    │───▶│  Dashboard   │
│             │    │              │    │  Platform   │    │  (Web/Mobile)│
└─────────────┘    └──────────────┘    └─────────────┘    └──────────────┘
     │                   │                    │                   │
  Vibration        Preprocessing         ML Inference       Fleet Health
  Temperature      Anomaly Filter        Alert Engine       Notifications
  Current          Compression           Predictions        Work Orders
  Pressure         Store & Forward       Analytics          ROI Tracking
```

## Supported Equipment

### Phase 1 (MVP)
- **CNC Machining Centers & Lathes**: Spindle health, axis wear, coolant systems
- **Hydraulic Presses & Press Brakes**: Pump degradation, seal wear, valve performance
- **Air Compressors**: Motor health, pressure cycling, filter condition

### Phase 2 (Expansion)
- Shears and punches
- MIG/TIG welders
- Coolant and lubrication systems

## Project Structure

```
fabriguard/
├── backend/               # FastAPI backend services
│   ├── api/              # REST API endpoints
│   ├── models/           # Database models
│   ├── services/         # Business logic
│   ├── ml/               # Machine learning models
│   └── utils/            # Utility functions
├── frontend/             # React web dashboard
│   ├── src/
│   │   ├── components/   # Reusable UI components
│   │   ├── pages/        # Page components
│   │   ├── hooks/        # Custom React hooks
│   │   └── services/     # API client services
│   └── public/
├── edge/                 # Edge computing components
│   ├── firmware/         # Sensor firmware
│   └── gateway/          # Edge gateway processing
├── sensors/              # Sensor management
│   ├── simulation/       # Sensor data simulation
│   └── calibration/      # Calibration utilities
├── docs/                 # Documentation
├── scripts/              # Deployment & utility scripts
└── config/               # Configuration files
```

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 15+ (or Docker)
- Redis (optional, for caching)

### Backend Setup

```bash
cd fabriguard/backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration
python -m uvicorn api.main:app --reload
```

### Frontend Setup

```bash
cd fabriguard/frontend
npm install
cp .env.example .env.local
npm run dev
```

### Run with Docker Compose

```bash
cd fabriguard
docker-compose up -d
```

## API Documentation

Once the backend is running, access the interactive API docs at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Key Features

### 1. Zero-IT Deployment
- Plug-and-play wireless sensors
- Cellular/WiFi connectivity with automatic cloud sync
- Mobile-first interface
- Vendor-managed cloud infrastructure

### 2. AI/ML Capabilities
- **Anomaly Detection**: Identifies deviations from normal patterns
- **RUL Prediction**: Remaining Useful Life with confidence intervals
- **Failure Mode Classification**: Bearing wear, lubrication issues, etc.
- **Trend Analysis**: Equipment degradation over time
- **Explainable AI**: Plain-language alert explanations

### 3. User Interface
- Fleet health dashboard (green/yellow/red status)
- Mobile push notifications
- Plain-language maintenance recommendations
- Work order generation
- ROI tracking with documented savings

## Pricing

- $150-250/asset/month (all-inclusive)
- No upfront implementation fees
- Month-to-month after 12-month commitment
- Volume discounts available

## Success Metrics

- **Deployment Time**: < 4 hours for 10 assets
- **Prediction Accuracy**: > 85% true positive rate
- **False Positive Rate**: < 10%
- **Customer ROI**: 5-10x documented savings

## License

Proprietary - All Rights Reserved

## Contact

For more information, contact the FabriGuard team.
