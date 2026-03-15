"""
report.py — Stage 6: RAG-grounded diagnostic report generation
Consumes anomaly + predictive output, queries RAG server,
generates final LLM report via Ollama.
"""

import os
import httpx
import ollama
from typing import Optional

RAG_BASE_URL  = os.getenv("RAG_BASE_URL",  "http://192.168.68.138:8766")
OLLAMA_MODEL  = os.getenv("OLLAMA_MODEL",  "llama3.1:8b")
OLLAMA_HOST   = os.getenv("OLLAMA_HOST",   "http://192.168.68.138:11434")


async def get_rag_context(query: str) -> str:
    """Query the RAG server for FSM context grounded to the fault."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{RAG_BASE_URL}/context",
                json={"query": query}
            )
            response.raise_for_status()
            return response.json()["context"]
    except Exception as e:
        print(f"[report] RAG server unavailable, proceeding without context: {e}")
        return ""


def build_rag_query(dtc_codes: list[str], anomalies: list[dict]) -> str:
    """Build a targeted RAG query from fault data."""
    dtc_str = " ".join(dtc_codes) if dtc_codes else "no fault codes"
    anomaly_systems = list({a.get("system", "") for a in anomalies if a.get("system")})
    system_str = " ".join(anomaly_systems) if anomaly_systems else ""
    return f"Toyota GR86 FA24 {dtc_str} {system_str} diagnosis procedure repair".strip()


async def generate_diagnostic_report(
    dtc_codes:    list[str],
    anomalies:    list[dict],
    vehicle_data: dict,
    vehicle_id:   Optional[str] = None,
) -> dict:
    """
    Full report generation pipeline:
      1. Build RAG query from fault data
      2. Retrieve FSM context
      3. Generate grounded LLM report via Ollama
    Returns dict with report text + metadata.
    """

    # ── Stage 1: RAG context ──────────────────────────────────────────────────
    rag_query = build_rag_query(dtc_codes, anomalies)
    context   = await get_rag_context(rag_query)

    # ── Stage 2: Build prompt ─────────────────────────────────────────────────
    context_section = f"""SERVICE MANUAL CONTEXT:
{context}

""" if context else "SERVICE MANUAL CONTEXT: Unavailable — analysis based on sensor data only.\n\n"

    prompt = f"""You are an automotive diagnostic AI for a Toyota GR86 (FA24 engine).
Use the service manual context below to ground your analysis.
Do not speculate beyond what the data and context support.
Be concise and technically precise.

{context_section}DETECTED FAULT CODES:
{dtc_codes if dtc_codes else 'None'}

SENSOR ANOMALIES:
{anomalies if anomalies else 'None detected'}

VEHICLE DATA SNAPSHOT:
{vehicle_data}

Provide a structured diagnostic report with these exact sections:
1. PRIMARY FAULT ASSESSMENT
2. LIKELY ROOT CAUSE (cite FSM section if applicable)
3. SEVERITY: [Critical / High / Medium / Low]
4. RECOMMENDED IMMEDIATE ACTION
5. ESTIMATED REPAIR COMPLEXITY: [DIY / Shop / Dealer]"""

    # ── Stage 3: LLM generation ───────────────────────────────────────────────
    client   = ollama.Client(host=OLLAMA_HOST)
    response = client.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    report_text = response["message"]["content"]

    return {
        "vehicle_id":    vehicle_id,
        "dtc_codes":     dtc_codes,
        "anomaly_count": len(anomalies),
        "rag_query":     rag_query,
        "rag_grounded":  bool(context),
        "report":        report_text,
    }