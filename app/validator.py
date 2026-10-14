"""Aturan bisnis: tandai field yang perlu dicek manusia (human-in-the-loop)."""
import re
from datetime import date

NPWP_RE = re.compile(r"^\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3}$")

def validate(d: dict) -> list[str]:
    issues = []
    for k in ("nomor_invoice", "tanggal", "nama_penjual", "npwp_penjual", "total"):
        if not d.get(k):
            issues.append(f"{k}: kosong")
    if d.get("npwp_penjual") and not NPWP_RE.match(str(d["npwp_penjual"])):
        issues.append("npwp_penjual: format bukan 99.999.999.9-999.999")
    try:
        date.fromisoformat(str(d.get("tanggal")))
    except ValueError:
        issues.append("tanggal: bukan YYYY-MM-DD")
    items = d.get("items") or []
    try:
        for i, it in enumerate(items, 1):
            if int(it["qty"]) * int(it["harga_satuan"]) != int(it["jumlah"]):
                issues.append(f"items[{i}]: qty x harga != jumlah")
        if items and sum(int(it["jumlah"]) for it in items) != int(d.get("subtotal") or 0):
            issues.append("subtotal: tidak sama dengan jumlah item")
        if int(d.get("subtotal") or 0) + int(d.get("ppn") or 0) != int(d.get("total") or 0):
            issues.append("total: subtotal + ppn != total")
    except (KeyError, TypeError, ValueError):
        issues.append("items/angka: struktur tidak valid")
    return issues
