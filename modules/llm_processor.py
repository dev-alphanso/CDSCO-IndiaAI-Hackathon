import re
import json
import requests
from config import OLLAMA_BASE_URL, OLLAMA_MODEL

# Max chars sent to the LLM in a single call.
# ~8 000 chars ≈ 10–12 pages of typical medical text.
_CHUNK_SIZE   = 8_000
# Overlap between consecutive chunks to preserve cross-page context.
_CHUNK_OVERLAP = 200

_PROMPTS = {
    "summary": """You are a medical assistant. Given the following medical document text, produce a concise clinical summary with these sections:
- **Chief Complaint / Reason for Visit**
- **Key Diagnosis / Findings**
- **Prescribed Medications** (name, dosage, frequency if available)
- **Doctor's Notes / Instructions**
- **Follow-up Recommendations**

Be precise, use bullet points, and avoid reproducing raw OCR noise.

Document text:
{text}

Summary:""",

    "summary_combine": """You are a medical assistant. The following are partial summaries of consecutive sections of a long medical document.
Merge them into one coherent clinical summary with these sections:
- **Chief Complaint / Reason for Visit**
- **Key Diagnosis / Findings**
- **Prescribed Medications** (name, dosage, frequency if available)
- **Doctor's Notes / Instructions**
- **Follow-up Recommendations**

Deduplicate repeated information. Be concise and use bullet points.

Partial summaries:
{text}

Final summary:""",

    "mask": """You are a medical privacy specialist. Identify and replace ALL personally identifiable information (PII) in the following medical document with placeholder tokens:
- Patient name → [PATIENT_NAME]
- Doctor name → [DOCTOR_NAME]
- Hospital/Clinic name → [FACILITY_NAME]
- Phone numbers → [PHONE]
- Email → [EMAIL]
- Address (street, city, state, pin) → [ADDRESS]
- Date of Birth → [DOB]
- Aadhar / PAN / ID numbers → [ID_NUMBER]
- Any other identifying detail → [REDACTED]

Return ONLY the masked document text, preserving medical terminology.

Original document:
{text}

Masked document:""",

    "report": """You are a medical data extraction specialist. Parse the following medical document and return a valid JSON object with this exact structure:
{{
  "patient_name": "",
  "patient_age": "",
  "patient_gender": "",
  "visit_date": "",
  "doctor_name": "",
  "facility_name": "",
  "chief_complaint": "",
  "diagnosis": [],
  "medications": [
    {{"name": "", "dosage": "", "frequency": "", "duration": ""}}
  ],
  "lab_tests": [],
  "vitals": {{}},
  "doctor_notes": "",
  "follow_up": "",
  "document_type": ""
}}

Fill every field you can find. Use empty string "" or empty array [] for missing fields. Return ONLY the JSON, no explanation.

Document text:
{text}

JSON:""",

    "report_merge": """You are a medical data extraction specialist. Merge the following JSON objects (extracted from consecutive pages of the same document) into one combined JSON. Rules:
- For string fields: keep the first non-empty value.
- For array fields (diagnosis, medications, lab_tests): combine all unique items.
- For vitals dict: merge all keys.
Return ONLY the merged JSON, no explanation.

JSON objects to merge:
{text}

Merged JSON:"""
}


def _chunks(text: str) -> list[str]:
    """Split text into overlapping chunks of _CHUNK_SIZE chars."""
    if len(text) <= _CHUNK_SIZE:
        return [text]
    parts = []
    start = 0
    while start < len(text):
        end = start + _CHUNK_SIZE
        parts.append(text[start:end])
        start = end - _CHUNK_OVERLAP
    return parts


def _call_ollama(prompt: str, model: str = OLLAMA_MODEL) -> str:
    print(f"[LLM] calling model={model}  prompt_len={len(prompt)} chars", flush=True)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 2048},
    }
    resp = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=180)
    resp.raise_for_status()
    result = resp.json().get("response", "").strip()
    print(f"[LLM] response received  model={model}  response_len={len(result)} chars", flush=True)
    return result


def list_models() -> list[str] | None:
    """Return model names, or None if Ollama is unreachable."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return None


#def is_ollama_running() -> bool:
#    return list_models() is not None


# ── Summary ────────────────────────────────────────────────

def process_summary(text: str, model: str = OLLAMA_MODEL) -> dict:
    chunks = _chunks(text)

    if len(chunks) == 1:
        result = _call_ollama(_PROMPTS["summary"].format(text=chunks[0]), model)
        return {"type": "summary", "content": result}

    # Multi-chunk: summarise each chunk, then combine
    partial = []
    for i, chunk in enumerate(chunks):
        part = _call_ollama(_PROMPTS["summary"].format(text=chunk), model)
        partial.append(f"--- Section {i+1} ---\n{part}")

    combined_input = "\n\n".join(partial)
    final = _call_ollama(_PROMPTS["summary_combine"].format(text=combined_input), model)
    return {"type": "summary", "content": final}


# ── Mask ───────────────────────────────────────────────────

def process_mask(text: str, model: str = OLLAMA_MODEL) -> dict:
    from modules.text_cleaner import mask_pii
    rule_masked = mask_pii(text)       # rule-based pass first
    chunks = _chunks(rule_masked)

    masked_parts = []
    for chunk in chunks:
        part = _call_ollama(_PROMPTS["mask"].format(text=chunk), model)
        masked_parts.append(part)

    return {"type": "mask", "content": "\n\n".join(masked_parts)}


# ── Report ─────────────────────────────────────────────────

def _parse_json(raw: str) -> dict:
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
    json_str = match.group(1) if match else raw
    return json.loads(json_str.strip())


def _merge_reports(reports: list[dict]) -> dict:
    """Merge multiple partial report dicts into one."""
    merged: dict = {}
    for r in reports:
        for key, val in r.items():
            if key not in merged or not merged[key]:
                merged[key] = val
            elif isinstance(val, list) and isinstance(merged[key], list):
                # Combine arrays, deduplicate by string representation
                seen = {json.dumps(x, sort_keys=True) for x in merged[key]}
                for item in val:
                    if json.dumps(item, sort_keys=True) not in seen:
                        merged[key].append(item)
                        seen.add(json.dumps(item, sort_keys=True))
            elif isinstance(val, dict) and isinstance(merged[key], dict):
                merged[key].update({k: v for k, v in val.items() if v})
    return merged


def process_report(text: str, model: str = OLLAMA_MODEL) -> dict:
    chunks = _chunks(text)

    if len(chunks) == 1:
        raw = _call_ollama(_PROMPTS["report"].format(text=chunks[0]), model)
        try:
            data = _parse_json(raw)
        except Exception:
            data = {"raw": raw, "parse_error": "Could not parse JSON from LLM output"}
        return {"type": "report", "content": data}

    # Multi-chunk: extract from each chunk, merge
    partial_reports = []
    for chunk in chunks:
        raw = _call_ollama(_PROMPTS["report"].format(text=chunk), model)
        try:
            partial_reports.append(_parse_json(raw))
        except Exception:
            pass   # skip unparseable chunks

    if not partial_reports:
        return {"type": "report", "content": {"parse_error": "No valid JSON from any chunk"}}

    merged = _merge_reports(partial_reports)
    return {"type": "report", "content": merged}
