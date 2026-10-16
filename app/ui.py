"""UI review DokuAgent. Jalankan: streamlit run app/ui.py (API harus sudah jalan)."""
import json, os
import pandas as pd
import requests
import streamlit as st

API = os.getenv("API_URL", "http://localhost:8000")
st.set_page_config(page_title="DokuAgent", page_icon="🧾", layout="wide")
st.title("DokuAgent — ekstraksi invoice")

try:
    h = requests.get(f"{API}/health", timeout=3).json()
    st.caption(f"API terhubung · model: {h['model']}")
except requests.RequestException:
    st.error(f"API tidak bisa dihubungi di {API}. Jalankan dulu: uvicorn app.main:app")
    st.stop()

JENIS = {"Invoice pemasok": "invoice", "Struk reimbursement": "nota"}
jenis = st.radio("Jenis dokumen", list(JENIS), horizontal=True)
f = st.file_uploader("Upload dokumen (PDF / JPG / PNG)", type=["pdf", "jpg", "jpeg", "png"])
if f and st.button("Proses", type="primary"):
    with st.spinner("OCR + ekstraksi..."):
        r = requests.post(f"{API}/extract", files={"file": (f.name, f.getvalue())},
                          data={"doc_type": JENIS[jenis]}, timeout=300)
    if r.ok:
        st.session_state.res = r.json()
        st.session_state.file = f.getvalue() if f.type.startswith("image") else None
    else:
        st.error(r.json().get("detail", r.text))

res = st.session_state.get("res")
if res:
    d = res["data"]
    kiri, kanan = st.columns([1, 1])
    with kiri:
        if st.session_state.get("file"):
            st.image(st.session_state.file, caption="Invoice asli")
        with st.expander("Teks hasil OCR"):
            st.text(res["ocr_text"])
    with kanan:
        q = res.get("ocr_quality") or {}
        info = f"Waktu proses: {res['latency_s']} detik"
        if q.get("mean_conf") is not None:
            info += f" · keyakinan OCR: {q['mean_conf']:.0%}"
        if res.get("model"):
            info += f" · model: {res['model']}"
        st.caption(info)
        if res.get("status") == "gagal":
            st.error("**Hasil ekstraksi tidak bisa dipercaya.** Sebagian besar barang atau total "
                     "tidak ditemukan di dokumen (mis. tulisan tangan, layout asing). "
                     "Isi atau koreksi semua field secara manual.")
        if res["issues"]:
            st.warning("Perlu dicek manusia:\n\n- " + "\n- ".join(res["issues"]))
        else:
            st.success("Semua validasi lolos")
        if res.get("doc_type", "invoice") == "invoice":
            c1, c2 = st.columns(2)
            d["nomor_invoice"] = c1.text_input("Nomor invoice", d.get("nomor_invoice") or "")
            d["tanggal"] = c2.text_input("Tanggal (YYYY-MM-DD)", d.get("tanggal") or "")
            d["nama_penjual"] = c1.text_input("Nama penjual", d.get("nama_penjual") or "")
            d["npwp_penjual"] = c2.text_input("NPWP penjual", d.get("npwp_penjual") or "")
            d["nama_pembeli"] = st.text_input("Nama pembeli", d.get("nama_pembeli") or "")
        else:
            st.caption("Struk reimbursement: hanya barang dan total yang diekstrak.")
        items = pd.DataFrame(d.get("items") or [], columns=["deskripsi", "qty", "harga_satuan", "jumlah"])
        items = st.data_editor(items, num_rows="dynamic", use_container_width=True)
        d["items"] = json.loads(items.to_json(orient="records"))
        def angka(v):
            try:
                return int(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                return None
        c1, c2, c3 = st.columns(3)
        # value=None -> kotak kosong, supaya "tidak ada di dokumen" tidak tampil sebagai 0
        d["subtotal"] = c1.number_input("Subtotal", value=angka(d.get("subtotal")), step=1, placeholder="tidak ada")
        d["ppn"] = c2.number_input("PPN", value=angka(d.get("ppn")), step=1, placeholder="tidak ada")
        d["total"] = c3.number_input("Total", value=angka(d.get("total")), step=1, placeholder="tidak ada")
        if st.button("Kirim ke Google Sheets"):
            r = requests.post(f"{API}/push", json={"data": d}, timeout=60)
            if r.ok:
                st.success(f"{r.json()['rows_added']} baris ditambahkan ke Google Sheets")
            else:
                st.error(r.json().get("detail", r.text))
        st.download_button("Download JSON", json.dumps(d, ensure_ascii=False, indent=2),
                           file_name=f"{(d.get('nomor_invoice') or (f.name if f else 'dokumen')).replace('/', '-')}.json")
