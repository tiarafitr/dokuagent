"""Skema output dan prompt per jenis dokumen.

Dua jenis dokumen:
  - "invoice": faktur pemasok (B2B), semua field header + item.
  - "nota"   : struk toko/restoran untuk reimbursement, hanya item dan angka.
Prompt yang SAMA dipakai saat fine-tuning dan inference.
"""
from typing import List, Optional
from pydantic import BaseModel


class Item(BaseModel):
    deskripsi: str
    qty: int
    harga_satuan: int
    jumlah: int


class Invoice(BaseModel):
    nomor_invoice: Optional[str]
    tanggal: Optional[str]          # format YYYY-MM-DD
    nama_penjual: Optional[str]
    npwp_penjual: Optional[str]
    nama_pembeli: Optional[str]
    items: List[Item]
    subtotal: Optional[int]
    ppn: Optional[int]
    total: Optional[int]


class Nota(BaseModel):
    items: List[Item]
    subtotal: Optional[int]
    ppn: Optional[int]
    total: Optional[int]


SYSTEM_PROMPT = (
    "Kamu adalah sistem ekstraksi invoice. Baca teks hasil OCR invoice berbahasa Indonesia "
    "dan keluarkan HANYA JSON valid dengan key: nomor_invoice, tanggal (YYYY-MM-DD), "
    "nama_penjual, npwp_penjual, nama_pembeli, items (list berisi deskripsi, qty, "
    "harga_satuan, jumlah), subtotal, ppn, total. Semua angka uang berupa integer rupiah "
    "tanpa titik. Jika field tidak ada, isi null."
)

SYSTEM_PROMPT_NOTA = (
    "Kamu adalah sistem ekstraksi struk belanja. Baca teks hasil OCR struk toko atau "
    "restoran berbahasa Indonesia dan keluarkan HANYA JSON valid dengan key: items (list "
    "berisi deskripsi, qty, harga_satuan, jumlah), subtotal, ppn, total. deskripsi ditulis "
    "persis seperti di struk. jumlah adalah harga total baris tersebut. Semua angka uang "
    "berupa integer rupiah tanpa titik. Jika field tidak ada di struk, isi null."
)

PROMPTS = {"invoice": SYSTEM_PROMPT, "nota": SYSTEM_PROMPT_NOTA}

HEADER_FIELDS = ["nomor_invoice", "tanggal", "nama_penjual", "npwp_penjual", "nama_pembeli"]
MONEY_FIELDS = ["subtotal", "ppn", "total"]
FIELDS = {"invoice": HEADER_FIELDS + MONEY_FIELDS, "nota": MONEY_FIELDS}
