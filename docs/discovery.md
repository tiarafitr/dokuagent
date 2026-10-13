# Discovery: PT Sumber Makmur

> Catatan: PT Sumber Makmur adalah klien fiktif. Skenario dan angka disusun
> berdasarkan alur kerja umum tim finance distributor di Indonesia.

## Klien
Distributor [jenis barang] di [kota], tim finance [jumlah] orang.

## Masalah saat ini
- Menerima ±500 invoice pemasok per bulan (PDF dari email + foto/scan).
- Diketik manual ke spreadsheet, ±4 menit per invoice (±33 jam kerja/bulan).
- Sering salah ketik di NPWP dan total, baru ketahuan saat rekonsiliasi.

## Field yang dibutuhkan
nomor_invoice, tanggal, nama_penjual, npwp_penjual, nama_pembeli,
items (deskripsi, qty, harga_satuan, jumlah), subtotal, ppn, total

## Batasan
- Data keuangan tidak boleh dikirim ke API pihak ketiga → model jalan lokal.
- Harus bisa jalan di server kantor tanpa GPU besar.
- Hasil akhir harus masuk ke Google Sheets yang sudah dipakai tim.

## Metrik sukses
- Akurasi per field ≥ 90% di test set.
- JSON valid ≥ 98%.
- < 10 detik per invoice.
- Waktu kerja manual turun dari 4 menit ke < 1 menit per invoice (cukup review).

## Di luar cakupan (versi 1)
Faktur pajak e-Faktur resmi, invoice mata uang asing, tulisan tangan.