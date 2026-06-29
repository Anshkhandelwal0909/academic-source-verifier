@echo off
echo =========================================
echo Starting Academic Source Verifier...
echo =========================================

:: Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in your PATH. 
    echo Please install Python 3.9 or newer from python.org and try again.
    pause
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist venv (
    echo [INFO] Creating Python virtual environment...
    python -m venv venv
)

:: Activate the virtual environment
call venv\Scripts\activate.bat

:: Install requirements
echo [INFO] Installing dependencies (this may take a moment on first run)...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt

:: Ensure NLTK data is downloaded
echo [INFO] Verifying language models...
python -c "import nltk; nltk.download('stopwords', quiet=True); nltk.download('punkt', quiet=True); nltk.download('averaged_perceptron_tagger_eng', quiet=True)"

:: Run the app
echo [INFO] Starting the application...
python app.py

pause
