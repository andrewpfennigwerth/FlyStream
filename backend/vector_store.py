"""ChromaDB-backed retrieval over the fly pattern catalog.

The store is built once per process and reused across requests.

Population is idempotent: we read the persisted embedding count from the
underlying sqlite file directly (without opening Chroma) so we never end up
with a stale chromadb client holding handles to a directory we then try to
rebuild. If the persisted count does not match the catalog size, we wipe
the directory, clear chromadb's global client cache, and rebuild from
scratch.
"""

import json
import logging
import os
import shutil
import sqlite3
from typing import Optional

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "fly_patterns.json")
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

logger = logging.getLogger(__name__)

_embeddings = None
_vector_store = None


def load_fly_patterns():
    """Load fly patterns from JSON file."""
    with open(DATA_PATH, "r") as f:
        return json.load(f)


def _build_docs_and_metadatas(patterns):
    """Build embedding documents and Chroma-safe metadata for each pattern."""
    docs = []
    metadatas = []
    for pattern in patterns:
        text = (
            f"{pattern['fly_name']}. Type: {pattern['type']}. "
            f"Hatch: {pattern.get('hatch_conditions', '')}. "
            f"Notes: {pattern.get('notes', '')}"
        )
        docs.append(text)
        safe_metadata = {}
        for key, value in pattern.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe_metadata[key] = value
            else:
                safe_metadata[key] = json.dumps(value)
        metadatas.append(safe_metadata)
    return docs, metadatas


def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
    return _embeddings


def _persisted_count(path: str) -> int:
    """Read embedding count from the persisted sqlite file without opening Chroma.

    Returns 0 if no persisted store exists, -1 if the file exists but the
    schema cannot be read.
    """
    sqlite_file = os.path.join(path, "chroma.sqlite3")
    if not os.path.exists(sqlite_file):
        return 0
    try:
        conn = sqlite3.connect(f"file:{sqlite_file}?mode=ro", uri=True)
        try:
            cur = conn.execute("SELECT COUNT(*) FROM embeddings")
            return int(cur.fetchone()[0])
        finally:
            conn.close()
    except sqlite3.Error:
        return -1


def _reset_chroma_client_cache() -> None:
    """Best-effort clear of chromadb's global client cache before a rebuild."""
    try:
        from chromadb.api.client import SharedSystemClient

        SharedSystemClient.clear_system_cache()
    except Exception:
        pass


def get_vector_store(force_rebuild: bool = False):
    """Return a process-wide singleton Chroma vector store for fly patterns."""
    global _vector_store
    if _vector_store is not None and not force_rebuild:
        return _vector_store

    embeddings = _get_embeddings()
    patterns = load_fly_patterns()
    expected_count = len(patterns)
    persisted = _persisted_count(CHROMA_PATH)
    needs_rebuild = force_rebuild or persisted != expected_count

    if needs_rebuild:
        logger.info(
            "Rebuilding fly pattern vector store (persisted=%s expected=%s).",
            persisted,
            expected_count,
        )
        _reset_chroma_client_cache()
        if os.path.exists(CHROMA_PATH):
            shutil.rmtree(CHROMA_PATH, ignore_errors=True)
        os.makedirs(CHROMA_PATH, exist_ok=True)
        docs, metadatas = _build_docs_and_metadatas(patterns)
        db = Chroma.from_texts(
            docs,
            embeddings,
            metadatas=metadatas,
            persist_directory=CHROMA_PATH,
        )
    else:
        logger.info("Reusing fly pattern vector store (count=%s).", persisted)
        db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

    _vector_store = db
    return _vector_store


def search_fly_patterns(query: str, k: int = 3, type_filter: Optional[str] = None):
    """Search fly patterns. Optionally filter by `type` via Chroma metadata."""
    db = get_vector_store()
    if type_filter:
        results = db.similarity_search(query, k=k, filter={"type": type_filter})
    else:
        results = db.similarity_search(query, k=k)
    return [r.metadata for r in results]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    print("Testing fly pattern search...")
    query = "cold water, blue wing olive hatch"
    results = search_fly_patterns(query)
    for i, pattern in enumerate(results, 1):
        print(
            f"Result {i}: {pattern['fly_name']} | Type: {pattern['type']} | "
            f"Hatch: {pattern.get('hatch_conditions', '')}"
        )
