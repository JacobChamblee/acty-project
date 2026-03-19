"""
rag_server.py — lightweight FastAPI wrapper around retriever.py
Runs on the 4U at port 8766, called by Acty's main backend
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from retriever import retrieve, build_context
import uvicorn
import httpx

app = FastAPI(title="Acty RAG Server")

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"

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
def retrieve_chunks(req: QueryRequest):
    try:
        results = retrieve(req.query, top_k=req.top_k)
        return {"chunks": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/context")
def get_context(req: ContextRequest):
    try:
        context = build_context(req.query)
        return {"context": context}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query")
def query(req: AskRequest):
    try:
        chunks = retrieve(req.query, top_k=req.top_k)
        if not chunks:
            raise HTTPException(status_code=404, detail="No relevant chunks found.")

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
