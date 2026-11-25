from pathlib import Path
from typing import List, Dict, Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

DATA_DIR = Path("data")
INDEX_DIR = Path("faiss_index")
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


def get_embeddings() -> HuggingFaceEmbeddings:
    """Loads the BGE embedding model (runs locally on CPU)."""
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},  # Recommended for BGE models
    )


def build_or_load_vectorstore(force_rebuild: bool = False) -> FAISS:
    """
    Loads an existing FAISS index from disk, or builds a new one from the data/ folder.
    """
    embeddings = get_embeddings()

    if INDEX_DIR.exists() and not force_rebuild:
        return FAISS.load_local(
            str(INDEX_DIR), embeddings, allow_dangerous_deserialization=True
        )

    # 1. Load all .md files from data/
    raw_docs: List[Document] = []
    for file_path in sorted(DATA_DIR.glob("*.md")):
        text = file_path.read_text(encoding="utf-8")
        raw_docs.append(
            Document(
                page_content=text,
                metadata={"source": file_path.name},
            )
        )

    if not raw_docs:
        raise FileNotFoundError(f"No .md files found in {DATA_DIR.resolve()}")

    # 2. Split into clean chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
    )
    chunks = splitter.split_documents(raw_docs)

    # 3. Build FAISS index and save locally
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(str(INDEX_DIR))
    return vectorstore


def retrieve_evidence(query: str, k: int = 3) -> List[Dict[str, Any]]:
    """
    Searches the knowledge base and returns top-k chunks with source filenames for citations.
    """
    vectorstore = build_or_load_vectorstore()
    results = vectorstore.similarity_search_with_score(query, k=k)

    evidence = []
    for doc, score in results:
        evidence.append({
            "source": doc.metadata.get("source", "unknown"),
            "score": round(float(score), 4),  # Lower L2 distance = closer match
            "content": doc.page_content.strip(),
        })
    return evidence


# --- Quick Sanity Test ---
if __name__ == "__main__":
    print("Building/loading FAISS index...")
    build_or_load_vectorstore(force_rebuild=True)

    test_query = "My VPN is failing to connect. What checks should I run and do I need approval to restart it?"
    print(f"\nQuery: {test_query}\n")

    matches = retrieve_evidence(test_query, k=3)
    for i, item in enumerate(matches, 1):
        print(f"--- Match {i} | Distance: {item['score']}] ---")
        print(item["content"])
        print()