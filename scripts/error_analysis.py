"""Tampilkan invoice test yang salah diekstrak, beserta field yang salah.
Pakai: python scripts/error_analysis.py --model qwen2.5:1.5b-instruct --limit 20
"""
import argparse, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from evaluate import score, doc_type_of  # noqa: E402


def items_tuple(items):
    return [(i.get("deskripsi"), i.get("qty"), i.get("harga_satuan"), i.get("jumlah"))
            for i in (items or []) if isinstance(i, dict)]


def main(model, limit, extract_fn, base="data"):
    ids = [json.loads(l)["id"] for l in open(f"{base}/sft/test.jsonl")][:limit]
    salah = Counter()
    for stem in ids:
        gold = json.loads(Path(f"{base}/labels/{stem}.json").read_text())
        out = extract_fn(Path(f"{base}/sft/ocr/{stem}.txt").read_text(), model, doc_type_of(gold))
        pred = out["data"] if isinstance(out["data"], dict) else {}
        r = score(pred, gold)
        bad = [k for k, v in r.items() if v < 1]
        if not bad:
            continue
        salah.update(bad)
        jenis = "nota" if stem.startswith("cord") else ("jpg" if int(stem[-4:]) % 2 == 0 else "pdf")
        print(f"\n== {stem} ({jenis}, {len(gold['items'])} item) salah di: {', '.join(bad)}")
        for k in bad:
            if k == "items_f1":
                print("   gold items:", items_tuple(gold["items"]))
                print("   pred items:", items_tuple(pred.get("items")))
            else:
                print(f"   {k}: gold={gold[k]!r}  pred={pred.get(k)!r}")
    print("\nRingkasan field yang salah:", dict(salah.most_common()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5:1.5b-instruct")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--data", default="data")
    a = ap.parse_args()
    from app.extractor import extract
    main(a.model, a.limit, extract, a.data)
