# Phase 2: Dynamic Corpus + Traceable Local Agent

Explore a **local-only, non-hallucinatory, traceable, grounded** agent (dictionary-style) using a **corpus that grows and changes based on need** — a large store that is not necessarily loaded in full every time.

## Goal

- **Local only** — no cloud; all data and compute on your machine.
- **Non-hallucinatory** — answers only from stored corpus + dictionary (Anchor-style Refine; Dictionary rules-first).
- **Traceable** — every part of an answer maps to a source (sentence id, definition term, chunk).
- **Grounded** — like a dictionary: definitions and retrieved sentences only.
- **Dynamic corpus** — store grows (user/Mirror/additions) and can shrink (prune, archive, cold storage); **demand-driven loading** so the full corpus is not needed every time.

## Where the ideas come from

This project builds on theories and code from sibling projects on your Desktop:

| Project    | Ideas used |
|-----------|------------|
| **dictionary** | On-demand graph (slice store), vocabulary + slice index at startup, per-query transient graph; information basis; provenance. |
| **scratchLLM** | User-based corpus, truth base, intent-driven helpers that grow from use; formal-only response path. |
| **align**      | Mirror (user corpus that grows), concept-style retrieval, episodic sync. |
| **anchor**     | Graph-grounded LLM, Refine (traceable by construction), evidence engine, unified data store; Theorem 4. |

## Docs

- **[docs/EXPLORATION.md](docs/EXPLORATION.md)** — Full exploration: theories, dynamic corpus design, data creation, “model that grows/shrinks,” proposed architecture, open questions.

## Layout

- `config/app.json` — Store dir, Ollama URL, model, prefer-traceable keywords.
- `data/corpus/` — `sentences.jsonl`, `slice_index.json` (build with `scripts/build_corpus.py`).
- `data/mirror/` — `profile.json`, `episodes.jsonl` (goals, preferences, conversation write-back).
- `src/phase2/` — Package: `dynamic_corpus`, `retrieval`, `traceable_agent`, `mirror`, `llm_client`, `chat`.
- `scripts/build_corpus.py` — Build corpus and slice index from inputs.

## Quick start

1. **Build corpus** (one-time):  
   `python scripts/build_corpus.py data/corpus/seed.jsonl -o data`
2. **Run chat** (from project root):  
   `python scripts/chat.py`  
   Try "what is a function?" (traceable); other questions use Ollama if running.  
   Commands: `Remember this: ...`, `My goal is ...`, `quit`.
3. Edit `config/app.json` for Ollama and keywords.

## Quick start (experiments)

1. Read `docs/EXPLORATION.md` for the full picture.
2. Use Dictionary’s on-demand mode as reference:  
   In the dictionary repo, set `USE_ON_DEMAND_GRAPH=1` and run the web app; see `basis_engine.py` and `basis_layers/slice_store.py`.
3. Use Anchor’s Refine + evidence engine for traceability:  
   In the anchor repo, see `graph_attention.py` (Refine, `return_sources=True`), `evidence_engine.py`, and `docs/ANCHOR_THEOREMS.md`.
4. Extend from here: implement a **slice store** for your own corpus (e.g. sentence/chunk id → file/offset), then a **query → load slice → activate → refine** pipeline that returns answers with source records.

## Data / model growth and compression

- **Data:** Create content via bulk import (Dictionary/Anchor/scratchLLM scripts) and incremental growth (Mirror, user additions). Optionally compress cold corpus (e.g. gzip JSONL) and keep a hot index.
- **“Model”:** The in-memory “model” is the **working set** (transient graph + sentence set) for the current query; it grows when you load a slice and shrinks when you drop it. An optional small parametric model (e.g. scratchLLM-style) can grow/shrink with the corpus for fluency; keep answers traceable by making Refine the authority and the LM only rank or suggest from store-backed candidates.
