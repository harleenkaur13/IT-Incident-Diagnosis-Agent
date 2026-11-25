from pathlib import Path
from typing import List, Dict, Any

import fitz  # PyMuPDF
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
        encode_kwargs={"normalize_embeddings": True},
    )


def load_pdf_documents(folder: Path, doc_type: str) -> List[Document]:
    """Parses all PDFs in a folder using PyMuPDF, preserving filename and page number."""
    docs: List[Document] = []
    if not folder.exists():
        return docs

    for pdf_path in sorted(folder.glob("*.pdf")):
        with fitz.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()
                if text:
                    docs.append(
                        Document(
                            page_content=text,
                            metadata={
                                "source": pdf_path.name,
                                "page": page_num,
                                "doc_type": doc_type,
                            },
                        )
                    )
    return docs


def load_markdown_documents(folder: Path, doc_type: str) -> List[Document]:
    """Loads all Markdown files in a folder with source and doc_type metadata."""
    docs: List[Document] = []
    if not folder.exists():
        return docs

    for md_path in sorted(folder.glob("*.md")):
        text = md_path.read_text(encoding="utf-8").strip()
        if text:
            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": md_path.name,
                        "page": 1,
                        "doc_type": doc_type,
                    },
                )
            )
    return docs


def build_or_load_vectorstore(force_rebuild: bool = False) -> FAISS:
    """Loads existing FAISS index or rebuilds it from official PDFs + internal Markdown docs."""
    embeddings = get_embeddings()

    if INDEX_DIR.exists() and not force_rebuild:
        return FAISS.load_local(
            str(INDEX_DIR), embeddings, allow_dangerous_deserialization=True
        )

    raw_docs: List[Document] = []
    raw_docs.extend(load_pdf_documents(DATA_DIR / "official_docs", "official_doc"))
    raw_docs.extend(load_markdown_documents(DATA_DIR / "internal_policies", "internal_policy"))
    raw_docs.extend(load_markdown_documents(DATA_DIR / "past_tickets", "past_ticket"))

    if not raw_docs:
        raise FileNotFoundError(f"No PDF or MD files found under {DATA_DIR.resolve()}")

    splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)
    chunks = splitter.split_documents(raw_docs)

    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(str(INDEX_DIR))
    print(f"Indexed {len(chunks)} chunks from {len(raw_docs)} pages/documents.")
    return vectorstore


def retrieve_evidence(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval: guarantees we fetch top chunks from internal policies,
    official Microsoft docs, and past tickets so policies are never drowned out.
    """
    vectorstore = build_or_load_vectorstore()

    # Fetch balanced slices by doc_type
    policy_hits = vectorstore.similarity_search_with_score(
        query, k=2, filter={"doc_type": "internal_policy"}, fetch_k=50
    )
    official_hits = vectorstore.similarity_search_with_score(
        query, k=2, filter={"doc_type": "official_doc"}, fetch_k=50
    )
    ticket_hits = vectorstore.similarity_search_with_score(
        query, k=1, filter={"doc_type": "past_ticket"}, fetch_k=50
    )

    combined = policy_hits + official_hits + ticket_hits

    evidence = []
    for doc, score in combined:
        source_label = doc.metadata.get("source", "unknown")
        if doc.metadata.get("doc_type") == "official_doc":
            source_label = f"{source_label} (p.{doc.metadata.get('page', '?')})"

        evidence.append({
            "source": source_label,
            "doc_type": doc.metadata.get("doc_type", "unknown"),
            "score": round(float(score), 4),
            "content": doc.page_content.strip(),
        })
    return evidence


# --- Quick Sanity Test ---
if __name__ == "__main__":
    print("Rebuilding FAISS index with real Microsoft PDFs + internal policies...")
    build_or_load_vectorstore(force_rebuild=True)

    test_query = "Corporate VPN fails to connect and SSO auth token might be expired."
    print(f"\nQuery: {test_query}\n")

    matches = retrieve_evidence(test_query)
    for i, item in enumerate(matches, 1):
        print(f"--- Match {i} | Type: {item['doc_type']} | Distance: {item['score']}] ---")
        print(item["content"][:250] + "...\n")