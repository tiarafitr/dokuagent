"""Kirim hasil ekstraksi ke Google Sheets (1 baris per item)."""
import os
import gspread

HEADER = ["nomor_invoice", "tanggal", "nama_penjual", "npwp_penjual", "nama_pembeli",
          "deskripsi", "qty", "harga_satuan", "jumlah", "subtotal", "ppn", "total"]


def append_invoice(d: dict) -> int:
    gc = gspread.service_account(filename=os.getenv("GOOGLE_SA_JSON", "service_account.json"))
    ws = gc.open_by_key(os.environ["SHEET_ID"]).sheet1
    if not ws.row_values(1):
        ws.append_row(HEADER)
    head = [d.get(k) for k in HEADER[:5]]
    tail = [d.get(k) for k in HEADER[9:]]
    rows = [head + [it.get("deskripsi"), it.get("qty"), it.get("harga_satuan"), it.get("jumlah")] + tail
            for it in (d.get("items") or [{}])]
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    return len(rows)
