"""Lightweight catalog search over the fly pattern dataset.

This module replaced an earlier Chroma + sentence-transformers vector store.
The catalog is small enough (a few hundred patterns) that a simple keyword
overlap score is fast, deterministic, and free of heavy ML dependencies,
which keeps the backend within tight memory limits on free-tier hosting.

Public API is unchanged so the rest of the agent does not need to be
modified: ``search_fly_patterns(query, k=3, type_filter=None)`` returns a
list of fly pattern dicts ranked by relevance.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "fly_patterns.json")

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "of", "for", "to", "with",
    "in", "on", "at", "by", "from", "as", "is", "are", "be", "been",
    "this", "that", "these", "those", "it", "its", "their", "them",
    "fly", "flies", "fishing", "fish", "patterns", "pattern", "use",
    "good", "great", "best", "very", "also", "than", "then", "when",
    "where", "what", "which", "while", "during", "month", "season",
}

_SEARCHABLE_FIELDS = (
    "fly_name",
    "type",
    "season",
    "hatch_conditions",
    "tying_keywords",
    "notes",
)


_patterns_cache: Optional[List[Dict[str, Any]]] = None
_index_cache: Optional[List[Dict[str, Any]]] = None


def _tokenize(text: str) -> List[str]:
    """Lowercase and tokenize text into meaningful words."""
    if not text:
        return []
    tokens = _TOKEN_RE.findall(text.lower())
    return [token for token in tokens if token and token not in _STOPWORDS]


def _flatten_field(value: Any) -> str:
    """Flatten a metadata value into a searchable string."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten_field(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_flatten_field(item) for item in value.values())
    return str(value)


def load_fly_patterns() -> List[Dict[str, Any]]:
    """Load and cache fly patterns from disk."""
    global _patterns_cache
    if _patterns_cache is None:
        with open(DATA_PATH, "r") as f:
            _patterns_cache = json.load(f)
    return _patterns_cache


def _build_index() -> List[Dict[str, Any]]:
    """Build a search index of token sets and term frequencies per pattern."""
    global _index_cache
    if _index_cache is not None:
        return _index_cache

    patterns = load_fly_patterns()
    index: List[Dict[str, Any]] = []
    for pattern in patterns:
        haystack_parts = [_flatten_field(pattern.get(field, "")) for field in _SEARCHABLE_FIELDS]
        haystack_parts.append(_flatten_field(pattern.get("regions", [])))
        haystack = " ".join(part for part in haystack_parts if part)

        tokens = _tokenize(haystack)
        term_freq: Dict[str, int] = {}
        for token in tokens:
            term_freq[token] = term_freq.get(token, 0) + 1

        index.append(
            {
                "pattern": pattern,
                "tokens": set(term_freq.keys()),
                "term_freq": term_freq,
            }
        )

    _index_cache = index
    return _index_cache


def _score_query(query_tokens: List[str], entry: Dict[str, Any]) -> float:
    """Score a single pattern against a tokenized query."""
    if not query_tokens:
        return 0.0
    token_set = entry["tokens"]
    term_freq = entry["term_freq"]

    seen_query_tokens = set()
    score = 0.0
    for token in query_tokens:
        if token in seen_query_tokens:
            continue
        seen_query_tokens.add(token)
        if token in token_set:
            score += 1.0 + 0.1 * (term_freq.get(token, 0) - 1)
    return score


def search_fly_patterns(
    query: str,
    k: int = 3,
    type_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return the top-``k`` fly patterns most relevant to ``query``.

    If ``type_filter`` is provided, only patterns whose ``type`` matches are
    considered. Results are sorted by score (descending) and ties are broken
    by the pattern's original index in the catalog so output stays stable.
    """
    index = _build_index()
    query_tokens = _tokenize(query)

    scored: List[Tuple[float, int, Dict[str, Any]]] = []
    for idx, entry in enumerate(index):
        pattern = entry["pattern"]
        if type_filter is not None and pattern.get("type") != type_filter:
            continue
        score = _score_query(query_tokens, entry)
        scored.append((score, idx, pattern))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [pattern for _, _, pattern in scored[:k]]


def get_vector_store(force_rebuild: bool = False):
    """Backwards-compatible shim for callers expecting a vector-store handle.

    Returns the in-memory catalog index. The ``force_rebuild`` flag clears
    the cached index so it will be rebuilt on the next call.
    """
    global _patterns_cache, _index_cache
    if force_rebuild:
        _patterns_cache = None
        _index_cache = None
    return _build_index()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    print("Testing fly pattern search...")
    sample_query = "cold water, blue wing olive hatch"
    for i, pattern in enumerate(search_fly_patterns(sample_query, k=5), 1):
        print(
            f"Result {i}: {pattern['fly_name']} | Type: {pattern['type']} | "
            f"Hatch: {pattern.get('hatch_conditions', '')}"
        )
