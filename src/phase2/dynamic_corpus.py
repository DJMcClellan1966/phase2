"""
Dynamic corpus: demand-driven slice loading.

Pattern from Dictionary's slice_store: large corpus on disk, index in memory,
load only the slice needed for the current query (by id + optional 1-hop).

- SliceIndex: holds vocabulary and id -> file/offset (or key) for sentences/chunks.
- load_slice_from_store: given a set of ids, read only those records from store.
- Corpus can grow (append new items, update index) and shrink (cold archive, prune).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _tokenize_query(query: str) -> list[str]:
    """Tokenize query for vocabulary lookup: lowercase words, length > 1."""
    return [
        w for w in re.findall(r"[a-z][a-z'-]*[a-z]|[a-z]", query.lower())
        if len(w) > 1
    ]


class SliceIndex:
    """
    In-memory index for on-demand slice loading.

    Holds:
    - ids: list of known sentence/chunk ids.
    - id_to_location: id -> (path, offset) for random access in JSONL.
    - vocabulary: term -> id or term -> list of ids (sentences containing that term).
    - neighbors: optional id -> list of ids for 1-hop expansion.
    """

    def __init__(
        self,
        ids: list[int] | None = None,
        id_to_location: dict[int | str, tuple[Path | str, int | str]] | None = None,
        vocabulary: dict[str, int] | dict[str, list[int]] | dict[int, str] | None = None,
        neighbors: dict[int, list[int]] | None = None,
    ) -> None:
        self.ids = list(ids or [])
        self.id_to_location = dict(id_to_location or {})
        self.vocabulary = dict(vocabulary or {})
        self.neighbors = dict(neighbors or {})

    @classmethod
    def load_from_path(cls, index_path: Path, corpus_dir: Path | None = None) -> "SliceIndex":
        """
        Load index from slice_index.json. Expects keys: ids, id_to_offset,
        sentences_file, vocabulary. Optional: neighbors (id -> list of ids).
        """
        path = Path(index_path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        ids = list(data.get("ids", []))
        id_to_offset = data.get("id_to_offset", {})
        sentences_file = data.get("sentences_file", "sentences.jsonl")
        base = corpus_dir if corpus_dir is not None else path.parent
        id_to_location: dict[int, tuple[str, int]] = {}
        for k, offset in id_to_offset.items():
            id_to_location[int(k)] = (sentences_file, int(offset))
        vocab = data.get("vocabulary", {})
        neighbors = {int(k): [int(x) for x in v] for k, v in data.get("neighbors", {}).items()}
        return cls(ids=ids, id_to_location=id_to_location, vocabulary=vocab, neighbors=neighbors)

    def resolve_query_to_ids(self, query: str | list[str], expand_1hop: bool = False) -> set[int]:
        """
        Map query (string or list of terms) to a set of sentence ids to load.
        Tokenizes query if string; matches terms against vocabulary (term -> id or term -> list of ids).
        If expand_1hop and neighbors is set, adds 1-hop neighbor ids.
        """
        if isinstance(query, str):
            terms = _tokenize_query(query)
        else:
            terms = [t.strip().lower() for t in query if t and t.strip()]
        resolved: set[int] = set()
        for term in terms:
            t = term.strip().lower()
            if not t:
                continue
            v = self.vocabulary.get(t)
            if v is None:
                continue
            if isinstance(v, list):
                resolved.update(v)
            else:
                resolved.add(int(v))
        resolved &= set(self.ids)
        if expand_1hop and self.neighbors:
            extra: set[int] = set()
            for i in resolved:
                extra.update(self.neighbors.get(i, []))
            resolved |= (extra & set(self.ids))
        return resolved


def _read_jsonl_line_by_offset(path: Path, offset: int) -> dict[str, Any] | None:
    """Read a single JSONL line at the given byte offset."""
    with open(path, encoding="utf-8") as f:
        f.seek(offset)
        line = f.readline()
    if not line.strip():
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def load_slice_from_store(
    store_dir: Path,
    ids: set[int],
    index: SliceIndex,
    *,
    expand_1hop: bool = False,
) -> list[dict[str, Any]]:
    """
    Load only the given ids from the store under store_dir.

    Expects index.id_to_location to map id -> (path, offset) where path is
    relative to store_dir and offset is byte offset in that JSONL file.
    If expand_1hop is True, index should provide a way to get neighbors
    (not implemented here; see Dictionary's load_slice for the graph version).

    Returns a list of records (dicts) for the requested ids. Missing or
    unreadable ids are skipped.
    """
    store_dir = Path(store_dir)
    out: list[dict[str, Any]] = []
    for i in ids:
        loc = index.id_to_location.get(i)
        if not loc:
            continue
        path_or_key, offset_or_key = loc
        path = store_dir / path_or_key if isinstance(path_or_key, str) else path_or_key
        if not path.exists():
            continue
        if isinstance(offset_or_key, int):
            rec = _read_jsonl_line_by_offset(path, offset_or_key)
            if rec is not None:
                out.append(rec)
    return out
