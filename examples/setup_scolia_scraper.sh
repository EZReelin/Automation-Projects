#!/bin/bash
# Scolia Scraper Setup Script
# ============================
# This script sets up the environment for the Scolia comprehensive scraper

set -e  # Exit on error

echo "=========================================="
echo "Scolia Scraper Setup"
echo "=========================================="
echo ""

# Check if Python 3.9+ is installed
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.9"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)"; then
    echo "Error: Python 3.9 or higher is required"
    echo "Current version: $PYTHON_VERSION"
    exit 1
fi

echo "Python version: $PYTHON_VERSION ✓"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created ✓"
else
    echo "Virtual environment already exists ✓"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "Virtual environment activated ✓"
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "pip upgraded ✓"
echo ""

# Install dependencies
echo "Installing dependencies..."
cd dart_coach
pip install -e . > /dev/null 2>&1
echo "Dependencies installed ✓"
echo ""

# Create necessary directories
echo "Creating directories..."
mkdir -p data/scolia
mkdir -p logs
mkdir -p logs/screenshots
mkdir -p config
echo "Directories created ✓"
echo ""

# Copy example config if config doesn't exist
if [ ! -f "config/scolia_scraper_config.yaml" ]; then
    echo "Creating configuration file..."
    cp config/scolia_scraper_config.example.yaml config/scolia_scraper_config.yaml
    echo "Configuration file created ✓"
    echo ""
    echo "IMPORTANT: Please edit config/scolia_scraper_config.yaml"
    echo "and set your Scolia credentials, or use environment variables:"
    echo ""
    echo "  export SCOLIA_USERNAME='your_email@example.com'"
    echo "  export SCOLIA_PASSWORD='your_password'"
    echo ""
fi

# Create .env template if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env template..."
    cat > .env << EOF
# Scolia Credentials
SCOLIA_USERNAME=your_email@example.com
SCOLIA_PASSWORD=your_password
EOF
    echo ".env template created ✓"
    echo ""
    echo "IMPORTANT: Please edit .env file and set your actual credentials"
    echo ""
fi

# Check for Chrome/Chromium
echo "Checking for Chrome/Chromium..."
if command -v google-chrome &> /dev/null; then
    echo "Google Chrome found ✓"
elif command -v chromium &> /dev/null; then
    echo "Chromium found ✓"
elif command -v chromium-browser &> /dev/null; then
    echo "Chromium Browser found ✓"
else
    echo "WARNING: Chrome/Chromium not found!"
    echo "Please install Chrome or Chromium for the scraper to work:"
    echo ""
    echo "  Ubuntu/Debian: sudo apt-get install chromium-browser"
    echo "  MacOS: brew install --cask google-chrome"
    echo "  Or download from: https://www.google.com/chrome/"
    echo ""
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Set your Scolia credentials (see above)"
echo "  2. Run the scraper:"
echo "     cd .."
echo "     python examples/run_scolia_scraper.py --all"
echo ""
echo "For more options:"
echo "  python examples/run_scolia_scraper.py --help"
echo ""
