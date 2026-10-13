"""Generate invoice sintetis Indonesia: PDF + JPG (versi 'scan') + label JSON.

v2: nama perusahaan & barang dirakit dari kosakata yang DIPISAH antara
train/val (inv_0001-0540) dan test (inv_0541-0600), jadi test set berisi
nama yang tidak pernah dilihat model saat latihan. Layout juga bervariasi.

Pakai: python scripts/generate_invoices.py --n 600 --out data
"""
import argparse, json, os, random
from datetime import date, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from PIL import Image, ImageDraw, ImageFont, ImageFilter

TEST_START = 541  # inv_0541 ke atas = test set

# ---------- kosakata, dipecah dua: [train/val, test] ----------
KATA_USAHA = [
    ["Maju", "Jaya", "Sinar", "Abadi", "Berkah", "Sentosa", "Karya", "Mandiri", "Sumber",
     "Rejeki", "Cahaya", "Nusantara", "Mitra", "Utama", "Bintang", "Timur", "Harapan",
     "Baru", "Sejahtera", "Makmur", "Indah", "Lestari", "Prima", "Global", "Niaga",
     "Surya", "Kencana", "Tunas", "Muda", "Agung", "Perkasa", "Gemilang", "Cipta",
     "Sarana", "Bumi", "Persada", "Mulia", "Langgeng", "Setia", "Kurnia"],
    ["Bahari", "Samudra", "Anugerah", "Wijaya", "Lancar", "Sukses", "Teguh", "Damai",
     "Pelangi", "Mutiara", "Delta", "Garuda", "Rajawali", "Andalas", "Borneo", "Pratama",
     "Sakti", "Megah", "Citra", "Insan"],
]
PREFIX = ["PT", "PT", "CV", "UD", "Toko", "PD"]
BARANG = [  # (nama dasar, varian ukuran, harga min, harga max)
    [("Kertas A4", ["70gsm", "80gsm"], 40000, 65000), ("Tinta Printer", ["Hitam", "Cyan", "664"], 70000, 160000),
     ("Kabel LAN", ["Cat5e /m", "Cat6 /m"], 4000, 9000), ("Semen", ["40kg", "50kg"], 55000, 80000),
     ("Beras Premium", ["5kg", "10kg", "25kg"], 60000, 320000), ("Minyak Goreng", ["1L", "2L", "5L"], 15000, 95000),
     ("Jasa Instalasi", ["Jaringan", "CCTV", "AC"], 300000, 2500000), ("Kursi Kantor", ["Ergonomis", "Lipat"], 300000, 1600000),
     ("Lampu LED", ["9W", "12W", "18W"], 18000, 60000), ("Pipa PVC", ["1/2 inch", "3/4 inch", "1 inch"], 15000, 45000),
     ("Sewa Truk", ["per hari", "per trip"], 600000, 1800000), ("Gula Pasir", ["1kg", "500g"], 9000, 20000),
     ("Cat Tembok", ["5kg", "25kg"], 90000, 950000), ("Baut Baja", ["M8", "M10", "M12"], 1000, 6000),
     ("Air Mineral", ["600ml", "1500ml", "19L"], 3000, 25000), ("Tepung Terigu", ["1kg", "25kg"], 11000, 230000),
     ("Kardus Box", ["40x30x30", "60x40x40"], 4000, 15000), ("Toner Laser", ["85A", "12A"], 250000, 900000)],
    [("Besi Beton", ["8mm", "10mm", "12mm"], 45000, 140000), ("Keramik Lantai", ["40x40", "60x60"], 55000, 180000),
     ("Kopi Bubuk", ["250g", "1kg"], 30000, 160000), ("Jasa Servis", ["Laptop", "Printer"], 150000, 900000),
     ("Kabel NYM", ["2x1.5mm /roll", "3x2.5mm /roll"], 250000, 900000), ("Oli Mesin", ["1L", "4L"], 45000, 280000),
     ("Map Plastik", ["F4", "A4"], 1500, 6000), ("Gas LPG", ["3kg", "12kg"], 20000, 220000),
     ("Ban Motor", ["80/90-14", "90/90-14"], 160000, 350000), ("Sabun Cair", ["500ml", "5L"], 12000, 110000)],
]
KOTA = ["Bandung", "Jakarta", "Surabaya", "Semarang", "Medan", "Bekasi", "Bogor", "Makassar",
        "Yogyakarta", "Malang", "Palembang", "Denpasar", "Tangerang", "Depok", "Pekanbaru"]
JALAN = ["Merdeka", "Sudirman", "Gatot Subroto", "Diponegoro", "Ahmad Yani", "Pahlawan",
         "Asia Afrika", "Veteran", "Hasanuddin", "Pemuda", "Siliwangi", "Gajah Mada"]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]
BULAN3 = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

# variasi label di invoice (layout berbeda antar pemasok)
L_NOMOR = ["No. Invoice", "Nomor Invoice", "No. Faktur", "Invoice No", "No"]
L_TGL = ["Tanggal", "Tgl", "Tanggal Invoice", "Date"]
L_KEPADA = ["Kepada", "Kepada Yth.", "Ditagihkan ke", "Bill To", "Pembeli"]
L_TOTAL = ["TOTAL", "Grand Total", "Total Tagihan", "JUMLAH"]
JUDUL = ["INVOICE", "FAKTUR", "INVOICE / FAKTUR", "TAGIHAN"]


def rupiah(x, gaya):
    s = f"{x:,}".replace(",", ".")
    return {0: f"Rp {s}", 1: f"Rp{s}", 2: f"Rp {s},00", 3: s}[gaya]


def npwp():
    s = "".join(str(random.randint(0, 9)) for _ in range(15))
    return f"{s[0:2]}.{s[2:5]}.{s[5:8]}.{s[8]}-{s[9:12]}.{s[12:15]}"


def nama_usaha(pool):
    kata = random.sample(KATA_USAHA[pool], random.choice([1, 2, 2, 3]))
    return f"{random.choice(PREFIX)} {' '.join(kata)}"


def tgl_text(d):
    return random.choice([d.strftime("%d/%m/%Y"), d.strftime("%d-%m-%Y"), d.strftime("%d.%m.%Y"),
                          f"{d.day} {BULAN[d.month - 1]} {d.year}", f"{d.day:02d} {BULAN3[d.month - 1]} {d.year}"])


def make_label(i):
    pool = 1 if i >= TEST_START else 0
    d = date(2025, 1, 1) + timedelta(days=random.randint(0, 600))
    items = []
    for nm, varian, lo, hi in random.sample(BARANG[pool], random.randint(1, 6)):
        qty = random.choice([random.randint(1, 12), random.randint(1, 60), random.randint(50, 500)])
        harga = random.randrange(lo, hi, 500 if hi > 20000 else 100)
        items.append({"deskripsi": f"{nm} {random.choice(varian)}", "qty": qty,
                      "harga_satuan": harga, "jumlah": qty * harga})
    subtotal = sum(it["jumlah"] for it in items)
    ppn = round(subtotal * 0.11)  # tarif efektif 11%; cek aturan terbaru
    penjual = nama_usaha(pool)
    pembeli = nama_usaha(pool)
    while pembeli == penjual:
        pembeli = nama_usaha(pool)
    no = random.choice([f"INV/{d.year}/{d.month:02d}/{i:04d}", f"INV-{d.year}{d.month:02d}-{i:04d}",
                        f"{i:04d}/FKT/{d.month:02d}/{d.year % 100}", f"SI{d.year % 100}{d.month:02d}{i:05d}"])
    return {"nomor_invoice": no, "tanggal": d.isoformat(), "nama_penjual": penjual,
            "npwp_penjual": npwp(), "nama_pembeli": pembeli, "items": items,
            "subtotal": subtotal, "ppn": ppn, "total": subtotal + ppn}


def lines_of(lab):
    g = random.randint(0, 3)  # gaya penulisan angka untuk invoice ini
    judul_atas = lab["nama_penjual"].upper() if random.random() < 0.7 else lab["nama_penjual"]
    L = [judul_atas,
         f"Jl. {random.choice(JALAN)} No. {random.randint(1, 250)}, {random.choice(KOTA)}",
         f"NPWP: {lab['npwp_penjual']}", "", random.choice(JUDUL),
         f"{random.choice(L_NOMOR):<12}: {lab['nomor_invoice']}",
         f"{random.choice(L_TGL):<12}: {tgl_text(date.fromisoformat(lab['tanggal']))}",
         f"{random.choice(L_KEPADA):<12}: {lab['nama_pembeli']}", ""]
    if random.random() < 0.5:  # dua urutan kolom berbeda
        L.append("No  Deskripsi                       Qty   Harga Satuan       Jumlah")
        row = lambda n, it: (f"{n:<3} {it['deskripsi']:<31} {it['qty']:>4}  "
                             f"{rupiah(it['harga_satuan'], g):>15}  {rupiah(it['jumlah'], g):>16}")
    else:
        L.append("Deskripsi                       Harga Satuan   Qty         Jumlah")
        row = lambda n, it: (f"{it['deskripsi']:<31} {rupiah(it['harga_satuan'], g):>14}  {it['qty']:>4}  "
                             f"{rupiah(it['jumlah'], g):>16}")
    for n, it in enumerate(lab["items"], 1):
        L.append(row(n, it))
    L += ["", f"{'Subtotal':>50} {rupiah(lab['subtotal'], g):>16}",
          f"{'PPN 11%':>50} {rupiah(lab['ppn'], g):>16}",
          f"{random.choice(L_TOTAL):>50} {rupiah(lab['total'], g):>16}", "",
          random.choice(["Hormat kami,", "Terima kasih atas kerja samanya.", "Pembayaran via transfer BCA."]),
          "", "(Bagian Keuangan)"]
    return L


def to_pdf(lines, path):
    c = canvas.Canvas(path, pagesize=A4)
    c.setFont("Courier", 8.5)
    y = 800
    for ln in lines:
        c.drawString(32, y, ln); y -= 14
    c.save()


def load_font(size=18):
    for f in ("/System/Library/Fonts/Menlo.ttc",            # macOS
              "DejaVuSansMono.ttf",                          # Linux
              "C:/Windows/Fonts/consola.ttf"):               # Windows
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def to_jpg(lines, path, font):
    """Simulasi scan/foto: rotasi kecil, blur, noise."""
    img = Image.new("L", (1080, 60 + 26 * len(lines)), 255)
    dr = ImageDraw.Draw(img)
    for k, ln in enumerate(lines):
        dr.text((30, 30 + 26 * k), ln, fill=random.randint(0, 60), font=font)
    img = img.rotate(random.uniform(-2, 2), expand=True, fillcolor=255)
    if random.random() < 0.5:
        img = img.filter(ImageFilter.GaussianBlur(random.uniform(0.3, 1.0)))
    px = img.load()
    for _ in range(img.width * img.height // 200):
        px[random.randrange(img.width), random.randrange(img.height)] = random.randint(0, 255)
    img.convert("RGB").save(path, quality=random.randint(60, 90))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--out", default="data")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    random.seed(a.seed)
    font = load_font()
    for sub in ("raw", "labels"):
        os.makedirs(f"{a.out}/{sub}", exist_ok=True)
    for i in range(1, a.n + 1):
        lab = make_label(i)
        lines = lines_of(lab)
        stem = f"inv_{i:04d}"
        if i % 2:
            to_pdf(lines, f"{a.out}/raw/{stem}.pdf")
        else:
            to_jpg(lines, f"{a.out}/raw/{stem}.jpg", font)
        with open(f"{a.out}/labels/{stem}.json", "w") as f:
            json.dump(lab, f, ensure_ascii=False, indent=2)
    print(f"Selesai: {a.n} invoice di {a.out}/raw, label di {a.out}/labels")
