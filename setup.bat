@echo off
echo =========================================
echo  MedDoc AI - Setup Script (Windows)
echo =========================================
echo.

echo [1/4] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate

echo [2/4] Installing Python dependencies...
pip install -r requirements.txt

echo [3/4] Downloading spaCy English model...
python -m spacy download en_core_web_sm

echo [4/4] Checking Tesseract...
where tesseract >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  WARNING: Tesseract OCR not found in PATH.
    echo  Download from: https://github.com/UB-Mannheim/tesseract/wiki
    echo  Install to: C:\Program Files\Tesseract-OCR\
    echo  Add to PATH and re-run this script.
    echo.
) else (
    echo  Tesseract found: OK
)

echo.
echo =========================================
echo  Setup complete!
echo  Run: venv\Scripts\activate  (if not active)
echo  Then: python app.py
echo  Open: http://localhost:5000
echo =========================================
pause
