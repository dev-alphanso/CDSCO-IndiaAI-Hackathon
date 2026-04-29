## How to Run

1. Prerequisites
Install Tesseract OCR → add to PATH
Install Ollama → ollama pull mistral

2. Setup
setup.bat          # Windows (creates venv + installs deps)

3. Start
venv\Scripts\activate
python app.py
# Open http://localhost:5000

## UI Features

1. Drag & drop upload -> PDF, PNG, JPG, TIFF up to 20 MB
2. Processing modes -> Clinical Summary · Privacy Masking · Structured JSON Report
3. Animated workflow steps -> 5-step progress bar (Upload → Configure → OCR → LLM → Output)
4. Live Ollama status -> Auto-detects running models, populates model selector
5. Tabbed results -> Output · Raw OCR · Detected Entities
6. Masked token highlights -> [PATIENT_NAME] rendered in purple in the masked view
7. JSON report grid -> Structured cards for each field — medications as a list

Job history	Last 20 jobs, click to reload any past result
Copy & Download	One-click copy or full JSON download

