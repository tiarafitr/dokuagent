"""Generate invoice sintetis Indonesia: PDF + PNG (versi 'scan') + label JSON.
Pakai: python scripts/generate_invoices.py --n 600 --out data
"""
import argparse, json, random, os
from datetime import date, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from PIL import Image, ImageDraw, ImageFont, ImageFilter

PREFIX = ["PT", "CV", "UD", "PT"]
NAMA = ["Maju Jaya", "Sinar Abadi", "Berkah Sentosa", "Karya Mandiri", "Sumber Rejeki",
        "Cahaya Nusantara", "Mitra Utama", "Bintang Timur", "Harapan Baru", "Sejahtera Makmur",
        "Indah Lestari", "Prima Teknik", "Global Niaga", "Surya Kencana", "Tunas Muda"]
KOTA = ["Bandung", "Jakarta", "Surabaya", "Semarang", "Medan", "Bekasi", "Bogor", "Makassar"]
BARANG = [("Kertas A4 80gsm", 45000, 60000), ("Tinta Printer Hitam", 80000, 150000),
          ("Kabel LAN Cat6 /m", 5000, 9000), ("Semen 50kg", 60000, 75000),
          ("Beras Premium 5kg", 65000, 85000), ("Minyak Goreng 2L", 30000, 40000),
          ("Jasa Instalasi Jaringan", 500000, 2500000), ("Kursi Kantor", 450000, 1500000),
          ("Lampu LED 12W", 25000, 45000), ("Pipa PVC 3/4 inch", 20000, 35000),
          ("Sewa Truk per hari", 750000, 1500000), ("Gula Pasir 1kg", 15000, 19000)]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]


def rupiah(x):  # 1250000 -> "Rp 1.250.000"
    return "Rp " + f"{x:,}".replace(",", ".")


def npwp():
    d = [random.randint(0, 9) for _ in range(15)]
    s = "".join(map(str, d))
    return f"{s[0:2]}.{s[2:5]}.{s[5:8]}.{s[8]}-{s[9:12]}.{s[12:15]}"


def tgl_text(d):  # variasi format tanggal, label tetap ISO
    return random.choice([d.strftime("%d/%m/%Y"), d.strftime("%d-%m-%Y"),
                          f"{d.day} {BULAN[d.month - 1]} {d.year}"])


def make_label(i):
    d = date(2025, 1, 1) + timedelta(days=random.randint(0, 600))
    items = []
    for nm, lo, hi in random.sample(BARANG, random.randint(1, 5)):
        qty = random.randint(1, 50)
        harga = random.randrange(lo, hi, 500)
        items.append({"deskripsi": nm, "qty": qty, "harga_satuan": harga, "jumlah": qty * harga})
    subtotal = sum(it["jumlah"] for it in items)
    ppn = round(subtotal * 0.11)  # tarif efektif PPN 11%; sesuaikan bila aturan berubah
    return {
        "nomor_invoice": f"INV/{d.year}/{d.month:02d}/{i:04d}",
        "tanggal": d.isoformat(),
        "nama_penjual": f"{random.choice(PREFIX)} {random.choice(NAMA)}",
        "npwp_penjual": npwp(),
        "nama_pembeli": f"{random.choice(PREFIX)} {random.choice(NAMA)}",
        "items": items, "subtotal": subtotal, "ppn": ppn, "total": subtotal + ppn,
    }


def lines_of(lab):
    """Teks invoice baris per baris (dipakai untuk PDF dan PNG)."""
    L = [lab["nama_penjual"].upper(), f"Jl. Merdeka No. {random.randint(1,200)}, {random.choice(KOTA)}",
         f"NPWP: {lab['npwp_penjual']}", "", "INVOICE",
         f"No. Invoice : {lab['nomor_invoice']}",
         f"Tanggal     : {tgl_text(date.fromisoformat(lab['tanggal']))}",
         f"Kepada      : {lab['nama_pembeli']}", "",
         "No  Deskripsi                     Qty   Harga Satuan      Jumlah"]
    for n, it in enumerate(lab["items"], 1):
        L.append(f"{n:<3} {it['deskripsi']:<29} {it['qty']:>3}   {rupiah(it['harga_satuan']):>14}  {rupiah(it['jumlah']):>14}")
    L += ["", f"{'Subtotal':>52} {rupiah(lab['subtotal']):>14}",
          f"{'PPN 11%':>52} {rupiah(lab['ppn']):>14}",
          f"{'TOTAL':>52} {rupiah(lab['total']):>14}", "", "Hormat kami,", "", "(Bagian Keuangan)"]
    return L


def to_pdf(lines, path):
    c = canvas.Canvas(path, pagesize=A4)
    c.setFont("Courier", 9)
    y = 800
    for ln in lines:
        c.drawString(40, y, ln); y -= 14
    c.save()


def to_png(lines, path):
    """Simulasi hasil scan/foto: rotasi kecil, blur, noise."""
    font = None
    for f in ("/System/Library/Fonts/Menlo.ttc",            # macOS
              "DejaVuSansMono.ttf",                          # Linux
              "C:/Windows/Fonts/consola.ttf"):               # Windows
        try:
            font = ImageFont.truetype(f, 18); break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default(size=18)
    img = Image.new("L", (1000, 60 + 26 * len(lines)), 255)
    dr = ImageDraw.Draw(img)
    for k, ln in enumerate(lines):
        dr.text((30, 30 + 26 * k), ln, fill=random.randint(0, 60), font=font)
    img = img.rotate(random.uniform(-2, 2), expand=True, fillcolor=255)
    if random.random() < 0.5:
        img = img.filter(ImageFilter.GaussianBlur(random.uniform(0.3, 1.0)))
    px = img.load()
    for _ in range(img.width * img.height // 200):  # bintik noise
        px[random.randrange(img.width), random.randrange(img.height)] = random.randint(0, 255)
    img.convert("RGB").save(path, quality=random.randint(60, 90))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--out", default="data")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    random.seed(a.seed)
    for sub in ("raw", "labels"):
        os.makedirs(f"{a.out}/{sub}", exist_ok=True)
    for i in range(1, a.n + 1):
        lab = make_label(i)
        lines = lines_of(lab)
        stem = f"inv_{i:04d}"
        if i % 2:  # setengah PDF digital, setengah gambar 'scan'
            to_pdf(lines, f"{a.out}/raw/{stem}.pdf")
        else:
            to_png(lines, f"{a.out}/raw/{stem}.jpg")
        json.dump(lab, open(f"{a.out}/labels/{stem}.json", "w"), ensure_ascii=False, indent=2)
    print(f"Selesai: {a.n} invoice di {a.out}/raw, label di {a.out}/labels")
