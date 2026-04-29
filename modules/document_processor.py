import os
import json
import uuid
from datetime import datetime
from modules.ocr_engine import extract_text
from modules.text_cleaner import clean_text, extract_entities
from modules.llm_processor import process_summary, process_mask, process_report

OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")


def _save_output(job_id: str, data: dict) -> str:
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    path = os.path.join(OUTPUTS_DIR, f"{job_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def process_document(file_path: str, mode: str, model: str = "mistral", client_ip: str = "") -> dict:
    job_id = str(uuid.uuid4())[:8]
    filename = os.path.basename(file_path)

    # Step 1 – OCR
    raw_text = extract_text(file_path)
    if not raw_text.strip():
        return {"error": "OCR produced no text. Check the file quality."}

    # Step 2 – Clean
    clean = clean_text(raw_text)

    # Step 3 – Entity extraction (metadata, not exposed to LLM)
    entities = extract_entities(clean)

    # Step 4 – LLM processing
    processors = {
        "summary": process_summary,
        "mask":    process_mask,
        "report":  process_report,
    }
    if mode not in processors:
        return {"error": f"Unknown mode: {mode}"}

    llm_result = processors[mode](clean, model)

    result = {
        "job_id":    job_id,
        "filename":  filename,
        "mode":      mode,
        "model":     model,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "client_ip": client_ip,
        "raw_text":  raw_text,
        "clean_text": clean,
        "entities":  entities,
        "output":    llm_result,
    }

    _save_output(job_id, result)
    return result
