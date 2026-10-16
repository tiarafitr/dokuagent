"""Ubah PDF/gambar menjadi teks baris per baris."""
import math
import statistics
from pathlib import Path
import pdfplumber

_engine = None

def _rapid():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine

def _ocr_image(path: str):
    """OCR gambar lalu susun ulang kotak teks menjadi baris.

    Gambar scan sering miring 1-3 derajat. Kotak teks diluruskan dulu (deskew
    berdasarkan kemiringan rata-rata kotak), baru dikelompokkan per baris,
    supaya kolom kanan (angka) tidak tercampur dengan baris lain.
    """
    result, _ = _rapid()(str(path))
    if not result:
        return "", []
    angles, heights = [], []
    for box, _t, _s in result:
        (x0, y0), (x1, y1), _, (x3, y3) = box
        if x1 - x0 > 30:
            angles.append(math.atan2(y1 - y0, x1 - x0))
        heights.append(math.hypot(x3 - x0, y3 - y0))
    ang = statistics.median(angles) if angles else 0.0
    h = statistics.median(heights) if heights else 20.0
    cos, sin = math.cos(ang), math.sin(ang)
    words = []
    for box, text, _s in result:
        cx = sum(p[0] for p in box) / 4
        cy = sum(p[1] for p in box) / 4
        words.append((-cx * sin + cy * cos, cx * cos + cy * sin, text))  # (y lurus, x lurus, teks)
    words.sort()
    rows = []
    for y, x, t in words:
        if rows and abs(y - rows[-1]["y"]) < 0.5 * h:
            r = rows[-1]
            r["items"].append((x, t))
            r["y"] = (r["y"] * (len(r["items"]) - 1) + y) / len(r["items"])
        else:
            rows.append({"y": y, "items": [(x, t)]})
    text = "\n".join(" ".join(t for _, t in sorted(r["items"])) for r in rows)
    return text, [float(sc) for _b, _t, sc in result]


def _quality(scores) -> dict:
    """Ringkasan keyakinan OCR. mean_conf rendah = dokumen sulit dibaca (buram, tulisan tangan)."""
    if not scores:
        return {"boxes": 0, "mean_conf": 0.0, "low_ratio": 1.0}
    return {"boxes": len(scores),
            "mean_conf": round(statistics.mean(scores), 3),
            "low_ratio": round(sum(sc < 0.8 for sc in scores) / len(scores), 3)}


def image_to_text(path: str) -> str:
    return _ocr_image(path)[0]




def pdf_to_text(path: str) -> str:
    with pdfplumber.open(path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    if len(text.strip()) < 30:  # PDF hasil scan (tanpa layer teks) -> OCR
        from PIL import Image  # noqa
        pages = []
        with pdfplumber.open(path) as pdf:
            for i, p in enumerate(pdf.pages):
                img_path = f"/tmp/_page_{i}.png"
                p.to_image(resolution=200).save(img_path)
                pages.append(image_to_text(img_path))
        text = "\n".join(pages)
    return text

def extract_text_with_quality(path: str):
    """Seperti extract_text, plus ringkasan kualitas OCR (untuk deteksi dokumen sulit dibaca)."""
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        text = pdf_to_text(path)
        with pdfplumber.open(path) as pdf:
            digital = len("".join((p.extract_text() or "") for p in pdf.pages).strip()) >= 30
        if digital:
            return text, {"boxes": len(text.split()), "mean_conf": 1.0, "low_ratio": 0.0}
        return text, {"boxes": len(text.split()), "mean_conf": None, "low_ratio": None}
    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        text, scores = _ocr_image(path)
        return text, _quality(scores)
    raise ValueError(f"Format tidak didukung: {ext}")


def extract_text(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return pdf_to_text(path)
    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        return image_to_text(path)
    raise ValueError(f"Format tidak didukung: {ext}")
