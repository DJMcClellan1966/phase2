# Phase 2: Dynamic Corpus + Traceable Local Agent

**Goal:** A local-only LLM/agent that is **non-hallucinatory**, **every answer traceable**, and **grounded** (dictionary-like), using a **corpus that grows and changes based on need** — a large store that is not necessarily loaded or used in full every time.

This document ties together ideas from **dictionary**, **scratchLLM**, **align**, and **anchor** (on your Desktop) and explores how to extend them toward that goal.

---

## 1. Theories and Building Blocks (from Desktop projects)

### 1.1 Dictionary

- **Symbolic intelligence:** Concept-level understanding over a knowledge graph (definitions, relations, rules). No LLM by default; ingestion from web/dictionary only.
- **On-demand graph (slice store):** `USE_ON_DEMAND_GRAPH=1`: load only **vocabulary + slice index** at startup; the graph is built **per query** from a condensed store (`data/unified_basis/slice/` — JSONL + index). Each question triggers a gather of relevant `word_ids` and 1-hop neighbors, then a **transient graph** is built for the response. *This is the main “large corpus stored, not all needed every time” pattern.*
- **Information basis:** PMI, NPMI, entropy-weighted salience, etymological affinity — refines the graph without altering the live engine.
- **Provenance:** Every answer has a source (rule_engine, focus, cache, etc.). Sovereign mode, conscience, Decalogue health.
- **Relevant paths:** `slice_store.py` (write_slice_store, load_slice, load_slice_index), BasisEngine `on_demand=True`, `_ensure_slice_for_query`.

### 1.2 scratchLLM

- **User-based local LLM:** Model and corpus built from *the user’s* data (email, reading, bookmarks, etc.); responses grounded in that context.
- **Truth base:** Formal layer (e.g. `truth_base.jsonl`) for fast, non-hallucinatory answers without training.
- **Intent-driven helpers:** “Create helper from intent” → blank canvas that **grows** from what the user adds (no fixed preset corpus).
- **Fast path:** Formal-only response from truth base/IR; no checkpoint required.

### 1.3 Align

- **Mirror:** User-specific corpus that **grows** from profile and continued use (episodic traces, sync to Mirror).
- **Concept-grounded flow:** Concept bundle + genre/style sentences → retrieval → dictionary critic (score, accept/warn).
- **Shared info:** Profile, Mirror summary, meds, appointments passed into every app build.

### 1.4 Anchor

- **Dictionary as symbolic anchor:** Concept bundle from dictionary; style sentences; generation via **graph attention** (query → activate → traverse → pattern → refine) or corpus; **critic** scores against the graph.
- **Graph-grounded LLM:** CPU-only, non-hallucinatory by design: response = refinement of definitions + ordered sentences from the graph; no free-form generation.
- **Theorem 4 (Traceability):** Every token in the response has a **source** in **S** (sentence store) ∪ **D** (dictionary). Refine only concatenates substrings from the store; output is fully traceable.
- **Evidence engine:** Claim vs corpus → verdict (supported / divided / silent) + support/contradict sentences — no prose, no dictionary required for the evidence path.
- **Unified data store:** Dictionary and corpus live in the same sentence/index space; refinement prefers definition text from the encoded index.

---

## 2. What We Want in Phase 2

| Property | Meaning |
|--------|----------|
| **Local only** | No cloud inference; all data and compute on your machine. |
| **Non-hallucinatory** | Answers only from the stored corpus + dictionary (Anchor-style Refine; Dictionary rules-first + focus). |
| **Traceable** | Every span of the answer maps to a source: sentence id, definition term, or (future) chunk id. |
| **Grounded** | Like a dictionary: definitions, relations, and retrieved sentences are the only content. |
| **Dynamic corpus** | Corpus **grows** (user adds content, Mirror-style) and **shrinks** (prune, archive, or drop unused slices). |
| **Demand-driven** | Large corpus **stored** but not all loaded every time; load only what’s needed for the current query (slice-store / on-demand pattern). |

The main design challenge you flagged: **how to create and maintain the data/information** for the model, and whether **compression** plus a **model that grows/shrinks** with need can help.

---

## 3. Dynamic Corpus: “Stored vs Loaded”

### 3.1 Pattern: Slice store (from Dictionary)

- **Store:** Condensed, slice-friendly format (e.g. JSONL keyed by word/sentence/chunk id) with an **index** (ids + byte offsets or keys) for random access.
- **At startup:** Load only **vocabulary** (or global term index) and **slice index** (which ids exist, where to read them).
- **Per query:**  
  1. Resolve query to a set of **ids** (e.g. word ids, sentence ids, or chunk ids).  
  2. Optionally **expand** (e.g. 1-hop neighbors, similar sentences).  
  3. **Read only** those ids from the store (by offset or key).  
  4. Build a **transient** graph or retrieval structure for that query.  
  5. Run the existing pipeline (activate → propagate → pattern → refine) on the transient structure.  
  6. Discard or cache the transient structure as needed.

So: **one large corpus on disk**, **small working set per query**.

### 3.2 Extending to “corpus that grows and shrinks”

- **Grow:**  
  - User adds documents, Q&A, or definitions (Align Mirror, scratchLLM truth base, Dictionary ingestion).  
  - New items get new ids and are appended (or merged) into the slice store and index.  
  - Optional: background jobs to extract sentences/chunks and update the index.
- **Shrink:**  
  - **By need:** Evict or never load slices that haven’t been used for N days (or by recency/importance).  
  - **By compression:** Keep a “hot” index (e.g. recent + high-access) in a fast format; move cold data to a compressed archive (e.g. compressed JSONL, or a single compressed blob with an id→offset index).  
  - **By pruning:** Remove or archive low-value items (e.g. low retrieval score, never cited in answers).

So the **corpus** (the store) can grow without bound on disk, while the **working set** (what’s in memory or in the transient graph) stays bounded and demand-driven.

---

## 4. Data / Information for the Model

### 4.1 What to store

- **Definitions** (dictionary): term → text (and optionally structured triples, POS, etc.).  
- **Sentences / spans:** From corpus, Q&A, or user content; each with an id, optional `term`, `genre_id`, `source`.  
- **Graph edges:**  
  - Word–word (e.g. P(w'|w), co-occurrence, or relation edges).  
  - Word–sentence: which words appear in which sentence (for S(w)).  
  - Sentence–sentence: e.g. Jaccard or other similarity (for propagation).  
- **Index structures:**  
  - Term/vocabulary index (string ↔ id).  
  - Slice index: id → file/offset or id → key (for on-demand load).  
  - Optional: inverted index (term → sentence ids) for fast retrieval before propagation.

This matches Anchor’s **unified data store** and Dictionary’s **unified basis** (graph + definitions + sentence index).

### 4.2 How to create it

- **Bulk import:** One-time or periodic: Dictionary compile, scratchLLM corpus build, Anchor `build_corpus` / `build_corpus_from_webster` / `build_corpus_from_dictionary`.  
- **Incremental growth:**  
  - New documents/sentences appended to the store; index updated (new ids, new edges for new terms).  
  - Optional: run a lightweight “propagation” or “graph update” only on the new subgraph (Anchor/Dictionary style).  
- **From the user:**  
  - Align-style Mirror: profile + episodic traces → truth_base / sentences.  
  - scratchLLM-style “create helper from intent”: start minimal, add statements; each addition is new data.  
- **Data compression:**  
  - Store: compressed JSONL (e.g. gzip) or a binary format; index stays uncompressed for fast lookup.  
  - Optional: deduplicate sentences/chunks (hash → one canonical id); store only references in the graph.  
  - Cold data: move to a compressed archive and load on demand when a query hits that region.

### 4.3 “Model that grows/shrinks”

Here “model” can mean two things:

1. **Retrieval / graph “model” (no neural net):**  
   - The **in-memory** structure (transient graph, propagation state, sentence set) **grows** with the slice loaded for the query and **shrinks** when that slice is discarded or evicted from cache.  
   - So the “model” is exactly the **working set** of the corpus for the current (or recent) queries. No parameters; size is proportional to the slice size.

2. **Optional small parametric model (e.g. scratchLLM-style LM):**  
   - **Grow:** Train or fine-tune on newly added corpus (e.g. definitional sentences, user truth base); optionally scale up (more layers, larger vocab) if corpus grows.  
   - **Shrink:** Distill to a smaller model, or prune low-impact parameters; or keep a “tiny” model that only runs on the current slice’s vocabulary.  
   - For a **traceable, non-hallucinatory** agent, the primary answer should still come from **retrieval + Refine** (Anchor/Dictionary); the parametric model can suggest ordering or phrasing but the **citable content** should remain store-backed.

So: **primary design = demand-driven retrieval + Refine (traceable);** optional small parametric model that can grow/shrink with the corpus for fluency or ranking.

---

## 5. Proposed Architecture (Phase 2)

- **Store (on disk):**  
  - **Corpus store:** Sentences/chunks in a slice-friendly format (e.g. JSONL by id) + optional compression for cold data.  
  - **Graph store:** Edges (word–word, word–sentence, sentence–sentence) in slice-friendly form (e.g. per-node or per-sentence JSONL + index), as in Dictionary’s slice store.  
  - **Dictionary:** Terms and definitions (same as today; can be part of the same sentence store with `source: "dictionary"`).  
  - **Index:** Vocabulary + slice index (id → location); optionally inverted index for terms → ids.

- **Runtime:**  
  - Load **vocabulary + slice index** at startup (and optionally a small “warm” cache).  
  - **Per query:**  
    1. Resolve query to **term ids** and/or **sentence/chunk ids** (from intent + dictionary + optional retrieval).  
    2. **Load slice** from store (only those ids + optional 1-hop expansion).  
    3. Build **transient** graph and sentence set.  
    4. Run **Anchor-style pipeline:** activate → propagate → pattern → refine (or Dictionary rules-first + focus).  
    5. **Refine** only from store-backed definitions and sentences → **traceable** output (Theorem 4 style).  
    6. Optionally **update usage stats** (for growth/shrink policies) and **cache** the slice for a short TTL.

- **Growth:**  
  - New content → append to corpus store + update index + optionally update graph edges for new terms.  
  - Mirror/episodic/user input → same pipeline.

- **Shrink:**  
  - Cold slices: don’t load unless queried; optionally move to compressed archive.  
  - Prune or archive low-value or never-accessed items in the index.

---

## 6. Open Questions and Experiments

1. **Chunking:** Use sentences (Anchor/Dictionary) or larger chunks (e.g. paragraphs)? Trade-off: finer traceability vs coarser context.  
2. **Compression:** Which format (gzip JSONL, msgpack, custom) and for which parts (cold store only vs full)? Measure read latency vs size.  
3. **Slice size:** How many nodes/sentences per query (fixed cap vs 1-hop vs 2-hop)? Balance quality vs memory and latency.  
4. **Parametric model:** If any: role (ranking, fluency, expansion) and how to keep answers traceable (e.g. only rank/select from store-backed candidates).  
5. **Unified id space:** One global id space for sentences, definitions, and chunks so that Refine and evidence engine share the same source set.

---

## 7. References (paths on your machine)

- **Dictionary:** `C:\Users\DJMcC\OneDrive\Desktop\dictionary`  
  - On-demand: `USE_ON_DEMAND_GRAPH=1`, `basis_engine.py` (`on_demand`, `_ensure_slice_for_query`), `basis_layers/slice_store.py`.  
  - Information basis: `information_basis.py`.  
- **scratchLLM:** `C:\Users\DJMcC\OneDrive\Desktop\scratchLLM`  
  - Truth base, intent, formal-only response, create-helper-from-intent.  
- **Align:** `C:\Users\DJMcC\OneDrive\Desktop\align`  
  - Mirror, concept-style retrieval, episodic sync.  
- **Anchor:** `C:\Users\DJMcC\OneDrive\Desktop\anchor`  
  - Graph attention, Refine, Theorem 4 (traceability), evidence engine, unified data store; `docs/ANCHOR_THEOREMS.md`, `docs/UNIFIED_MATH_MODEL.md`.

This exploration doc is the starting point for phase2: reuse these building blocks and experiment with dynamic, demand-driven corpus and a strictly traceable, grounded local agent.

---

## 8. Phase 2 code scaffold

- **`src/phase2/dynamic_corpus.py`** — `SliceIndex` (ids, id_to_location, vocabulary) and `load_slice_from_store(store_dir, ids, index)` for demand-driven loading. Extend with 1-hop expansion and your own store format.
- **`src/phase2/traceable_agent.py`** — `TraceableAnswer` (text + list of `SourceRecord`) and `build_traceable_answer(query, slice_records, ...)` placeholder. Replace with Anchor-style activate → propagate → pattern → refine using the loaded slice.
- Wire the two: resolve query → ids → load_slice_from_store → build_traceable_answer so that every answer is traceable and only uses the on-demand slice.
