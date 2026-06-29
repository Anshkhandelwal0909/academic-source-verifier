#!/bin/bash

echo "========================================="
echo "Starting Academic Source Verifier..."
echo "========================================="

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 is not installed or not in your PATH."
    echo "Please install Python 3.9+ and try again."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "[INFO] Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate the virtual environment
source venv/bin/activate

# Install requirements
echo "[INFO] Installing dependencies (this may take a moment on first run)..."
python3 -m pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt

# Ensure NLTK data is downloaded
echo "[INFO] Verifying language models..."
python3 -c "import nltk; nltk.download('stopwords', quiet=True); nltk.download('punkt', quiet=True); nltk.download('averaged_perceptron_tagger_eng', quiet=True)"

# Run the app
echo "[INFO] Starting the application..."
python3 app.py
