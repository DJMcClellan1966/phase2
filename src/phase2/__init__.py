"""
Phase 2: Dynamic corpus + traceable local agent.

Exploration package for:
- Demand-driven corpus loading (slice store pattern from Dictionary).
- Traceable answers (Anchor-style Refine: every span from store).
- Corpus that grows (user/Mirror) and shrinks (cold/prune).

See docs/EXPLORATION.md for design and references to dictionary, scratchLLM, align, anchor.
"""

from .dynamic_corpus import SliceIndex, load_slice_from_store
from .retrieval import retrieve_context, retrieve_context_with_mirror
from .traceable_agent import (
    SourceRecord,
    TraceableAnswer,
    build_traceable_answer,
    prefer_traceable_route,
)

__all__ = [
    "SliceIndex",
    "load_slice_from_store",
    "retrieve_context",
    "retrieve_context_with_mirror",
    "SourceRecord",
    "TraceableAnswer",
    "build_traceable_answer",
    "prefer_traceable_route",
]
