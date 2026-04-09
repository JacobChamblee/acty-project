#!/usr/bin/env python3
"""
04_acty_bridge.py
-----------------
Integration layer between Acty's ML pipeline and the FSM RAG system.

When anomaly.py or predictive.py flags a fault, this module:
  1. Converts the fault data into a natural-language FSM query
  2. Retrieves relevant FSM sections (wiring, specs, DTCs)
  3. Returns structured context that llm_report.py can inject into its prompt

Also exposes a standalone server mode (--serve) that listens on localhost:7272
so any Acty pipeline component can query it via HTTP without loading the
embedding model multiple times.

Usage as a library:
    from fsm_rag.04_acty_bridge import FsmBridge
    bridge = FsmBridge()
    ctx = bridge.fault_context(dtc="P0300", pids={"RPM": 2800, "COOLANT_TEMP": 95})
    # ctx is a dict: {"fsm_summary": "...", "raw_chunks": [...]}

Usage as a server:
    python3 04_acty_bridge.py --serve
    # Then POST to http://localhost:7272/query  {"question": "...", "top_k": 6}

Usage from command line:
    python3 04_acty_bridge.py --dtc P0300
    python3 04_acty_bridge.py --fault "coolant temp sensor high voltage"
    python3 04_acty_bridge.py --pid-anomaly COOLANT_TEMP --value 108 --threshold 95
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Add project root to path so fsm_rag imports work regardless of cwd
sys.path.insert(0, str(Path(__file__).parent))

MISSING = []
try:
    import httpx
except ImportError:
    MISSING.append("httpx")

if MISSING:
    print(f"[ERROR] pip install {' '.join(MISSING)}")
    sys.exit(1)

# ── DTC → FSM query templates ─────────────────────────────────────────────────
DTC_QUERY_TEMPLATE = (
    "DTC {dtc} diagnosis procedure, possible causes, circuit description, "
    "wiring diagram, sensor specifications, and test values"
)

PID_FAULT_TEMPLATES = {
    "COOLANT_TEMP":        "engine coolant temperature sensor circuit wiring ECT sensor specification",
    "INTAKE_TEMP":         "intake air temperature sensor IAT circuit wiring connector",
    "ENGINE_OIL_TEMP":     "engine oil temperature sensor circuit",
    "MAF":                 "mass air flow sensor circuit wiring MAF specification voltage",
    "O2_B1S1_V":           "oxygen sensor bank 1 sensor 1 circuit wiring heater specification",
    "O2_B1S2_V":           "oxygen sensor bank 1 sensor 2 downstream circuit",
    "LONG_FUEL_TRIM_1":    "long term fuel trim bank 1 rich lean condition diagnosis fuel system",
    "SHORT_FUEL_TRIM_1":   "short term fuel trim diagnosis O2 sensor fuel injector",
    "RPM":                 "crankshaft position sensor CKP circuit wiring ignition system",
    "THROTTLE_POS":        "throttle position sensor TPS circuit wiring calibration specification",
    "INTAKE_MAP":          "manifold absolute pressure sensor MAP circuit wiring specification",
    "TIMING_ADVANCE":      "ignition timing knock sensor circuit camshaft position sensor",
    "FUEL_PRESSURE":       "fuel pressure specification fuel pump circuit wiring regulator",
    "CONTROL_VOLTAGE":     "charging system alternator voltage regulator circuit ECM power supply",
    "CATALYST_TEMP_B1S1":  "catalytic converter temperature sensor circuit oxygen sensor",
    "EGR_COMMANDED":       "EGR valve circuit wiring electronic EGR system",
    "INJECTION_TIMING":    "fuel injector circuit wiring timing specification",
}

# ── bridge class ──────────────────────────────────────────────────────────────
class FsmBridge:
    def __init__(self, top_k: int = 5, model: str = "mistral"):
        self.top_k = top_k
        self.model = model
        self._retriever = None

    def _get_retriever(self):
        if self._retriever is None:
            # Lazy import to allow use as library without loading model at import time
            from sentence_transformers import SentenceTransformer
            import chromadb
            from chromadb.config import Settings
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
            model = SentenceTransformer("BAAI/bge-large-en-v1.5", device=device)
            model._prefix = "Represent this sentence for searching relevant passages: "

            chroma_dir = Path(__file__).parent / "data/chromadb"
            if not chroma_dir.exists():
                raise RuntimeError(
                    f"ChromaDB not found at {chroma_dir}. "
                    "Run 01_parse_fsm.py and 02_embed.py first."
                )
            client = chromadb.PersistentClient(
                path=str(chroma_dir),
                settings=Settings(anonymized_telemetry=False),
            )
            col = client.get_collection("fsm")
            self._retriever = (model, col)
        return self._retriever

    def retrieve(self, question: str) -> list[dict]:
        model, col = self._get_retriever()
        vec = model.encode(
            model._prefix + question,
            normalize_embeddings=True,
        ).tolist()
        results = col.query(
            query_embeddings=[vec],
            n_results=self.top_k,
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
                "relevance": round(1 - dist, 3),
            })
        return sorted(chunks, key=lambda x: x["relevance"], reverse=True)

    def summarize_via_ollama(self, question: str, chunks: list[dict],
                              ollama_host: str = "http://192.168.68.142:11434") -> str:
        context = "\n\n---\n\n".join(
            f"[Page {c['page']} | {c['source']}]\n{c['text']}"
            for c in chunks
        )
        prompt = (
            f"Summarize the FSM information relevant to this fault in 3-5 bullet points. "
            f"Include: circuit path, key connector IDs, spec values, and test procedure.\n\n"
            f"FAULT: {question}\n\nFSM CONTEXT:\n{context}\n\nSUMMARY:"
        )
        try:
            resp = httpx.post(
                f"{ollama_host}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.1, "num_predict": 512}},
                timeout=60,
            )
            return resp.json().get("response", "")
        except Exception as e:
            return f"[Ollama unavailable: {e}]"

    def fault_context(self, dtc: str | None = None, pid: str | None = None,
                       value: float | None = None, pids: dict | None = None,
                       raw_fault: str | None = None) -> dict:
        """
        Main entry point for Acty pipeline components.

        Returns:
            {
                "query":       the FSM query string used,
                "fsm_summary": 3-5 bullet summary from Ollama,
                "raw_chunks":  list of retrieved chunk dicts,
                "top_page":    page number of most relevant chunk,
                "top_source":  PDF name of most relevant chunk,
            }
        """
        # Build query string
        if raw_fault:
            query = raw_fault
        elif dtc:
            query = DTC_QUERY_TEMPLATE.format(dtc=dtc)
        elif pid and pid in PID_FAULT_TEMPLATES:
            query = PID_FAULT_TEMPLATES[pid]
            if value is not None:
                query += f" value={value}"
        elif pid:
            query = f"{pid} sensor circuit wiring specification fault diagnosis"
        else:
            query = "general fault diagnosis procedure"

        chunks = self.retrieve(query)
        summary = self.summarize_via_ollama(query, chunks)

        top = chunks[0] if chunks else {}
        return {
            "query":       query,
            "fsm_summary": summary,
            "raw_chunks":  chunks,
            "top_page":    top.get("page"),
            "top_source":  top.get("source"),
        }

# ── optional HTTP server mode ─────────────────────────────────────────────────
def run_server(port: int = 7272):
    """Lightweight HTTP server so Acty components can query without reloading model."""
    try:
        from http.server import BaseHTTPRequestHandler, HTTPServer
    except ImportError:
        print("[ERROR] Standard library http.server not available")
        sys.exit(1)

    bridge = FsmBridge()
    print(f"[SERVER] Preloading model and ChromaDB...")
    bridge._get_retriever()
    print(f"[SERVER] FSM bridge listening on http://localhost:{port}")
    print(f"[SERVER] POST /query  {{\"question\": \"...\", \"top_k\": 6}}")
    print(f"[SERVER] POST /fault  {{\"dtc\": \"P0300\"}}  or  {{\"pid\": \"MAF\", \"value\": 2.1}}")

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length))

            if self.path == "/query":
                question = body.get("question", "")
                bridge.top_k = body.get("top_k", 5)
                chunks = bridge.retrieve(question)
                result = {
                    "chunks": chunks,
                    "context": "\n\n---\n\n".join(c["text"] for c in chunks),
                }
            elif self.path == "/fault":
                result = bridge.fault_context(
                    dtc=body.get("dtc"),
                    pid=body.get("pid"),
                    value=body.get("value"),
                    raw_fault=body.get("fault"),
                )
            else:
                self.send_response(404)
                self.end_headers()
                return

            payload = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(payload))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt, *args):
            print(f"[{self.address_string()}] {fmt % args}")

    HTTPServer(("localhost", port), Handler).serve_forever()

# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Acty ↔ FSM bridge")
    parser.add_argument("--dtc",          help="DTC code e.g. P0300")
    parser.add_argument("--fault",        help="Raw fault description string")
    parser.add_argument("--pid-anomaly",  help="PID name with anomaly e.g. COOLANT_TEMP")
    parser.add_argument("--value",        type=float, help="Anomalous PID value")
    parser.add_argument("--threshold",    type=float, help="Expected threshold for context")
    parser.add_argument("--serve",        action="store_true", help="Run HTTP server on :7272")
    parser.add_argument("--port",         type=int, default=7272)
    parser.add_argument("--top",          type=int, default=5)
    parser.add_argument("--model",        default="mistral")
    args = parser.parse_args()

    if args.serve:
        run_server(port=args.port)
        return

    bridge = FsmBridge(top_k=args.top, model=args.model)

    if args.dtc:
        result = bridge.fault_context(dtc=args.dtc)
    elif args.pid_anomaly:
        fault_str = None
        if args.threshold and args.value:
            fault_str = (
                f"{args.pid_anomaly} reading {args.value} "
                f"(expected ≤{args.threshold}) — circuit diagnosis"
            )
        result = bridge.fault_context(
            pid=args.pid_anomaly,
            value=args.value,
            raw_fault=fault_str,
        )
    elif args.fault:
        result = bridge.fault_context(raw_fault=args.fault)
    else:
        parser.print_help()
        sys.exit(1)

    print(f"\n[QUERY]   {result['query']}")
    print(f"[SOURCE]  {result['top_source']}  page {result['top_page']}")
    print(f"\n── FSM Summary ─────────────────────────────────────────────")
    print(result["fsm_summary"])
    print(f"────────────────────────────────────────────────────────────")
    print(f"\n[CHUNKS]  {len(result['raw_chunks'])} retrieved")
    for i, c in enumerate(result["raw_chunks"]):
        print(f"  [{i+1}] relevance={c['relevance']}  page={c['page']}  {c['section']!r}")

if __name__ == "__main__":
    main()
