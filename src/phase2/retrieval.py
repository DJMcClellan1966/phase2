"""
Retrieval: resolve query to context bundle from corpus store.

Uses SliceIndex (vocabulary + id_to_location) and load_slice_from_store
to return a list of store records for Refine and LLM context assembly.
Can merge with Mirror (profile + recent episodes) for full context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .dynamic_corpus import SliceIndex, load_slice_from_store
from .mirror import get_mirror_context


SLICE_INDEX_JSON = "slice_index.json"


def retrieve_context(
    query: str,
    store_dir: Path,
    index: SliceIndex | None = None,
    *,
    max_items: int = 20,
    expand_1hop: bool = False,
) -> list[dict[str, Any]]:
    """
    Retrieve a context bundle for the query from the corpus store.

    - Resolves query to sentence ids via index.resolve_query_to_ids.
    - Loads only those records from the store via load_slice_from_store.
    - Returns up to max_items records (each with id, text, and optional term, genre_id, source).

    If index is None, loads SliceIndex from store_dir / slice_index.json.
    """
    store_dir = Path(store_dir)
    if index is None:
        index_path = store_dir / SLICE_INDEX_JSON
        if not index_path.exists():
            return []
        index = SliceIndex.load_from_path(index_path, corpus_dir=store_dir)

    ids = index.resolve_query_to_ids(query, expand_1hop=expand_1hop)
    if not ids:
        return []

    records = load_slice_from_store(store_dir, ids, index, expand_1hop=False)
    return records[:max_items]


def retrieve_context_with_mirror(
    query: str,
    store_dir: Path,
    mirror_dir: Path | None = None,
    index: SliceIndex | None = None,
    *,
    max_items: int = 20,
    last_n_episodes: int = 5,
    expand_1hop: bool = False,
) -> tuple[list[dict[str, Any]], str]:
    """
    Retrieve corpus context bundle and Mirror context (goals, preferences, recent episodes).
    Returns (corpus_records, mirror_context_string) for context assembly.
    """
    records = retrieve_context(
        query, store_dir, index=index, max_items=max_items, expand_1hop=expand_1hop
    )
    mirror_context = ""
    if mirror_dir and Path(mirror_dir).exists():
        mirror_context = get_mirror_context(Path(mirror_dir), last_n_episodes=last_n_episodes)
    return records, mirror_context
