import os
#!/usr/bin/env python3
"""
00_setup.py
-----------
One-time setup: checks system deps, installs Python packages,
pulls Ollama models, and verifies your RTX 3060 is visible.

Run once before anything else:
    python3 00_setup.py
"""

import subprocess
import sys

def run(cmd, check=True):
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=False)
    if check and result.returncode != 0:
        print(f"  [WARN] Command exited {result.returncode}")
    return result.returncode == 0

def check_import(pkg, import_name=None):
    name = import_name or pkg
    try:
        __import__(name)
        return True
    except ImportError:
        return False

print("=" * 60)
print("  FSM RAG Pipeline — Setup")
print("=" * 60)

# ── system packages (Tesseract OCR) ──────────────────────────────────────────
print("\n[1] System packages")
result = subprocess.run("tesseract --version", shell=True, capture_output=True)
if result.returncode != 0:
    print("  Installing tesseract-ocr...")
    run("sudo apt-get install -y tesseract-ocr tesseract-ocr-eng")
else:
    ver = result.stdout.decode().splitlines()[0]
    print(f"  tesseract: {ver} ✓")

# ── Python packages ───────────────────────────────────────────────────────────
print("\n[2] Python packages")

packages = [
    ("pymupdf",              "fitz"),
    ("pdfplumber",           "pdfplumber"),
    ("pytesseract",          "pytesseract"),
    ("Pillow",               "PIL"),
    ("sentence-transformers","sentence_transformers"),
    ("chromadb",             "chromadb"),
    ("httpx",                "httpx"),
    ("torch",                "torch"),
]

to_install = []
for pip_name, import_name in packages:
    if check_import(pip_name, import_name):
        print(f"  {pip_name}: ✓")
    else:
        print(f"  {pip_name}: MISSING — will install")
        to_install.append(pip_name)

if to_install:
    print(f"\n  Installing: {' '.join(to_install)}")
    run(f"{sys.executable} -m pip install {' '.join(to_install)} --break-system-packages")
else:
    print("  All packages present ✓")

# ── GPU check ─────────────────────────────────────────────────────────────────
print("\n[3] GPU / CUDA")
try:
    import torch
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"  GPU:  {name}")
        print(f"  VRAM: {vram:.1f} GB ✓")
        if vram < 8:
            print("  [WARN] <8GB VRAM — reduce BATCH_SIZE in 02_embed.py to 16")
    else:
        print("  [WARN] No CUDA GPU — embedding will use CPU (slower but works)")
except Exception as e:
    print(f"  [WARN] Could not check GPU: {e}")

# ── Ollama check ──────────────────────────────────────────────────────────────
print("\n[4] Ollama")
OLLAMA_HOST = "os.environ.get("OLLAMA_HOST", "http://192.168.68.138:11434")"
try:
    import httpx
    resp = httpx.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
    models = [m["name"] for m in resp.json().get("models", [])]
    print(f"  Ollama reachable at {OLLAMA_HOST} ✓")
    print(f"  Models available: {models or '(none)'}")
    if not models:
        print("\n  Pulling recommended models (this takes a few minutes)...")
        for model in ["mistral", "llama3.1:8b"]:
            run(f"ollama pull {model}", check=False)
    elif "mistral" not in " ".join(models):
        print("\n  Pulling mistral (recommended)...")
        run("ollama pull mistral", check=False)
except Exception as e:
    print(f"  [WARN] Cannot reach Ollama at {OLLAMA_HOST}: {e}")
    print(f"  Make sure Ollama is running on your R7525 and accessible on LAN")

# ── directory structure ───────────────────────────────────────────────────────
print("\n[5] Directories")
import os
for d in ["data/parsed", "data/chromadb"]:
    os.makedirs(d, exist_ok=True)
    print(f"  {d}/ ✓")

# ── done ──────────────────────────────────────────────────────────────────────
print(f"""
{'='*60}
  Setup complete.

  WORKFLOW:
    1. python3 01_parse_fsm.py your_fsm.pdf [more.pdf ...]
       → Parses PDFs, OCRs diagrams, saves data/parsed/combined.json

    2. python3 02_embed.py
       → Embeds all chunks into ChromaDB using RTX 3060

    3. python3 03_query.py "your question"
       → Queries the FSM and answers via Ollama

    4. python3 03_query.py --interactive
       → REPL for rapid questioning

    5. python3 04_acty_bridge.py --dtc P0300
       → Acty-aware fault lookup with structured output

    ACTY PIPELINE INTEGRATION:
    Start the bridge server once, then call from anywhere:
       python3 04_acty_bridge.py --serve
       curl -s localhost:7272/fault -d '{{"dtc":"P0300"}}'
{'='*60}
""")
