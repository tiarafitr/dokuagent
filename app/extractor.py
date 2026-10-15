"""Panggil LLM lewat Ollama untuk mengubah teks OCR menjadi JSON."""
import json, os, re, time
import requests
from app.schemas import PROMPTS

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


def parse_json(raw: str):
    raw = raw.strip()
    m = re.search(r"\{.*\}", raw, re.S)   # buang teks di luar kurung kurawal
    return json.loads(m.group(0) if m else raw)


def extract(ocr_text: str, model: str = "qwen2.5:1.5b-instruct", doc_type: str = "invoice") -> dict:
    if doc_type not in PROMPTS:
        raise ValueError(f"doc_type harus salah satu dari {list(PROMPTS)}")
    t0 = time.time()
    r = requests.post(f"{OLLAMA_URL}/api/chat", json={
        "model": model,
        "messages": [{"role": "system", "content": PROMPTS[doc_type]},
                     {"role": "user", "content": ocr_text}],
        "format": "json",
        "stream": False,
        "options": {"temperature": 0, "num_ctx": 4096},
    }, timeout=300)
    r.raise_for_status()
    raw = r.json()["message"]["content"]
    try:
        data, ok = parse_json(raw), True
    except json.JSONDecodeError:
        data, ok = {}, False
    if ok and isinstance(data, dict) and doc_type == "nota":
        # buang field header yang tidak diminta, kalau model tetap menulisnya
        data = {k: data.get(k) for k in ("items", "subtotal", "ppn", "total")}
    return {"data": data, "json_valid": ok, "latency_s": round(time.time() - t0, 2), "raw": raw}
