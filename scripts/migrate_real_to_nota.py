"""Ubah data CORD yang sudah diimpor (format lama) ke skema "nota", tanpa unduh/OCR ulang.

Yang diubah: data/real/labels/*.json dan data/real/sft/{train,test}.jsonl
(field header dibuang, prompt sistem diganti ke prompt nota). Teks OCR tidak disentuh.
Aman dijalankan berkali-kali.
Pakai: python scripts/migrate_real_to_nota.py
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.schemas import SYSTEM_PROMPT_NOTA  # noqa: E402

BASE = Path("data/real")
KEEP = ("items", "subtotal", "ppn", "total")

n = 0
for f in sorted((BASE / "labels").glob("*.json")):
    d = json.loads(f.read_text())
    f.write_text(json.dumps({k: d.get(k) for k in KEEP}, ensure_ascii=False, indent=2))
    n += 1
for split in ("train", "test"):
    p = BASE / "sft" / f"{split}.jsonl"
    rows = [json.loads(l) for l in p.open() if l.strip()]
    with p.open("w") as fh:
        for r in rows:
            label = json.loads((BASE / "labels" / f"{r['id']}.json").read_text())
            r["messages"][0]["content"] = SYSTEM_PROMPT_NOTA
            r["messages"][2]["content"] = json.dumps(label, ensure_ascii=False)
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{split}: {len(rows)} contoh dikonversi")
print(f"{n} label dikonversi ke skema nota")
