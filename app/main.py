"""API DokuAgent. Jalankan: uvicorn app.main:app --reload  → buka http://localhost:8000/docs"""
import json, os, shutil, tempfile, time
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel
from app.ocr import extract_text
from app.extractor import extract
from app.validator import validate

MODEL = os.getenv("EXTRACT_MODEL", "dokuagent")
LOG = Path("logs/requests.jsonl")
LOG.parent.mkdir(exist_ok=True)
app = FastAPI(title="DokuAgent", description="Ekstraksi invoice Indonesia dengan LLM lokal hasil fine-tuning")


def log(event: dict):
    with LOG.open("a") as f:
        f.write(json.dumps({"ts": time.time(), **event}, ensure_ascii=False) + "\n")


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL}


@app.post("/extract")
async def extract_endpoint(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
    try:
        text = extract_text(tmp.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        os.unlink(tmp.name)
    if not text.strip():
        raise HTTPException(422, "Tidak ada teks yang terbaca dari file")
    out = extract(text, MODEL)
    issues = validate(out["data"]) if out["json_valid"] else ["output model bukan JSON valid"]
    log({"type": "extract", "file": file.filename, "latency_s": out["latency_s"], "issues": len(issues)})
    return {"data": out["data"], "issues": issues, "needs_review": bool(issues),
            "latency_s": out["latency_s"], "ocr_text": text}


class PushIn(BaseModel):
    data: dict


@app.post("/push")
def push_endpoint(body: PushIn):
    try:
        from app.sheets import append_invoice
        n = append_invoice(body.data)
    except Exception as e:  # kredensial/SHEET_ID belum diatur, dll.
        raise HTTPException(500, f"Gagal kirim ke Google Sheets: {e}")
    log({"type": "push", "invoice": body.data.get("nomor_invoice"), "rows": n})
    return {"rows_added": n}


@app.get("/stats")
def stats():
    """Ringkasan monitoring sederhana dari log."""
    if not LOG.exists():
        return {"total": 0}
    rows = [json.loads(l) for l in LOG.open() if l.strip()]
    ex = [r for r in rows if r["type"] == "extract"]
    if not ex:
        return {"total": 0}
    lat = sorted(r["latency_s"] for r in ex)
    return {"total": len(ex),
            "perlu_review": sum(r["issues"] > 0 for r in ex),
            "latency_p50_s": lat[len(lat) // 2],
            "dikirim_ke_sheets": sum(r["type"] == "push" for r in rows)}
