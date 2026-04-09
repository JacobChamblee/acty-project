# FSM RAG Pipeline

Local AI search over your vehicle's Field Service Manual.  
Runs entirely on your home server — RTX 3060, Ollama, no cloud.

---

## Files

| File | Purpose |
|---|---|
| `00_setup.py` | One-time install check + Ollama model pull |
| `01_parse_fsm.py` | PDF → chunked JSON (text + OCR + tables) |
| `02_embed.py` | Chunks → ChromaDB vectors (runs on 3060) |
| `03_query.py` | Ask questions, get answers from Ollama |
| `04_acty_bridge.py` | Acty pipeline integration + HTTP server mode |
| `requirements.txt` | Python dependencies |

---

## Quick Start

```bash
# 1. One-time setup
python3 00_setup.py

# 2. Parse your FSM PDFs (can pass multiple)
python3 01_parse_fsm.py ~/Documents/RM_section_EF.pdf ~/Documents/RM_wiring.pdf

# 3. Embed (uses RTX 3060, ~500 chunks/min)
python3 02_embed.py

# 4. Query
python3 03_query.py "what wire color runs from ECM pin 42 to the TPS?"
python3 03_query.py --interactive   # REPL mode
python3 03_query.py --show-chunks "DTC P0300 misfire diagnosis"
```

---

## Query Examples

```bash
# Wiring / connector lookup
python3 03_query.py "trace the circuit from battery to fuel injector bank 1"
python3 03_query.py "connector C219 pin layout and wire colors"

# DTC diagnosis
python3 03_query.py "DTC P0171 system too lean bank 1 diagnosis steps"
python3 03_query.py --model deepseek-r1 "DTC P0300 random misfire complete diagnosis tree"

# Specs
python3 03_query.py "coolant temperature sensor resistance specification at 80 degrees C"
python3 03_query.py "throttle position sensor output voltage at closed throttle"

# Use a faster/different model
python3 03_query.py --model llama3.1:8b "ignition timing advance specification at idle"
```

---

## Acty Integration

### One-off fault lookup
```bash
python3 04_acty_bridge.py --dtc P0300
python3 04_acty_bridge.py --pid-anomaly COOLANT_TEMP --value 108 --threshold 95
python3 04_acty_bridge.py --fault "long term fuel trim bank 1 at -12 percent"
```

### Persistent server (start once, query from Acty pipeline)
```bash
python3 04_acty_bridge.py --serve &

# From Acty's llm_report.py or anomaly.py:
curl -s localhost:7272/fault \
  -H "Content-Type: application/json" \
  -d '{"dtc": "P0300"}'

curl -s localhost:7272/query \
  -H "Content-Type: application/json" \
  -d '{"question": "P0171 bank 1 lean condition wiring diagram", "top_k": 6}'
```

### Python library usage in existing Acty code
```python
# In llm_report.py, after anomaly.py flags something:
from fsm_rag.acty_bridge import FsmBridge

bridge = FsmBridge()

# Get FSM context for a DTC
ctx = bridge.fault_context(dtc="P0300")
fsm_notes = ctx["fsm_summary"]   # inject into your LLM prompt

# Get FSM context for a PID anomaly
ctx = bridge.fault_context(pid="LONG_FUEL_TRIM_1", value=-12.4)
```

---

## Hardware Notes

- **Parsing** (`01_parse_fsm.py`): CPU-bound, ~2-5 min per 500-page PDF
- **Embedding** (`02_embed.py`): GPU-bound, ~500 chunks/min on RTX 3060 (12GB)
- **Query** (`03_query.py`): Embedding query is instant; Ollama LLM response is 5-20s depending on model
- **Storage**: ChromaDB uses ~1MB per 1000 chunks; a full FSM is typically 5,000-20,000 chunks

## Model Recommendations

| Use case | Recommended model |
|---|---|
| Fast lookups, wiring diagrams | `mistral` |
| DTC diagnosis trees | `llama3.1:8b` |
| Complex multi-step reasoning | `deepseek-r1` |

Pull any of these: `ollama pull <model>`  
All run fine on your RTX 3060 with Ollama's 4-bit quantization.

---

## Data Layout

```
fsm_rag/
├── data/
│   ├── parsed/
│   │   ├── your_fsm_section.json   # per-PDF parsed chunks
│   │   └── combined.json           # all chunks merged (input to embed)
│   └── chromadb/                   # persistent vector store
├── 00_setup.py
├── 01_parse_fsm.py
├── 02_embed.py
├── 03_query.py
├── 04_acty_bridge.py
└── requirements.txt
```
