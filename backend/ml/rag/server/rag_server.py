"""
rag_server.py — lightweight FastAPI wrapper around retriever.py
Runs on the 4U at port 8766, called by Acty's main backend
"""

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
from retriever import retrieve, build_context
import uvicorn
import httpx

import os
import secrets

app = FastAPI(title="Acty RAG Server")

_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_URL   = f"{_OLLAMA_HOST}/api/generate"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

# Internal shared secret — must be set via env on both caller and this server.
# Callers (acty-api backend) send this in X-Internal-Token header.
_RAG_INTERNAL_TOKEN = os.environ.get("RAG_INTERNAL_TOKEN", "")


def _require_internal_token(x_internal_token: str | None = Header(default=None)) -> None:
    """Dependency: reject requests that don't present the correct internal token."""
    if not _RAG_INTERNAL_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="RAG_INTERNAL_TOKEN is not configured on this server.",
        )
    if not x_internal_token or not secrets.compare_digest(
        x_internal_token, _RAG_INTERNAL_TOKEN
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing X-Internal-Token")


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5

class ContextRequest(BaseModel):
    query: str

class AskRequest(BaseModel):
    query: str
    top_k: int = 5
    model: str = OLLAMA_MODEL

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/retrieve")
def retrieve_chunks(req: QueryRequest, _: None = Depends(_require_internal_token)):
    try:
        results = retrieve(req.query, top_k=req.top_k)
        return {"chunks": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/context")
def get_context(req: ContextRequest, _: None = Depends(_require_internal_token)):
    try:
        context = build_context(req.query)
        return {"context": context}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query")
def query(req: AskRequest, _: None = Depends(_require_internal_token)):
    # Validate query length before hitting the embedding model
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=422, detail="Query must not be empty.")
    if len(req.query) > 2000:
        raise HTTPException(status_code=422, detail="Query exceeds 2000-character limit.")

    try:
        chunks = retrieve(req.query, top_k=req.top_k)

        # No results is a valid outcome — return 200 with empty answer rather than 404.
        # 404 caused callers to treat it as a server error instead of a graceful degradation.
        if not chunks:
            return {
                "answer": "",
                "no_results_found": True,
                "sources": [],
            }

        context = "\n\n---\n\n".join(
            f"[{c['source']} p.{c['page']}]\n{c['text']}" for c in chunks
        )

        prompt = (
            "You are an automotive technician assistant with access to the GR86/BRZ "
            "factory service manual. Answer the question using only the provided excerpts. "
            "Be concise and include torque specs, part names, or step numbers exactly as written. "
            "If the answer is not in the excerpts, say so.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {req.query}"
        )

        response = httpx.post(
            OLLAMA_URL,
            json={"model": req.model, "prompt": prompt, "stream": False},
            timeout=60.0,
        )
        response.raise_for_status()
        answer = response.json().get("response", "").strip()

        return {
            "answer": answer,
            "no_results_found": False,
            "sources": [
                {"source": c["source"], "page": c["page"], "distance": c["distance"]}
                for c in chunks
            ],
        }

    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("rag_server:app", host="0.0.0.0", port=8766, reload=False)
