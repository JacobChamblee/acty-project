#!/usr/bin/env python3
"""
02_embed.py
-----------
Embed parsed FSM chunks into a persistent ChromaDB vector database.

Uses BAAI/bge-large-en-v1.5 — runs on your RTX 3060, ~12GB VRAM,
processes ~500 chunks/min on GPU.

On first run:
  - Downloads the embedding model (~1.3GB, cached in ~/.cache/huggingface)
  - Creates data/chromadb/   (persistent vector store)
  - Embeds all chunks from data/parsed/combined.json

Subsequent runs skip already-embedded chunks (idempotent).

Usage:
    python3 02_embed.py                          # embed all from combined.json
    python3 02_embed.py --source rm_section      # embed only one PDF's chunks
    python3 02_embed.py --reembed                # drop and rebuild the collection
    python3 02_embed.py --stats                  # show collection stats and exit
"""

import argparse
import json
import sys
import time
from pathlib import Path

MISSING = []
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    MISSING.append("sentence-transformers")
try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    MISSING.append("chromadb")
try:
    import torch
except ImportError:
    MISSING.append("torch")

if MISSING:
    print(f"\n[ERROR] Missing packages. Run:\n  pip install {' '.join(MISSING)}\n")
    sys.exit(1)

# ── config ────────────────────────────────────────────────────────────────────
EMBED_MODEL  = "BAAI/bge-large-en-v1.5"
CHROMA_DIR   = Path("data/chromadb")
COMBINED_JSON = Path("data/parsed/combined.json")
COLLECTION   = "fsm"
BATCH_SIZE   = 64     # tune down to 32 if 3060 OOMs

# ── helpers ───────────────────────────────────────────────────────────────────
def get_device():
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"[GPU] {name}  ({vram:.1f} GB VRAM)")
        return "cuda"
    print("[CPU] No GPU found — embedding will be slow but works")
    return "cpu"

def load_model(device: str) -> SentenceTransformer:
    print(f"[EMBED] Loading {EMBED_MODEL}...")
    model = SentenceTransformer(EMBED_MODEL, device=device)
    # BGE models benefit from prepending this prefix for retrieval
    model._acty_prefix = "Represent this sentence for searching relevant passages: "
    print(f"[EMBED] Model loaded ✓  dim={model.get_sentence_embedding_dimension()}")
    return model

def get_collection(reset: bool = False):
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    if reset:
        try:
            client.delete_collection(COLLECTION)
            print(f"[DB] Collection '{COLLECTION}' dropped")
        except Exception:
            pass
    col = client.get_or_create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    return col

def embed_batch(model, texts: list[str]) -> list[list[float]]:
    prefixed = [model._acty_prefix + t for t in texts]
    vecs = model.encode(
        prefixed,
        batch_size=BATCH_SIZE,
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vecs.tolist()

# ── main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Embed FSM chunks into ChromaDB")
    parser.add_argument("--source", help="Only embed chunks from this source name")
    parser.add_argument("--reembed", action="store_true", help="Drop and rebuild collection")
    parser.add_argument("--stats", action="store_true", help="Show stats and exit")
    args = parser.parse_args()

    col = get_collection(reset=args.reembed)

    if args.stats:
        count = col.count()
        if count == 0:
            print("[DB] Collection is empty — run 02_embed.py first")
        else:
            sample = col.peek(5)
            sources = set(m.get("source","?") for m in sample["metadatas"])
            print(f"\n[DB] Collection: '{COLLECTION}'")
            print(f"     Vectors    : {count}")
            print(f"     Sources    : {sources} (sample)")
        return

    if not COMBINED_JSON.exists():
        print(f"[ERROR] {COMBINED_JSON} not found — run 01_parse_fsm.py first")
        sys.exit(1)

    with open(COMBINED_JSON) as f:
        chunks = json.load(f)

    if args.source:
        chunks = [c for c in chunks if c["source"] == args.source]
        print(f"[FILTER] Source '{args.source}' → {len(chunks)} chunks")

    # Skip already-embedded IDs
    existing_ids = set(col.get(include=[])["ids"])
    chunks = [c for c in chunks if c["id"] not in existing_ids]
    print(f"[EMBED] {len(chunks)} chunks to embed ({len(existing_ids)} already in DB)")

    if not chunks:
        print("[DONE] Nothing to embed.")
        return

    device = get_device()
    model  = load_model(device)

    t0 = time.monotonic()
    total = len(chunks)
    processed = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch = chunks[batch_start : batch_start + BATCH_SIZE]
        texts     = [c["text"] for c in batch]
        ids       = [c["id"]   for c in batch]
        metadatas = [
            {
                "source":  c["source"],
                "page":    c["page"],
                "section": c.get("section") or "",
                "chunk":   c["chunk"],
            }
            for c in batch
        ]

        embeddings = embed_batch(model, texts)

        col.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        processed += len(batch)
        elapsed = time.monotonic() - t0
        rate = processed / elapsed
        eta  = (total - processed) / rate if rate > 0 else 0
        print(f"  {processed:5d}/{total}  {rate:.0f} chunks/s  ETA {eta:.0f}s")

    elapsed = time.monotonic() - t0
    print(f"\n[DONE] Embedded {processed} chunks in {elapsed:.1f}s")
    print(f"[DB]   Collection '{COLLECTION}' now has {col.count()} vectors")
    print(f"[DB]   Stored at: {CHROMA_DIR.resolve()}")
    print(f"\nNext step: python3 03_query.py \"your question here\"")

if __name__ == "__main__":
    main()
