#!/usr/bin/env python3
"""
03_query.py
-----------
Query the FSM knowledge base.  Retrieves relevant chunks from ChromaDB,
injects them as context, and asks Ollama for an answer.

Usage:
    python3 03_query.py "what gauge wire runs from ECM pin 42 to TPS?"
    python3 03_query.py --top 8 "DTC P0300 diagnosis procedure"
    python3 03_query.py --model deepseek-r1 "trace the coolant temp sensor circuit"
    python3 03_query.py --show-chunks "ignition coil wiring harness connector"
    python3 03_query.py --interactive   # REPL mode
    python3 03_query.py --acty          # pipe mode: read question from stdin
"""

import argparse
import os
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
    import httpx
except ImportError:
    MISSING.append("httpx")

if MISSING:
    print(f"[ERROR] pip install {' '.join(MISSING)}")
    sys.exit(1)

# ── config ────────────────────────────────────────────────────────────────────
EMBED_MODEL  = "BAAI/bge-large-en-v1.5"
CHROMA_DIR   = Path("data/chromadb")
COLLECTION   = "fsm"
OLLAMA_HOST  = os.environ.get("OLLAMA_HOST", "http://192.168.68.138:11434")   # your R7525
DEFAULT_MODEL = "mistral"
TOP_K        = 6
MAX_CTX_CHARS = 12_000   # stay within Ollama context window

SYSTEM_PROMPT = """You are a senior Toyota field service technician with 20+ years of experience.
You have access to the vehicle's Field Service Manual (FSM) and wiring diagrams.

When answering:
- Be precise and cite specific connector IDs, wire colors, and pin numbers when available in the provided context
- If tracing a circuit, walk through it step by step (power source → fuse → relay → component → ground)
- If a DTC is mentioned, provide the full diagnostic tree: possible causes, check sequence, specification values
- If the context doesn't contain enough information, say so clearly rather than guessing
- Format connector pinout tables using | separators for readability
- Use metric units (ohms, volts, kPa) matching the FSM standard
"""

# ── singleton loader (avoids reloading model in interactive mode) ─────────────
_model_cache = {}

def get_model():
    if "model" not in _model_cache:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model_cache["model"] = SentenceTransformer(EMBED_MODEL, device=device)
        _model_cache["model"]._prefix = "Represent this sentence for searching relevant passages: "
    return _model_cache["model"]

def get_collection():
    if not CHROMA_DIR.exists():
        print(f"[ERROR] ChromaDB not found at {CHROMA_DIR}")
        print("  Run: python3 01_parse_fsm.py your_manual.pdf && python3 02_embed.py")
        sys.exit(1)
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    col = client.get_collection(COLLECTION)
    if col.count() == 0:
        print("[ERROR] Collection is empty — run 02_embed.py first")
        sys.exit(1)
    return col

# ── retrieval ─────────────────────────────────────────────────────────────────
def retrieve(question: str, top_k: int = TOP_K, source_filter: str | None = None) -> list[dict]:
    model = get_model()
    col   = get_collection()

    query_vec = model.encode(
        model._prefix + question,
        normalize_embeddings=True,
    ).tolist()

    where = {"source": source_filter} if source_filter else None
    results = col.query(
        query_embeddings=[query_vec],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text":      doc,
            "source":    meta.get("source", ""),
            "page":      meta.get("page", 0),
            "section":   meta.get("section", ""),
            "relevance": round(1 - dist, 3),   # cosine distance → similarity
        })

    # Sort by relevance descending
    chunks.sort(key=lambda x: x["relevance"], reverse=True)
    return chunks

def format_context(chunks: list[dict], max_chars: int = MAX_CTX_CHARS) -> str:
    parts = []
    used = 0
    for i, c in enumerate(chunks):
        header = (
            f"[FSM Excerpt {i+1} | "
            f"Source: {c['source']} | "
            f"Page: {c['page']}"
            + (f" | Section: {c['section']}" if c['section'] else "")
            + f" | Relevance: {c['relevance']}]"
        )
        block = f"{header}\n{c['text']}"
        if used + len(block) > max_chars:
            remaining = max_chars - used
            if remaining > 200:
                parts.append(block[:remaining] + "\n[...truncated]")
            break
        parts.append(block)
        used += len(block)
    return "\n\n---\n\n".join(parts)

# ── ollama call ───────────────────────────────────────────────────────────────
def ask_ollama(question: str, context: str, model: str = DEFAULT_MODEL, stream: bool = True) -> str:
    prompt = f"""Use the following FSM (Field Service Manual) excerpts to answer the question.
Only use information from the provided excerpts. If the answer isn't in the excerpts, say so.

{context}

QUESTION: {question}

ANSWER:"""

    payload = {
        "model":  model,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": stream,
        "options": {
            "temperature": 0.1,    # low temp for technical precision
            "num_predict": 2048,
        },
    }

    try:
        if stream:
            answer_parts = []
            with httpx.stream("POST", f"{OLLAMA_HOST}/api/generate",
                              json=payload, timeout=120) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line: continue
                    data = json.loads(line)
                    token = data.get("response", "")
                    print(token, end="", flush=True)
                    answer_parts.append(token)
                    if data.get("done"):
                        break
            print()  # newline after streaming
            return "".join(answer_parts)
        else:
            resp = httpx.post(f"{OLLAMA_HOST}/api/generate",
                              json={**payload, "stream": False}, timeout=120)
            resp.raise_for_status()
            return resp.json()["response"]

    except httpx.ConnectError:
        return (f"[ERROR] Cannot reach Ollama at {OLLAMA_HOST}\n"
                f"  Check: curl {OLLAMA_HOST}/api/tags")
    except httpx.HTTPStatusError as e:
        return f"[ERROR] Ollama HTTP {e.response.status_code}: {e.response.text}"

# ── main query function ───────────────────────────────────────────────────────
def query(question: str, top_k: int = TOP_K, model: str = DEFAULT_MODEL,
          show_chunks: bool = False, source: str | None = None) -> str:
    print(f"\n[RETRIEVE] Searching FSM for: {question!r}")
    t0 = time.monotonic()
    chunks = retrieve(question, top_k=top_k, source_filter=source)
    print(f"[RETRIEVE] Got {len(chunks)} chunks in {time.monotonic()-t0:.2f}s")

    if show_chunks:
        print("\n── Retrieved Chunks ────────────────────────────────────────")
        for i, c in enumerate(chunks):
            print(f"\n[{i+1}] Source={c['source']} Page={c['page']} "
                  f"Relevance={c['relevance']} Section={c['section']!r}")
            print(c['text'][:400] + ("..." if len(c['text']) > 400 else ""))
        print("────────────────────────────────────────────────────────────\n")

    context = format_context(chunks)
    print(f"\n[{model}] Generating answer...\n")
    answer = ask_ollama(question, context, model=model)
    return answer

# ── entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Query FSM knowledge base via Ollama",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("question", nargs="?", help="Question to ask")
    parser.add_argument("--top", "-k", type=int, default=TOP_K,
        help=f"Number of chunks to retrieve (default: {TOP_K})")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL,
        help=f"Ollama model (default: {DEFAULT_MODEL})")
    parser.add_argument("--show-chunks", action="store_true",
        help="Print retrieved FSM excerpts before the answer")
    parser.add_argument("--source", help="Restrict search to one PDF source name")
    parser.add_argument("--interactive", "-i", action="store_true",
        help="Launch interactive REPL")
    parser.add_argument("--acty", action="store_true",
        help="Pipe mode: read question from stdin, write answer to stdout")
    args = parser.parse_args()

    # Preload model and collection once
    print(f"[INIT] Loading embedding model and ChromaDB...")
    get_model()
    get_collection()
    print(f"[INIT] Ready ✓\n")

    if args.acty:
        question = sys.stdin.read().strip()
        answer = query(question, top_k=args.top, model=args.model,
                       show_chunks=False, source=args.source)
        print(answer)
        return

    if args.interactive:
        print(f"FSM Query REPL  |  model={args.model}  |  top_k={args.top}")
        print("Type 'quit' or Ctrl+C to exit\n")
        while True:
            try:
                q = input("Question: ").strip()
                if not q: continue
                if q.lower() in ("quit", "exit", "q"): break
                query(q, top_k=args.top, model=args.model,
                      show_chunks=args.show_chunks, source=args.source)
                print()
            except (KeyboardInterrupt, EOFError):
                print("\nBye.")
                break
        return

    if not args.question:
        parser.print_help()
        sys.exit(1)

    query(args.question, top_k=args.top, model=args.model,
          show_chunks=args.show_chunks, source=args.source)

if __name__ == "__main__":
    main()
