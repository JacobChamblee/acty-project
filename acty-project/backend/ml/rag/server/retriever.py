"""
retriever.py — query ChromaDB and return grounded context for Acty pipeline
"""

import chromadb
import ollama

CHROMA_DIR  = "/home/jacob/acty/rag/chroma_db"
COLLECTION  = "acty_manuals"
EMBED_MODEL = "nomic-embed-text"
TOP_K       = 5

client     = chromadb.PersistentClient(path=CHROMA_DIR)
collection = client.get_or_create_collection(name=COLLECTION)


def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Embed query, retrieve top_k chunks from ChromaDB.
    Returns list of {text, source, page, distance}
    """
    response = ollama.embeddings(model=EMBED_MODEL, prompt=query)
    results  = collection.query(
        query_embeddings=[response["embedding"]],
        n_results=top_k
    )

    chunks = []
    for i in range(len(results["documents"][0])):
        chunks.append({
            "text":     results["documents"][0][i],
            "source":   results["metadatas"][0][i]["source"],
            "page":     results["metadatas"][0][i]["page"],
            "distance": results["distances"][0][i]
        })

    return chunks


def build_context(query: str) -> str:
    """
    Convenience wrapper — returns a single formatted context string
    ready to inject into an LLM prompt.
    """
    chunks = retrieve(query)
    context_blocks = [
        f"[{c['source']} p.{c['page']}]\n{c['text']}"
        for c in chunks
    ]
    return "\n\n---\n\n".join(context_blocks)