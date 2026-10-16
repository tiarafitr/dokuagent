"""API DokuAgent. Jalankan: uvicorn app.main:app --reload  → buka http://localhost:8000/docs"""
import json, os, shutil, tempfile, time
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from app.ocr import extract_text_with_quality
from app.extractor import extract
from app.validator import (check_grounding, check_header_grounding, grounding_score,
                           is_complete, quality_issues, repair_items, validate)
from app.vendor import resolve_vendor

MODEL = os.getenv("EXTRACT_MODEL", "dokuagent-v2")
# Model cadangan (opsional): dipanggil HANYA jika hasil model utama berstatus "gagal",
# dan hanya dipakai jika jawabannya lengkap & tidak gagal grounding.
# Default mati. Contoh mengaktifkan: FALLBACK_MODEL=qwen2.5:7b uvicorn app.main:app
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "")
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
async def extract_endpoint(file: UploadFile = File(...), doc_type: str = Form("invoice")):
    """doc_type: "invoice" (faktur pemasok) atau "nota" (struk reimbursement)."""
    if doc_type not in ("invoice", "nota"):
        raise HTTPException(400, "doc_type harus 'invoice' atau 'nota'")
    suffix = Path(file.filename or "").suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
    try:
        text, quality = extract_text_with_quality(tmp.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        os.unlink(tmp.name)
    if not text.strip():
        raise HTTPException(422, "Tidak ada teks yang terbaca dari file")
    def run(model):
        """Ekstraksi + perbaikan + grounding untuk satu model."""
        o = extract(text, model, doc_type)
        if not o["json_valid"]:
            return o, [], [], {"status": "gagal", "n_masalah": 99}
        data, notes = repair_items(o["data"])                # qty yang jelas salah dihitung ulang
        grounding = check_grounding(data, text)              # angka/barang harus tercetak
        if doc_type == "invoice":
            grounding += check_header_grounding(data, text)  # sebelum koreksi NPWP
        o["data"] = data
        return o, notes, grounding, grounding_score(data, grounding)

    out, notes, grounding, score = run(MODEL)
    model_used = MODEL
    if score["status"] == "gagal" and FALLBACK_MODEL and FALLBACK_MODEL != MODEL:
        alt = run(FALLBACK_MODEL)
        alt_ok = (alt[0]["json_valid"] and is_complete(alt[0]["data"])
                  and alt[3]["status"] != "gagal")
        if alt_ok:                                            # cadangan lengkap & didukung dokumen
            out, notes, grounding, score = alt
            model_used = FALLBACK_MODEL
            notes = notes + [f"hasil diambil dari model cadangan ({FALLBACK_MODEL}) karena lebih sesuai dokumen"]
    if out["json_valid"]:
        if doc_type == "invoice":
            out["data"], vnotes = resolve_vendor(out["data"])   # koreksi nama penjual via NPWP
            notes += vnotes
        issues = quality_issues(quality) + validate(out["data"], doc_type) + grounding + notes
    else:
        issues = quality_issues(quality) + ["output model bukan JSON valid"]
    log({"type": "extract", "doc_type": doc_type, "model": model_used, "status": score["status"], "file": file.filename, "latency_s": out["latency_s"], "issues": len(issues)})
    return {"doc_type": doc_type, "model": model_used, "status": score["status"], "ocr_quality": quality, "data": out["data"], "issues": issues, "needs_review": bool(issues),
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
