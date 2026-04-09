#!/usr/bin/env python3
"""
01_parse_fsm.py
---------------
Parse one or more Field Service Manual PDFs into structured JSON.

Handles three page types automatically:
  - Text pages     : direct text extraction via pymupdf (fast, accurate)
  - Diagram pages  : OCR via pytesseract at 300 DPI (catches wiring diagrams)
  - Table pages    : pdfplumber for connector pinout / spec tables

Output: data/parsed/<stem>.json  (one file per PDF)
        data/parsed/combined.json (all pages merged, used by 02_embed.py)

Usage:
    python3 01_parse_fsm.py path/to/fsm.pdf [path/to/more.pdf ...]
    python3 01_parse_fsm.py --dir /path/to/pdf/folder
    python3 01_parse_fsm.py --reparse   # force re-parse even if JSON exists
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

# ── dependency check ──────────────────────────────────────────────────────────
MISSING = []
try:
    import fitz  # pymupdf
except ImportError:
    MISSING.append("pymupdf")
try:
    import pdfplumber
except ImportError:
    MISSING.append("pdfplumber")
try:
    import pytesseract
    from PIL import Image
except ImportError:
    MISSING.append("pytesseract pillow")

if MISSING:
    print(f"\n[ERROR] Missing packages. Run:\n  pip install {' '.join(MISSING)}\n")
    sys.exit(1)

# ── constants ─────────────────────────────────────────────────────────────────
DATA_DIR   = Path("data/parsed")
MIN_TEXT   = 80      # chars below this → treat page as image/diagram
OCR_DPI    = 300
CHUNK_SIZE = 600     # target tokens per chunk (approx 4 chars/token → ~2400 chars)
OVERLAP    = 80      # overlapping chars between chunks

# ── section header heuristics (FSM-specific) ─────────────────────────────────
SECTION_PATTERNS = [
    re.compile(r"^(SECTION|CHAPTER|PART)\s+\d+", re.IGNORECASE),
    re.compile(r"^\d{1,2}[-–]\d{1,3}\s+[A-Z]"),   # e.g. "5-23 ENGINE CONTROL"
    re.compile(r"^[A-Z]{2,}\s*[-–:]\s*[A-Z]"),     # e.g. "EFI - FUEL SYSTEM"
    re.compile(r"^(WIRING DIAGRAM|CIRCUIT DIAGRAM|HARNESS ROUTING)", re.IGNORECASE),
    re.compile(r"^(CONNECTOR|TERMINAL|PIN)\s+(LAYOUT|DESCRIPTION|CHART)", re.IGNORECASE),
    re.compile(r"^DTC\s+[A-Z]\d+"),                # e.g. "DTC P0300"
]

def detect_section(text: str) -> str | None:
    for line in text.splitlines()[:8]:
        line = line.strip()
        for pat in SECTION_PATTERNS:
            if pat.match(line):
                return line[:120]
    return None

# ── page classification ───────────────────────────────────────────────────────
def classify_page(page_fitz, text: str) -> str:
    """Return 'text', 'ocr', or 'table'."""
    if len(text.strip()) < MIN_TEXT:
        return "ocr"
    # Check if page has significant image coverage
    image_list = page_fitz.get_images(full=True)
    if image_list:
        bbox_area = sum(
            abs((r[2] - r[0]) * (r[3] - r[1]))
            for img in image_list
            for r in [page_fitz.get_image_rects(img[0])[0]]
            if page_fitz.get_image_rects(img[0])
        )
        page_area = page_fitz.rect.width * page_fitz.rect.height
        if bbox_area > page_area * 0.35:
            return "ocr"
    # Check for table-heavy pages (lots of short lines, numbers)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    short_lines = sum(1 for l in lines if len(l) < 40)
    if lines and short_lines / len(lines) > 0.6 and len(lines) > 10:
        return "table"
    return "text"

# ── extractors ────────────────────────────────────────────────────────────────
def extract_text_page(page_fitz) -> str:
    return page_fitz.get_text("text")

def extract_ocr_page(page_fitz) -> str:
    pix = page_fitz.get_pixmap(dpi=OCR_DPI, colorspace=fitz.csGRAY)
    img = Image.frombytes("L", [pix.width, pix.height], pix.samples)
    # Slight upscale helps tesseract on small text
    return pytesseract.image_to_string(img, config="--oem 3 --psm 6")

def extract_table_page(pdf_path: Path, page_num: int) -> str:
    """Use pdfplumber for table-heavy pages — preserves column alignment."""
    lines = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        page = pdf.pages[page_num]
        # Extract tables first
        for table in page.extract_tables():
            for row in table:
                cleaned = [cell.strip() if cell else "" for cell in row]
                lines.append(" | ".join(cleaned))
            lines.append("")  # blank separator
        # Then remaining text
        remaining = page.extract_text() or ""
        if remaining.strip():
            lines.append(remaining)
    return "\n".join(lines)

# ── chunking ──────────────────────────────────────────────────────────────────
def chunk_text(text: str, page_num: int, section: str | None, source: str) -> list[dict]:
    """Split text into overlapping chunks with metadata."""
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    chunk_idx = 0

    while start < len(text):
        end = start + CHUNK_SIZE * 4  # approx chars
        if end >= len(text):
            segment = text[start:]
        else:
            # Try to break at sentence boundary
            for break_char in ["\n\n", "\n", ". ", " "]:
                pos = text.rfind(break_char, start + CHUNK_SIZE * 2, end)
                if pos > start:
                    end = pos + len(break_char)
                    break
            segment = text[start:end]

        if segment.strip():
            chunks.append({
                "id":       f"{source}_p{page_num:04d}_c{chunk_idx:03d}",
                "source":   source,
                "page":     page_num,
                "section":  section,
                "chunk":    chunk_idx,
                "text":     segment.strip(),
                "char_len": len(segment.strip()),
            })
            chunk_idx += 1

        start = end - OVERLAP * 4
        if start >= len(text):
            break

    return chunks

# ── main PDF processor ────────────────────────────────────────────────────────
def parse_pdf(pdf_path: Path, reparse: bool = False) -> list[dict]:
    out_path = DATA_DIR / f"{pdf_path.stem}.json"

    if out_path.exists() and not reparse:
        print(f"  [SKIP] {pdf_path.name} — already parsed ({out_path})")
        with open(out_path) as f:
            return json.load(f)

    print(f"\n[PARSE] {pdf_path.name}")
    doc = fitz.open(str(pdf_path))
    all_chunks = []
    current_section = None

    for i, page in enumerate(doc):
        text = page.get_text("text")
        page_type = classify_page(page, text)

        # Extract based on type
        if page_type == "ocr":
            content = extract_ocr_page(page)
            method = "ocr"
        elif page_type == "table":
            content = extract_table_page(pdf_path, i)
            method = "table"
        else:
            content = text
            method = "text"

        # Update section tracker
        detected = detect_section(content)
        if detected:
            current_section = detected

        chunks = chunk_text(
            text=content,
            page_num=i + 1,
            section=current_section,
            source=pdf_path.stem,
        )
        all_chunks.extend(chunks)

        if (i + 1) % 20 == 0 or i == 0:
            print(f"  Page {i+1:4d}/{len(doc)}  method={method:5s}  "
                  f"chunks_so_far={len(all_chunks)}")

    doc.close()
    print(f"  Done — {len(all_chunks)} chunks from {len(doc)} pages")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(all_chunks, f, indent=2)
    print(f"  Saved → {out_path}")

    return all_chunks

# ── entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Parse FSM PDFs into chunked JSON")
    parser.add_argument("pdfs", nargs="*", help="PDF file paths")
    parser.add_argument("--dir", help="Directory containing PDFs to parse")
    parser.add_argument("--reparse", action="store_true", help="Force re-parse")
    args = parser.parse_args()

    pdf_paths = [Path(p) for p in args.pdfs]
    if args.dir:
        pdf_paths += sorted(Path(args.dir).glob("*.pdf"))
    if not pdf_paths:
        parser.print_help()
        sys.exit(1)

    missing = [p for p in pdf_paths if not p.exists()]
    if missing:
        print(f"[ERROR] Files not found: {missing}")
        sys.exit(1)

    t0 = time.monotonic()
    all_chunks = []
    for pdf_path in pdf_paths:
        chunks = parse_pdf(pdf_path, reparse=args.reparse)
        all_chunks.extend(chunks)

    # Write combined file for embedder
    combined_path = DATA_DIR / "combined.json"
    with open(combined_path, "w") as f:
        json.dump(all_chunks, f, indent=2)

    elapsed = time.monotonic() - t0
    print(f"\n{'='*60}")
    print(f"Total chunks : {len(all_chunks)}")
    print(f"Total time   : {elapsed:.1f}s")
    print(f"Combined     : {combined_path}")
    print(f"\nNext step: python3 02_embed.py")

if __name__ == "__main__":
    main()
