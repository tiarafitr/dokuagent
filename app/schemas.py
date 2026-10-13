from typing import List
from pydantic import BaseModel

class Item(BaseModel):
    deskripsi: str
    qty: int
    harga_satuan: int
    jumlah: int

class Invoice(BaseModel):
    nomor_invoice: str
    tanggal: str          # format YYYY-MM-DD
    nama_penjual: str
    npwp_penjual: str
    nama_pembeli: str
    items: List[Item]
    subtotal: int
    ppn: int
    total: int

# Prompt yang SAMA dipakai saat fine-tuning dan inference
SYSTEM_PROMPT = (
    "Kamu adalah sistem ekstraksi invoice. Baca teks hasil OCR invoice berbahasa Indonesia "
    "dan keluarkan HANYA JSON valid dengan key: nomor_invoice, tanggal (YYYY-MM-DD), "
    "nama_penjual, npwp_penjual, nama_pembeli, items (list berisi deskripsi, qty, "
    "harga_satuan, jumlah), subtotal, ppn, total. Semua angka uang berupa integer rupiah "
    "tanpa titik. Jika field tidak ada, isi null."
)
