import json
import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# Paths
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "fly_patterns.json")
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")

def load_fly_patterns():
    """Load fly patterns from JSON file."""
    with open(DATA_PATH, "r") as f:
        return json.load(f)

def get_vector_store():
    """Build or load the ChromaDB vector store for fly patterns using SentenceTransformers."""
    # Use a local embedding model (all-MiniLM-L6-v2 is small, fast, and good for semantic search)
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    if not os.path.exists(CHROMA_PATH):
        os.makedirs(CHROMA_PATH)
    patterns = load_fly_patterns()
    docs = []
    metadatas = []
    for pattern in patterns:
        # Combine relevant fields for embedding
        text = f"{pattern['fly_name']}. Type: {pattern['type']}. Hatch: {pattern.get('hatch_conditions', '')}. Notes: {pattern.get('notes', '')}"
        docs.append(text)
        metadatas.append(pattern)
    # Create or load ChromaDB
    db = Chroma.from_texts(docs, embeddings, metadatas=metadatas, persist_directory=CHROMA_PATH)
    return db

def search_fly_patterns(query, k=3):
    """Search for relevant fly patterns given a query string."""
    db = get_vector_store()
    results = db.similarity_search(query, k=k)
    return [r.metadata for r in results]

# Example usage for testing
if __name__ == "__main__":
    print("Testing fly pattern search...")
    query = "cold water, blue wing olive hatch"
    results = search_fly_patterns(query)
    for i, pattern in enumerate(results, 1):
        print(f"Result {i}: {pattern['fly_name']} | Type: {pattern['type']} | Hatch: {pattern.get('hatch_conditions', '')}")# Placeholder for ChromaDB vector store setup
# Load fly patterns, create embeddings, etc.