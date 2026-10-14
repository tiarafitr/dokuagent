"""Koreksi nama penjual lewat data master pemasok, dengan NPWP sebagai kunci.

NPWP diekstrak model dengan akurasi 100% di test set, sedangkan nama penjual
sering salah eja karena OCR. Jadi nama diambil dari data master, bukan dari OCR.
"""
import csv, os
from pathlib import Path
from difflib import SequenceMatcher

_MASTER = None


def _master() -> dict:
    global _MASTER
    if _MASTER is None:
        p = Path(os.getenv("VENDOR_MASTER", "data/vendors.csv"))
        _MASTER = {}
        if p.exists():
            with p.open() as fh:
                _MASTER = {r["npwp"]: r["nama_resmi"] for r in csv.DictReader(fh)}
    return _MASTER


def resolve_vendor(d: dict) -> tuple[dict, list[str]]:
    """Kembalikan (data yang sudah dikoreksi, daftar catatan untuk reviewer)."""
    notes = []
    npwp = (d.get("npwp_penjual") or "").strip()
    resmi = _master().get(npwp)
    if resmi is None:
        notes.append("nama_penjual: NPWP tidak ada di data master (pemasok baru?), cek manual")
        return d, notes
    hasil_ocr = d.get("nama_penjual") or ""
    if hasil_ocr != resmi:
        skor = 100 * SequenceMatcher(None, hasil_ocr.lower(), resmi.lower()).ratio()
        if skor < 60:  # terlalu beda: bisa jadi NPWP salah baca, jangan koreksi diam-diam
            notes.append(f"nama_penjual: '{hasil_ocr}' sangat berbeda dari data master '{resmi}', cek manual")
            return d, notes
        d = {**d, "nama_penjual": resmi}
    return d, notes
