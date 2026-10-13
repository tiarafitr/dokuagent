"""Buat dataset chat (JSONL) untuk fine-tuning: input = teks OCR, output = label JSON.
Pakai: python scripts/build_sft_dataset.py
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ocr import extract_text
from app.schemas import SYSTEM_PROMPT

RAW, LAB, OUT = Path("data/raw"), Path("data/labels"), Path("data/sft")
SPLITS = {"train": range(1, 481), "val": range(481, 541), "test": range(541, 601)}

OUT.mkdir(parents=True, exist_ok=True)
for split, ids in SPLITS.items():
    n = 0
    with open(OUT / f"{split}.jsonl", "w") as f:
        for i in ids:
            stem = f"inv_{i:04d}"
            src = next(RAW.glob(stem + ".*"), None)
            if src is None:
                continue
            text = extract_text(str(src))          # OCR asli -> model belajar menghadapi noise
            (OUT / "ocr").mkdir(exist_ok=True)
            (OUT / "ocr" / f"{stem}.txt").write_text(text)   # cache untuk evaluasi
            label = json.loads((LAB / f"{stem}.json").read_text())
            f.write(json.dumps({"id": stem, "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
                {"role": "assistant", "content": json.dumps(label, ensure_ascii=False)},
            ]}, ensure_ascii=False) + "\n")
            n += 1
    print(split, n, "contoh")
