import os
import json
from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from werkzeug.utils import secure_filename
from modules.document_processor import process_document
from modules.llm_processor import list_models
from modules.export_generator import generate_pdf, generate_docx

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
app.config["OUTPUT_FOLDER"] = os.path.join(os.path.dirname(__file__), "outputs")
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB

ALLOWED_EXT = {"pdf", "png", "jpg", "jpeg", "tiff", "bmp", "webp"}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["OUTPUT_FOLDER"], exist_ok=True)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.remote_addr or "unknown")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    models = list_models()
    running = models is not None
    return jsonify({"ollama_running": running, "models": models or []})


@app.route("/api/process", methods=["POST"])
def process():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    mode = request.form.get("mode", "summary")
    model = request.form.get("model", "mistral")

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type"}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    try:
        result = process_document(save_path, mode, model, client_ip=_client_ip())
        if "error" in result:
            return jsonify(result), 422
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        # Clean up uploaded file after processing
        if os.path.exists(save_path):
            os.remove(save_path)


@app.route("/api/download/<job_id>")
def download(job_id: str):
    filename = f"{job_id}.json"
    return send_from_directory(app.config["OUTPUT_FOLDER"], filename, as_attachment=True)


@app.route("/api/export/<job_id>/<fmt>")
def export(job_id: str, fmt: str):
    json_path = os.path.join(app.config["OUTPUT_FOLDER"], f"{job_id}.json")
    if not os.path.exists(json_path):
        return jsonify({"error": "Job not found"}), 404

    with open(json_path, encoding="utf-8") as f:
        job_data = json.load(f)

    base_name = os.path.splitext(job_data.get("filename", job_id))[0]

    if fmt == "pdf":
        try:
            data = generate_pdf(job_data)
            return Response(
                data,
                mimetype="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{base_name}_meddoc.pdf"'},
            )
        except Exception as e:
            return jsonify({"error": f"PDF generation failed: {e}"}), 500

    elif fmt == "docx":
        try:
            data = generate_docx(job_data)
            return Response(
                data,
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": f'attachment; filename="{base_name}_meddoc.docx"'},
            )
        except Exception as e:
            return jsonify({"error": f"DOCX generation failed: {e}"}), 500

    else:
        return jsonify({"error": f"Unknown format: {fmt}"}), 400


@app.route("/api/jobs/<job_id>", methods=["DELETE"])
def delete_job(job_id: str):
    path = os.path.join(app.config["OUTPUT_FOLDER"], f"{job_id}.json")
    if not os.path.exists(path):
        return jsonify({"error": "Job not found"}), 404
    os.remove(path)
    return jsonify({"deleted": job_id})


@app.route("/api/history")
def history():
    folder = app.config["OUTPUT_FOLDER"]
    requester_ip = _client_ip()
    items = []
    for fname in os.listdir(folder):
        if fname.endswith(".json"):
            path = os.path.join(folder, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                # Show only jobs from this IP; jobs without client_ip (old) are visible to all
                job_ip = data.get("client_ip")
                if job_ip and job_ip != requester_ip:
                    continue
                items.append({
                    "job_id":    data.get("job_id"),
                    "filename":  data.get("filename"),
                    "mode":      data.get("mode"),
                    "model":     data.get("model"),
                    "timestamp": data.get("timestamp") or "",
                })
            except Exception:
                pass
    items.sort(key=lambda x: x["timestamp"], reverse=True)
    return jsonify(items[:20])


if __name__ == "__main__":
    app.run(debug=True, port=5000)
