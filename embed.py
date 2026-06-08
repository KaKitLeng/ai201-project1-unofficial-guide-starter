"""
embed.py - embed chunks, store them in a persistent ChromaDB collection, and retrieve.

Milestone 4 (embedding + vector store + retrieval only; no LLM/generation yet). Pipeline:

    ingest.build_chunks()  ->  all-MiniLM-L6-v2 (sentence-transformers)  ->  ChromaDB
                                                                              |
                                                       retrieve(query, k)  <--+

The embedding model and Chroma client are loaded once and reused. The store is persistent
(./chroma_db/) so we don't re-embed on every run. Run `python embed.py` for the retrieval
test over 3 eval queries.

Requires: sentence-transformers, chromadb (already in requirements.txt). First run downloads
all-MiniLM-L6-v2 (~90 MB) from Hugging Face; cached afterward.
"""

import sys

import chromadb
from sentence_transformers import SentenceTransformer

import ingest

MODEL_NAME = "all-MiniLM-L6-v2"
PERSIST_DIR = "chroma_db"
COLLECTION = "unofficial_guide"

_model = None
_client = None


# --------------------------------------------------------------------------- #
# load-once singletons
# --------------------------------------------------------------------------- #
def get_model():
    """The SentenceTransformer, loaded once and reused."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def get_client():
    """The persistent ChromaDB client, created once and reused."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=PERSIST_DIR)
    return _client


def get_collection():
    """The named collection, using cosine distance (not Chroma's default squared-L2) so
    distances are interpretable as 1 - cosine_similarity in [0, 2]."""
    return get_client().get_or_create_collection(
        COLLECTION, metadata={"hnsw:space": "cosine"}
    )


def _clean_meta(meta):
    """ChromaDB rejects None metadata values -> map None to "" (keeps int chunk_index)."""
    return {k: ("" if v is None else v) for k, v in meta.items()}


def _embed_text(chunk):
    """Text we actually embed: the chunk prefixed with its building and (for Reddit) title.
    Those identifiers live in metadata, not the body -- e.g. a POG review thread says "the
    office"/"POG", never "Pacifica on Green" -- so without this the building name carries no
    vector signal and building-specific review queries miss. The clean body is still what we
    store as the document and return from retrieve()."""
    m = chunk["metadata"]
    prefix = " | ".join(p for p in (m.get("building"), m.get("title")) if p)
    return f"{prefix}\n{chunk['text']}" if prefix else chunk["text"]


# --------------------------------------------------------------------------- #
# indexing + retrieval
# --------------------------------------------------------------------------- #
def build_index(rebuild=False):
    """Embed every chunk from ingest.build_chunks() and upsert into ChromaDB. Skips
    embedding if the collection is already populated (unless rebuild=True)."""
    client = get_client()
    if rebuild:
        try:
            client.delete_collection(COLLECTION)
        except Exception:
            pass                                     # nothing to delete on a fresh store

    coll = get_collection()
    if not rebuild and coll.count() > 0:
        print(f"already indexed: {coll.count()} chunks in '{COLLECTION}' "
              f"(call build_index(rebuild=True) to re-embed)")
        return coll

    chunks = ingest.build_chunks()
    texts = [c["text"] for c in chunks]
    ids = [f"{c['metadata']['source_file']}_{c['metadata']['chunk_index']}" for c in chunks]
    metadatas = [_clean_meta(c["metadata"]) for c in chunks]

    print(f"embedding {len(texts)} chunks with {MODEL_NAME} ...")
    embeddings = get_model().encode(
        [_embed_text(c) for c in chunks],          # embed metadata-enriched text
        batch_size=64, normalize_embeddings=True, show_progress_bar=True,
    ).tolist()

    coll.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
    print(f"indexed {len(ids)} chunks into '{COLLECTION}'")
    return coll


def retrieve(query, k=5, where=None):
    """Embed the query with the same model and return the top-k nearest chunks as
    [{"text", "metadata", "distance"}]. `where` is an optional ChromaDB metadata filter,
    e.g. retrieve(q, where={"building": "Pacifica on Green"})."""
    qvec = get_model().encode([query], normalize_embeddings=True).tolist()
    res = get_collection().query(query_embeddings=qvec, n_results=k, where=where)
    return [
        {"text": text, "metadata": meta, "distance": dist}
        for text, meta, dist in zip(
            res["documents"][0], res["metadatas"][0], res["distances"][0]
        )
    ]


# --------------------------------------------------------------------------- #
# retrieval test
# --------------------------------------------------------------------------- #
# (label, query, predicate that flags the expected chunk, human description)
EVAL_QUERIES = [
    ("Q1 (fact)", "What is the monthly rent for a 2 bedroom unit at Legacy 202?",
     lambda r: "$1,275" in r["text"], "chunk containing $1,275"),
    ("Q2 (fact)", "Are pets allowed at Legacy 202?",
     lambda r: "does not allow pets" in r["text"], "Legacy 202 FAQ chunk: 'does not allow pets...'"),
    ("Q4 (reviews)", "What do students say about management at Pacifica on Green?",
     lambda r: r["metadata"].get("source_file") == "reddit_uiuc_1o6pln5.txt",
     "a chunk from reddit_uiuc_1o6pln5.txt"),
    ("Q5 (legal)", "How long does a landlord have to return a security deposit?",
     lambda r: "forty-five (45)" in r["text"], "OCCL chunk containing 'forty-five (45)'"),
]


def main():
    try:                                             # render curly quotes on Windows console
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    build_index()
    print()

    for label, query, expected, desc in EVAL_QUERIES:
        print("=" * 78)
        print(f"{label}: {query}")
        print("=" * 78)
        results = retrieve(query, k=5)
        for rank, r in enumerate(results, 1):
            m = r["metadata"]
            building = m.get("building") or "-"
            snippet = " ".join(r["text"].split())[:150]
            print(f"  {rank}. [{r['distance']:.3f}] {m['source_file']} ({building}) :: {snippet}")

        hit = next(((rank, r) for rank, r in enumerate(results, 1) if expected(r)), None)
        if hit is None:
            print(f"  FAIL -- expected {desc} not in top-5")
        else:
            rank, r = hit
            ok = r["distance"] < 0.5
            verdict = "PASS" if ok else "FAIL"
            tail = "" if ok else "  (distance >= 0.5)"
            print(f"  {verdict} -- expected {desc} at rank {rank}, distance {r['distance']:.3f}{tail}")
        print()


if __name__ == "__main__":
    main()
