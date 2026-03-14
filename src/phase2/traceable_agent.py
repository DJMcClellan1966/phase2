"""
Traceable agent: answers built only from store-backed sources.

Every span of the answer must come from a citable source (sentence id,
definition term, or chunk id). Anchor's Refine does this by construction
(Theorem 4): response = concatenation of text(s) for s in S_used and
D(t) for t in terms_used; no other characters.

- TraceableAnswer: response text + list of source records (type, id, optional text).
- build_traceable_answer: placeholder that, in a full impl, would run
  activate -> propagate -> pattern -> refine and return text + sources.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SourceRecord:
    """One citable source for a span of the answer."""
    type: str   # "sentence" | "definition" | "chunk"
    id: str | int
    text: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceableAnswer:
    """Answer with full traceability to the store."""
    text: str
    sources: list[SourceRecord]
    extras: dict[str, Any] = field(default_factory=dict)

    def source_summary(self) -> list[dict[str, Any]]:
        """Summary of sources for UI or logging."""
        return [
            {"type": s.type, "id": s.id, "preview": (s.text[:80] + "...") if len(s.text) > 80 else s.text}
            for s in self.sources
        ]


def build_traceable_answer(
    query: str,
    context_bundle: list[dict[str, Any]],
    *,
    max_sentences: int = 10,
    max_definitions: int = 3,
) -> TraceableAnswer:
    """
    Refine: build an answer only from the context bundle (store-backed).
    Definitions (records with "term") first, then sentences. Every span has a source.
    """
    definitions: list[dict[str, Any]] = []
    sentences: list[dict[str, Any]] = []
    for rec in context_bundle:
        if not (rec.get("text") or rec.get("definition")):
            continue
        if rec.get("term") is not None:
            definitions.append(rec)
        else:
            sentences.append(rec)

    sources: list[SourceRecord] = []
    parts: list[str] = []

    for rec in definitions[:max_definitions]:
        text = rec.get("text") or rec.get("definition") or ""
        if not text:
            continue
        sources.append(SourceRecord(type="definition", id=rec["term"], text=text, meta=rec))
        parts.append(text)

    for rec in sentences[:max_sentences]:
        text = rec.get("text") or rec.get("definition") or ""
        if not text:
            continue
        sid = rec.get("id", rec.get("sentence_id", len(sources)))
        sources.append(SourceRecord(type="sentence", id=sid, text=text, meta=rec))
        parts.append(text)

    text = "\n\n".join(parts) if parts else ""
    return TraceableAnswer(text=text, sources=sources, extras={"query": query})


# Default phrases that trigger traceable-only path
DEFAULT_PREFER_TRACEABLE = (
    "what is ", "what are ", "definition of ", "define ",
    "what did we decide", "what did i say", "what was decided",
    "remind me", "recall ", "according to my",
)


def prefer_traceable_route(
    query: str,
    keywords: list[str] | tuple[str, ...] | None = None,
) -> bool:
    """
    Return True if the query should use Refine-only (traceable) path.
    If keywords is None, uses DEFAULT_PREFER_TRACEABLE.
    """
    q = query.strip().lower()
    if not q:
        return False
    kws = keywords if keywords is not None else DEFAULT_PREFER_TRACEABLE
    return any(q.startswith(k) or k in q for k in kws)
