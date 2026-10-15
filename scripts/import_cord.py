"""Impor nota ASLI dari dataset CORD-v2 (struk toko & restoran Indonesia, lisensi CC-BY-4.0).

Sumber: https://huggingface.co/datasets/naver-clova-ix/cord-v2
Sitasi: Park et al., "CORD: A Consolidated Receipt Dataset for Post-OCR Parsing", 2019.

Yang dilakukan skrip ini:
  1. Mengunduh N nota dari split train dan M nota dari split test (streaming, tidak perlu unduh semua).
  2. Menyimpan gambar ke data/real/raw/, label (format skema DokuAgent) ke data/real/labels/.
  3. Menjalankan OCR yang sama dengan pipeline utama, lalu membuat
     data/real/sft/train.jsonl dan data/real/sft/test.jsonl.

Nota memakai skema dan prompt "nota" (items, subtotal, ppn, total), terpisah dari invoice
pemasok. CORD tidak memuat nama toko, nomor nota, atau tanggal di labelnya (dihapus pembuatnya
karena alasan hukum), jadi field header memang tidak diminta untuk jenis dokumen ini.

Pakai:  pip install datasets
        python scripts/import_cord.py --train 100 --test 50
"""
import argparse, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = Path("data/real")


def to_int(s):
    """'75,000' / '75.000' / 'Rp 25.000,00' / '25,000.00' -> 75000 / 25000. None jika kosong."""
    if s is None:
        return None
    s = str(s).strip()
    if re.search(r"[.,]\d{2}$", s) and not re.search(r"[.,]\d{3}$", s):
        s = s[:-3]  # buang desimal ,00 / .00
    neg = s.startswith("-")
    digits = re.sub(r"\D", "", s)
    if not digits:
        return None
    return -int(digits) if neg else int(digits)


def to_qty(s):
    """'1 x' / 'x2' / '2.00' / '3 PCS' / None -> 1, 2, 2, 3, 1."""
    m = re.search(r"\d+(?:[.,]\d+)?", str(s or ""))
    if not m:
        return 1
    return max(1, int(float(m.group(0).replace(",", "."))))


def _first(v):
    return v[0] if isinstance(v, list) else v


def convert(gt_parse: dict) -> dict:
    menu = gt_parse.get("menu") or []
    if isinstance(menu, dict):
        menu = [menu]
    items = []
    for m in menu:
        nm = _first(m.get("nm"))
        jumlah = to_int(_first(m.get("price")))
        if not nm or jumlah is None:
            continue
        qty = to_qty(_first(m.get("cnt")))
        unit = to_int(_first(m.get("unitprice")))
        if unit is None:
            unit = jumlah // qty if qty else jumlah
        items.append({"deskripsi": str(nm).strip(), "qty": qty, "harga_satuan": unit, "jumlah": jumlah})
    sub = gt_parse.get("sub_total") or {}
    tot = gt_parse.get("total") or {}
    if isinstance(sub, list):
        sub = sub[0] if sub else {}
    if isinstance(tot, list):
        tot = tot[0] if tot else {}
    return {
        "items": items,
        "subtotal": to_int(_first(sub.get("subtotal_price"))),
        "ppn": to_int(_first(sub.get("tax_price"))),
        "total": to_int(_first(tot.get("total_price"))),
    }


def run(n_train, n_test):
    from datasets import load_dataset
    from app.ocr import extract_text
    from app.schemas import SYSTEM_PROMPT_NOTA

    for sub in ("raw", "labels", "sft/ocr"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    for split, n in (("train", n_train), ("test", n_test)):
        ds = load_dataset("naver-clova-ix/cord-v2", split=split, streaming=True)
        kept = 0
        with open(OUT / "sft" / f"{split}.jsonl", "w") as f:
            for i, row in enumerate(ds):
                if kept >= n:
                    break
                label = convert(json.loads(row["ground_truth"])["gt_parse"])
                if not label["items"] or label["total"] is None:
                    continue  # lewati nota yang labelnya tidak lengkap
                stem = f"cord_{split}_{i:04d}"
                img_path = OUT / "raw" / f"{stem}.jpg"
                row["image"].convert("RGB").save(img_path, quality=90)
                (OUT / "labels" / f"{stem}.json").write_text(json.dumps(label, ensure_ascii=False, indent=2))
                text = extract_text(str(img_path))
                (OUT / "sft" / "ocr" / f"{stem}.txt").write_text(text)
                f.write(json.dumps({"id": stem, "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT_NOTA},
                    {"role": "user", "content": text},
                    {"role": "assistant", "content": json.dumps(label, ensure_ascii=False)},
                ]}, ensure_ascii=False) + "\n")
                kept += 1
                print(f"\r{split}: {kept}/{n}", end="", flush=True)
        print()
    print(f"Selesai. Data di {OUT}/ ; gabungkan untuk training:\n"
          f"  cat data/sft/train.jsonl {OUT}/sft/train.jsonl > data/sft/train_mix.jsonl")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=int, default=100)
    ap.add_argument("--test", type=int, default=50)
    a = ap.parse_args()
    run(a.train, a.test)
