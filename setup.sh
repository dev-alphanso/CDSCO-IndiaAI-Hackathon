#!/usr/bin/env bash
set -e

echo "========================================="
echo " MedDoc AI - Setup Script (Linux/Mac)"
echo "========================================="

echo "[1/4] Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "[2/4] Installing Python dependencies..."
pip install -r requirements.txt

echo "[3/4] Downloading spaCy English model..."
python -m spacy download en_core_web_sm

echo "[4/4] Checking Tesseract..."
if ! command -v tesseract &> /dev/null; then
  echo ""
  echo "  WARNING: Tesseract not found."
  echo "  Ubuntu/Debian: sudo apt install tesseract-ocr tesseract-ocr-hin tesseract-ocr-guj"
  echo "  macOS:         brew install tesseract tesseract-lang"
  echo ""
else
  echo "  Tesseract: $(tesseract --version 2>&1 | head -1)"
fi

echo ""
echo "========================================="
echo " Setup complete!"
echo " source venv/bin/activate"
echo " python app.py"
echo " Open: http://localhost:5000"
echo "========================================="
