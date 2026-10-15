"""Evaluasi extractor di test set: akurasi per field, F1 item, JSON valid, latensi.

Field yang labelnya kosong (null) TIDAK dinilai, supaya angka tetap jujur untuk data
yang labelnya tidak lengkap (mis. CORD tidak punya nama toko/tanggal).

Pakai:
  python scripts/evaluate.py --models qwen2.5:1.5b-instruct dokuagent            # invoice sintetis
  python scripts/evaluate.py --models dokuagent --vendor                          # + koreksi NPWP
  python scripts/evaluate.py --models qwen2.5:1.5b-instruct dokuagent --data data/real   # nota asli
"""
import argparse, json, re, statistics, sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.schemas import FIELDS  # noqa: E402

ALL_FIELDS = FIELDS["invoice"]


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


def doc_type_of(gold: dict) -> str:
    return "invoice" if "nomor_invoice" in gold else "nota"


def score(pred, gold):
    """Nilai hanya field yang ada labelnya. Return {field: 0/1, 'items_f1': float}."""
    r = {f: float(norm(pred.get(f)) == norm(gold[f]))
         for f in ALL_FIELDS if gold.get(f) is not None}
    r["items_f1"] = item_f1(pred.get("items"), gold["items"])
    return r


def evaluate(model, ids, extract_fn, post=None, base="data"):
    sums, counts, valid, lat = defaultdict(float), defaultdict(int), 0, []
    for stem in ids:
        text = Path(f"{base}/sft/ocr/{stem}.txt").read_text()
        gold = json.loads(Path(f"{base}/labels/{stem}.json").read_text())
        dt = doc_type_of(gold)
        out = extract_fn(text, model, dt)
        valid += out["json_valid"]; lat.append(out["latency_s"])
        pred = out["data"] if isinstance(out["data"], dict) else {}
        if post and dt == "invoice":
            pred, _ = post(pred)
        for k, v in score(pred, gold).items():
            sums[k] += v; counts[k] += 1
    res = {k: sums[k] / counts[k] for k in sums}
    scored = [f for f in ALL_FIELDS if f in res]
    res["field_avg"] = statistics.mean(res[f] for f in scored) if scored else float("nan")
    res["json_valid"] = valid / len(ids)
    res["latency_p50_s"] = statistics.median(lat)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--data", default="data", help="folder data, mis. data/real untuk nota asli")
    ap.add_argument("--vendor", action="store_true", help="koreksi nama penjual via data master NPWP")
    a = ap.parse_args()
    from app.extractor import extract
    post = None
    if a.vendor:
        from app.vendor import resolve_vendor as post
    ids = [json.loads(l)["id"] for l in open(f"{a.data}/sft/test.jsonl")][: a.limit]
    results = {m: evaluate(m, ids, extract, post, a.data) for m in a.models}
    cols = ["field_avg", "items_f1", "json_valid", "latency_p50_s"] + ALL_FIELDS
    lines = ["| metrik | " + " | ".join(a.models) + " |", "|---" * (len(a.models) + 1) + "|"]
    for c in cols:
        cells = [f"{results[m][c]:.3f}" if c in results[m] else "-" for m in a.models]
        lines.append(f"| {c} | " + " | ".join(cells) + " |")
    table = "\n".join(lines)
    print(table)
    print(f"\n({len(ids)} dokumen; '-' = field tidak dinilai karena labelnya kosong)")
    nama = "results" if a.data == "data" else "results_" + Path(a.data).name
    Path("docs").mkdir(exist_ok=True)
    Path(f"docs/{nama}.md").write_text("# Hasil evaluasi (test set)\n\n" + table + "\n")
    with open(f"docs/{nama}.json", "w") as fh:
        json.dump(results, fh, indent=2)
