"""Buat data master pemasok (simulasi): data/vendors.csv berisi NPWP -> nama resmi.

Di dunia nyata, daftar ini sudah dimiliki klien (sistem akuntansi / ERP).
Di sini kita buat dari label, lalu sengaja menyisakan ±10% pemasok sebagai
"pemasok baru" yang belum terdaftar, supaya alur review-nya ikut teruji.
Pakai: python scripts/build_vendor_master.py
"""
import csv, json, random
from pathlib import Path

random.seed(7)
vendors = {}
for f in sorted(Path("data/labels").glob("*.json")):
    d = json.loads(f.read_text())
    vendors[d["npwp_penjual"]] = d["nama_penjual"]
items = sorted(vendors.items())
baru = set(random.sample([k for k, _ in items], k=len(items) // 10))
with open("data/vendors.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["npwp", "nama_resmi"])
    for npwp, nama in items:
        if npwp not in baru:
            w.writerow([npwp, nama])
print(f"{len(items) - len(baru)} pemasok terdaftar, {len(baru)} sengaja dikosongkan sebagai pemasok baru")
