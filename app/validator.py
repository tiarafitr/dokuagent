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


# ---------------------------------------------------------------------------
# Grounding check: apakah yang dikeluarkan model benar-benar ada di dokumen?
# Menangkap halusinasi (angka/barang karangan) yang lolos aturan matematika.
# ---------------------------------------------------------------------------
from difflib import SequenceMatcher


_OCR_FIX = str.maketrans({"o": "0", "O": "0", "i": "1", "I": "1", "l": "1", ":": ".", ";": "."})


def _num_tokens(text: str) -> set[str]:
    """Semua angka yang tercetak di teks OCR, sebagai string digit: '27,000' -> '27000'.

    Memperbaiki salah baca khas OCR di dalam angka: titik dua sebagai pemisah
    ('12.962:500'), huruf o/i/l sebagai 0/1 ('80.081.70o,o0').
    """
    out = set()
    for tok in re.findall(r"[\doOiIl][\doOiIl.,:;]*[\doOiIl]|\d", text):
        if sum(c.isdigit() for c in tok) < 2 and not tok.isdigit():
            continue  # kata biasa seperti 'oli', bukan angka
        tok = tok.translate(_OCR_FIX)
        if re.search(r"[.,]\d{2}$", tok) and not re.search(r"[.,]\d{3}$", tok):
            tok = tok[:-3]  # buang desimal ,00
        digits = re.sub(r"\D", "", tok).lstrip("0")
        if digits:
            out.add(digits)
    return out


def _edit1(a: str, b: str) -> bool:
    """True jika a dan b berbeda paling banyak 1 karakter (ganti/sisip/hapus)."""
    if abs(len(a) - len(b)) > 1:
        return False
    i = j = diff = 0
    while i < len(a) and j < len(b):
        if a[i] != b[j]:
            diff += 1
            if diff > 1:
                return False
            if len(a) > len(b):
                i += 1
                continue
            if len(b) > len(a):
                j += 1
                continue
        i += 1; j += 1
    return diff + (len(a) - i) + (len(b) - j) <= 1


def _printed(value: int, nums: set[str]) -> bool:
    """Angka dianggap tercetak jika sama persis, atau (untuk angka >= 6 digit)
    beda 1 digit karena salah baca OCR. Angka pendek harus sama persis."""
    v = str(abs(int(value)))
    if v in nums:
        return True
    return len(v) >= 6 and any(_edit1(v, n) for n in nums if abs(len(n) - len(v)) <= 1)


def _alnum(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def _desc_found(desc: str, lines: list[str], threshold: float = 0.5) -> bool:
    d = _alnum(desc)
    if len(d) < 3:
        return True
    best = 0.0
    for line in lines:
        m = SequenceMatcher(None, d, line).find_longest_match(0, len(d), 0, len(line))
        best = max(best, m.size / len(d))
    return best >= threshold


def check_grounding(d: dict, ocr_text: str) -> list[str]:
    issues = []
    nums = _num_tokens(ocr_text)
    lines = [_alnum(l) for l in ocr_text.splitlines() if l.strip()]
    for i, it in enumerate(d.get("items") or [], 1):
        if not isinstance(it, dict):
            continue
        if not _desc_found(it.get("deskripsi", ""), lines):
            issues.append(f"items[{i}]: '{it.get('deskripsi')}' tidak ditemukan di dokumen")
        try:
            jumlah = int(it.get("jumlah"))
        except (TypeError, ValueError):
            continue
        if jumlah == 0:
            issues.append(f"items[{i}]: harga 0, cek apakah item gratis atau salah baca")
        elif not _printed(jumlah, nums):
            issues.append(f"items[{i}]: jumlah {jumlah:,} tidak tercetak di dokumen".replace(",", "."))
    for k in ("subtotal", "ppn", "total"):
        v = d.get(k)
        if v not in (None, "", 0):
            try:
                if not _printed(int(v), nums):
                    issues.append(f"{k}: {int(v):,} tidak tercetak di dokumen".replace(",", "."))
            except (TypeError, ValueError):
                pass
    return issues


def _npwp_found(npwp: str, ocr_text: str) -> bool:
    target = re.sub(r"\D", "", str(npwp))
    if len(target) < 15:
        return True  # format salah sudah ditangani validate()
    for line in ocr_text.splitlines():
        digits = re.sub(r"\D", "", line.translate(_OCR_FIX))
        if target in digits:
            return True
        for k in range(0, max(1, len(digits) - len(target) + 2)):
            if _edit1(target, digits[k:k + len(target)]):
                return True
    return False


def check_header_grounding(d: dict, ocr_text: str) -> list[str]:
    """Field header invoice (nama, nomor, NPWP) juga harus tercetak di dokumen."""
    issues = []
    lines = [_alnum(l) for l in ocr_text.splitlines() if l.strip()]
    for k, label in (("nama_penjual", "nama penjual"), ("nama_pembeli", "nama pembeli"),
                     ("nomor_invoice", "nomor invoice")):
        v = d.get(k)
        if v and not _desc_found(v, lines, threshold=0.6):
            issues.append(f"{k}: '{v}' tidak ditemukan di dokumen, kemungkinan dikarang model")
    if d.get("npwp_penjual") and not _npwp_found(d["npwp_penjual"], ocr_text):
        issues.append(f"npwp_penjual: '{d['npwp_penjual']}' tidak tercetak di dokumen")
    return issues


def repair_items(d: dict) -> tuple[dict, list[str]]:
    """Perbaiki qty jika jelas salah tapi harga & jumlah konsisten (mis. kolom qty di kiri
    terbaca sebagai jumlah). qty baru = jumlah / harga, hanya bila hasilnya bulat & wajar."""
    notes, items = [], []
    for i, it in enumerate(d.get("items") or [], 1):
        if isinstance(it, dict):
            try:
                qty, harga, jumlah = int(it["qty"]), int(it["harga_satuan"]), int(it["jumlah"])
                if harga > 0 and jumlah > 0 and qty * harga != jumlah and jumlah % harga == 0:
                    baru = jumlah // harga
                    if 1 <= baru <= 10000:
                        it = {**it, "qty": baru}
                        notes.append(f"items[{i}]: qty diperbaiki otomatis {qty} -> {baru} (jumlah / harga)")
            except (KeyError, TypeError, ValueError):
                pass
        items.append(it)
    return ({**d, "items": items} if "items" in d else d), notes


def quality_issues(q: dict | None) -> list[str]:
    """Peringatan dokumen sulit dibaca. Ambang dikalibrasi dari sedikit contoh, jadi
    hanya peringatan (bukan penolakan)."""
    if not q or q.get("mean_conf") is None:
        return []
    if q["boxes"] == 0:
        return ["dokumen: tidak ada teks yang terbaca"]
    if q["mean_conf"] < 0.75:
        return [f"dokumen: kualitas teks rendah (keyakinan OCR rata-rata {q['mean_conf']:.0%}), "
                "kemungkinan tulisan tangan atau foto buram. Cek SEMUA field secara manual."]
    return []


def grounding_score(d: dict, grounding: list[str]) -> dict:
    """Seberapa banyak hasil ekstraksi yang benar-benar didukung dokumen.
    status: 'ok' | 'review' | 'gagal' (sebagian besar barang/total tidak ada di dokumen)."""
    items = [it for it in (d.get("items") or []) if isinstance(it, dict)]
    bad_items = {int(m.group(1)) for g in grounding
                 for m in [re.match(r"items\[(\d+)\]: .*(tidak ditemukan|tidak tercetak)", g)] if m}
    # barang tanpa angka juga tidak didukung dokumen (jawaban kosong bukan jawaban aman)
    bad_items |= {i for i, it in enumerate(items, 1) if not is_complete_item(it)}
    total_bad = (d.get("total") in (None, "")
                 or any(g.startswith("total:") and "tidak tercetak" in g for g in grounding))
    frac_bad = len(bad_items) / len(items) if items else 1.0
    if not items or frac_bad >= 0.5 or total_bad:
        status = "gagal"
    elif grounding:
        status = "review"
    else:
        status = "ok"
    return {"status": status, "items_tidak_didukung": len(bad_items), "items": len(items),
            "total_tidak_didukung": total_bad, "n_masalah": len(grounding)}


def is_complete_item(it: dict) -> bool:
    try:
        return all(int(it[k]) >= 0 for k in ("qty", "harga_satuan", "jumlah"))
    except (KeyError, TypeError, ValueError):
        return False


def is_complete(d: dict) -> bool:
    """Jawaban lengkap: ada barang, semua barang punya angka, dan total terisi."""
    items = [it for it in (d.get("items") or []) if isinstance(it, dict)]
    return bool(items) and all(is_complete_item(it) for it in items) and d.get("total") not in (None, "")
