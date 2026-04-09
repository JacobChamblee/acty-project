"""
ingest.py — chunk PDFs and embed into ChromaDB via Ollama nomic-embed-text
Run once per new manual, or re-run to refresh.
"""

import os
import chromadb
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import ollama

# ── Config ────────────────────────────────────────────────────────────────────
PDF_DIR       = "/home/jacob/acty/rag/pdfs"
CHROMA_DIR    = "/home/jacob/acty/rag/chroma_db"
COLLECTION    = "acty_manuals"
EMBED_MODEL   = "nomic-embed-text"
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 100

# ── ChromaDB ──────────────────────────────────────────────────────────────────
client     = chromadb.PersistentClient(path=CHROMA_DIR)
collection = client.get_or_create_collection(
    name=COLLECTION,
    metadata={"hnsw:space": "cosine"}
)

# ── Splitter ──────────────────────────────────────────────────────────────────
splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ".", " "]
)

# ── Ingest loop ───────────────────────────────────────────────────────────────
for filename in os.listdir(PDF_DIR):
    if not filename.endswith(".pdf"):
        continue

    pdf_path = os.path.join(PDF_DIR, filename)
    print(f"📄 Loading {filename}...")

    loader = PyPDFLoader(pdf_path)
    pages  = loader.load()
    chunks = splitter.split_documents(pages)

    print(f"   {len(pages)} pages → {len(chunks)} chunks, embedding...")

    ids, embeddings, documents, metadatas = [], [], [], []

    for i, chunk in enumerate(chunks):
        response = ollama.embeddings(model=EMBED_MODEL, prompt=chunk.page_content)
        ids.append(f"{filename}_{i}")
        embeddings.append(response["embedding"])
        documents.append(chunk.page_content)
        metadatas.append({
            "source": filename,
            "page":   chunk.metadata.get("page", 0)
        })

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )
    print(f"   ✅ {len(chunks)} chunks upserted into ChromaDB")

print("\n✅ Ingestion complete.")