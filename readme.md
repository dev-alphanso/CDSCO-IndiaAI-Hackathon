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
##Feature	                 ##Detail
Drag & drop upload	        PDF, PNG, JPG, TIFF up to 20 MB
3 processing modes	        Clinical Summary · Privacy Masking · Structured JSON Report
Animated workflow steps	5-step progress bar (Upload → Configure → OCR → LLM → Output)
Live Ollama status	        Auto-detects running models, populates model selector
Tabbed results	            Output · Raw OCR · Detected Entities
Masked token highlights	    [PATIENT_NAME] rendered in purple in the masked view
JSON report grid	        Structured cards for each field — medications as a list

Job history	Last 20 jobs, click to reload any past result
Copy & Download	One-click copy or full JSON download
