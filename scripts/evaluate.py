"""Evaluasi extractor di test set: akurasi per field, F1 item, JSON valid, latensi.
Pakai: python scripts/evaluate.py --models qwen2.5:1.5b-instruct qwen2.5:7b dokuagent
"""
import argparse, json, re, statistics, sys
from difflib import SequenceMatcher
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FIELDS = ["nomor_invoice", "tanggal", "nama_penjual", "npwp_penjual",
          "nama_pembeli", "subtotal", "ppn", "total"]


def norm(v):
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        return str(int(v))
    s = str(v).strip().lower()
    if re.fullmatch(r"(rp\.?\s*)?[\d.,]+", s):  # "Rp 1.250.000" -> "1250000"
        s = re.sub(r"[^\d]", "", s.split(",")[0])
    return re.sub(r"\s+", " ", s)


def item_f1(pred, gold):
    pred = [p for p in (pred or []) if isinstance(p, dict)]
    used, tp = set(), 0
    for g in gold:
        for j, p in enumerate(pred):
            if j in used:
                continue
            same_num = all(norm(p.get(k)) == norm(g[k]) for k in ("qty", "harga_satuan", "jumlah"))
            same_desc = SequenceMatcher(None, norm(p.get("deskripsi")), norm(g["deskripsi"])).ratio() > 0.85
            if same_num and same_desc:
                used.add(j); tp += 1; break
    if tp == 0:
        return 0.0
    prec, rec = tp / len(pred), tp / len(gold)
    return 2 * prec * rec / (prec + rec)


def score(pred, gold):
    r = {f: float(norm(pred.get(f)) == norm(gold[f])) for f in FIELDS}
    r["items_f1"] = item_f1(pred.get("items"), gold["items"])
    return r


def evaluate(model, ids, extract_fn, post=None):
    rows, valid, lat = [], 0, []
    for stem in ids:
        text = Path(f"data/sft/ocr/{stem}.txt").read_text()
        gold = json.loads(Path(f"data/labels/{stem}.json").read_text())
        out = extract_fn(text, model)
        valid += out["json_valid"]; lat.append(out["latency_s"])
        pred = out["data"] if isinstance(out["data"], dict) else {}
        if post:
            pred, _ = post(pred)
        rows.append(score(pred, gold))
    res = {k: statistics.mean(r[k] for r in rows) for k in rows[0]}
    res["field_avg"] = statistics.mean(res[f] for f in FIELDS)
    res["json_valid"] = valid / len(ids)
    res["latency_p50_s"] = statistics.median(lat)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--vendor", action="store_true", help="koreksi nama penjual via data master NPWP")
    a = ap.parse_args()
    from app.extractor import extract
    post = None
    if a.vendor:
        from app.vendor import resolve_vendor as post
    ids = [json.loads(l)["id"] for l in open("data/sft/test.jsonl")][: a.limit]
    results = {m: evaluate(m, ids, extract, post) for m in a.models}
    cols = ["field_avg", "items_f1", "json_valid", "latency_p50_s"] + FIELDS
    lines = ["| metrik | " + " | ".join(a.models) + " |", "|---" * (len(a.models) + 1) + "|"]
    for c in cols:
        lines.append(f"| {c} | " + " | ".join(f"{results[m][c]:.3f}" for m in a.models) + " |")
    table = "\n".join(lines)
    print(table)
    Path("docs").mkdir(exist_ok=True)
    Path("docs/results.md").write_text("# Hasil evaluasi (test set)\n\n" + table + "\n")
    json.dump(results, open("docs/results.json", "w"), indent=2)
