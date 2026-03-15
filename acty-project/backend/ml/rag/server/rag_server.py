"""
rag_server.py — lightweight FastAPI wrapper around retriever.py
Runs on the 4U at port 8766, called by Acty's main backend
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from retriever import retrieve, build_context
import uvicorn

app = FastAPI(title="Acty RAG Server")

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5

class ContextRequest(BaseModel):
    query: str

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

if __name__ == "__main__":
    uvicorn.run("rag_server:app", host="0.0.0.0", port=8766, reload=False)