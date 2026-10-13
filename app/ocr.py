"""Ubah PDF/gambar menjadi teks baris per baris."""
from pathlib import Path
import pdfplumber

_engine = None

def _rapid():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine

def image_to_text(path: str) -> str:
    result, _ = _rapid()(str(path))
    if not result:
        return ""
    # result: [[box, text, score], ...]; kelompokkan kotak per baris berdasarkan posisi y
    boxes = sorted(((b[0][1] + b[2][1]) / 2, b[0][0], t) for b, t, s in result)
    lines, cur, last_y = [], [], None
    for y, x, t in boxes:
        if last_y is not None and abs(y - last_y) > 12:
            lines.append(" ".join(w for _, w in sorted(cur)))
            cur = []
        cur.append((x, t)); last_y = y
    if cur:
        lines.append(" ".join(w for _, w in sorted(cur)))
    return "\n".join(lines)

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

def extract_text(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return pdf_to_text(path)
    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        return image_to_text(path)
    raise ValueError(f"Format tidak didukung: {ext}")
