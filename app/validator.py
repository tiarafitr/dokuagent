"""Aturan bisnis: tandai field yang perlu dicek manusia (human-in-the-loop)."""
import re
from datetime import date

NPWP_RE = re.compile(r"^\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3}$")


def _int(v):
    return int(v) if v not in (None, "") else None


def validate(d: dict, doc_type: str = "invoice") -> list[str]:
    issues = []
    if doc_type == "invoice":
        for k in ("nomor_invoice", "tanggal", "nama_penjual", "npwp_penjual", "total"):
            if not d.get(k):
                issues.append(f"{k}: kosong")
        if d.get("npwp_penjual") and not NPWP_RE.match(str(d["npwp_penjual"])):
            issues.append("npwp_penjual: format bukan 99.999.999.9-999.999")
        try:
            date.fromisoformat(str(d.get("tanggal")))
        except ValueError:
            issues.append("tanggal: bukan YYYY-MM-DD")
    elif not d.get("total"):
        issues.append("total: kosong")

    items = d.get("items") or []
    if not items:
        issues.append("items: tidak ada baris barang")
    try:
        for i, it in enumerate(items, 1):
            if int(it["qty"]) * int(it["harga_satuan"]) != int(it["jumlah"]):
                issues.append(f"items[{i}]: qty x harga != jumlah")
        subtotal, ppn, total = _int(d.get("subtotal")), _int(d.get("ppn")), _int(d.get("total"))
        if items and subtotal is not None and sum(int(it["jumlah"]) for it in items) != subtotal:
            issues.append("subtotal: tidak sama dengan jumlah item")
        if doc_type == "invoice":
            if (subtotal or 0) + (ppn or 0) != (total or 0):
                issues.append("total: subtotal + ppn != total")
        elif subtotal is not None and total is not None and total < subtotal:
            # struk bisa punya service charge/diskon, jadi cukup cek yang jelas mustahil
            issues.append("total: lebih kecil dari subtotal, cek diskon/potongan")
    except (KeyError, TypeError, ValueError):
        issues.append("items/angka: struktur tidak valid")
    return issues
