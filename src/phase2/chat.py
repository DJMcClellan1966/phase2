"""
Chat pipeline: context assembly, Refine vs LLM routing, and (in Phase 5) REPL + write-back.

Assembles context from corpus + Mirror; routes to traceable Refine or local LLM;
returns answer with optional sources.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import mirror as mirror_mod
from .llm_client import generate as llm_generate
from .retrieval import retrieve_context_with_mirror
from . import traceable_agent

CONFIG_NAME = "app.json"


def load_config(base_dir: Path | None = None) -> dict[str, Any]:
    """Load config from config/app.json under base_dir or cwd."""
    base = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent
    config_path = base / "config" / CONFIG_NAME
    if not config_path.exists():
        return {
            "store_dir": str(base / "data"),
            "corpus_subdir": "corpus",
            "ollama_base_url": "http://localhost:11434",
            "model_name": "llama3.2",
            "max_tokens": 1024,
            "prefer_traceable_keywords": [],
        }
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def assemble_context(
    corpus_records: list[dict[str, Any]],
    mirror_context: str,
    conversation_history: list[dict[str, str]],
) -> str:
    """
    Build a single context block string: corpus snippets, Mirror (goals, recent conv), then history.
    """
    parts = []
    if corpus_records:
        parts.append("## Context from your notes and history")
        for r in corpus_records[:15]:
            text = r.get("text") or r.get("definition") or ""
            if text:
                parts.append(text.strip())
    if mirror_context.strip():
        parts.append(mirror_context.strip())
    if conversation_history:
        parts.append("## Recent conversation")
        for msg in conversation_history[-10:]:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role and content:
                parts.append(f"{role}: {content[:300]}")
    return "\n\n".join(parts) if parts else ""


def route_and_answer(
    query: str,
    *,
    config: dict[str, Any] | None = None,
    base_dir: Path | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> tuple[str, bool, list[dict[str, Any]]]:
    """
    Run retrieval, then either Refine (traceable) or LLM (fluent).
    Returns (answer_text, is_traceable, source_summary_list).
    """
    cfg = config or load_config(base_dir)
    base = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent
    store_dir = Path(cfg["store_dir"])
    if not store_dir.is_absolute():
        store_dir = base / store_dir
    corpus_dir = store_dir / cfg.get("corpus_subdir", "corpus")
    mirror_dir = store_dir / "mirror"
    history = list(conversation_history or [])

    keywords = cfg.get("prefer_traceable_keywords")
    use_traceable = traceable_agent.prefer_traceable_route(query, keywords=keywords)

    records, mirror_context = retrieve_context_with_mirror(
        query,
        corpus_dir,
        mirror_dir=mirror_dir,
        max_items=20,
        last_n_episodes=5,
    )

    if use_traceable and records:
        traceable = traceable_agent.build_traceable_answer(
            query, records, max_sentences=10, max_definitions=3
        )
        return traceable.text, True, traceable.source_summary()

    # LLM path
    context_block = assemble_context(records, mirror_context, history)
    system = (
        "You are a local assistant. Prefer answers from the context when possible. "
        "For code, use the style and constraints from context. Be concise."
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    if context_block:
        messages.append({"role": "user", "content": f"Context:\n{context_block}\n\nDo not repeat the context verbatim. Use it to answer the following."})
        messages.append({"role": "assistant", "content": "Understood. I will use the context to answer."})
    for m in history[-10:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": query})

    try:
        answer = llm_generate(
            messages,
            base_url=cfg.get("ollama_base_url", "http://localhost:11434"),
            model=cfg.get("model_name", "llama3.2"),
            max_tokens=cfg.get("max_tokens", 1024),
        )
    except Exception as e:
        answer = f"[LLM error: {e}. Try Refine-only for traceable answers.]"
    sources = [{"type": "llm", "id": "generated", "preview": answer[:80] + "..."}] if answer else []
    return answer, False, sources


REMEMBER_PREFIX = "remember this:"
MY_GOAL_PREFIX = "my goal is"


def run_repl(
    *,
    config: dict[str, Any] | None = None,
    base_dir: Path | None = None,
    persist_conversation_path: Path | None = None,
) -> None:
    """
    REPL loop: read user input, route and answer, write-back to Mirror, optional persist.
    Commands: "Remember this: ..." appends to Mirror as user_reminder; "My goal is ..." adds to profile goals.
    """
    cfg = config or load_config(base_dir)
    base = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent
    store_dir = Path(cfg["store_dir"])
    if not store_dir.is_absolute():
        store_dir = base / store_dir
    mirror_dir = store_dir / "mirror"

    conversation: list[dict[str, str]] = []
    if persist_conversation_path and Path(persist_conversation_path).exists():
        try:
            for line in Path(persist_conversation_path).read_text(encoding="utf-8").strip().splitlines():
                if line.strip():
                    import json as _json
                    conversation.append(_json.loads(line))
        except Exception:
            pass

    print("Phase2 chat (local). Commands: 'Remember this: ...' | 'My goal is ...' | 'quit'")
    while True:
        try:
            line = input("You: ").strip()
        except EOFError:
            break
        if not line:
            continue
        if line.lower() == "quit":
            break

        # Remember this: ...
        if line.lower().startswith(REMEMBER_PREFIX):
            text = line[len(REMEMBER_PREFIX):].strip()
            if text:
                mirror_mod.write_back_turn(mirror_dir, "", text, user_reminder=True)
                print("Saved to Mirror.")
            continue

        # My goal is ...
        if line.lower().startswith(MY_GOAL_PREFIX):
            goal = line[len(MY_GOAL_PREFIX):].strip()
            if goal:
                mirror_mod.add_goal(mirror_dir, goal)
                print("Goal added.")
            continue

        answer, is_traceable, sources = route_and_answer(
            line, config=cfg, base_dir=base, conversation_history=conversation
        )
        print("Assistant:", answer)
        if is_traceable and sources:
            print("  [Traceable:", len(sources), "sources]")

        mirror_mod.write_back_turn(mirror_dir, query=line, answer=answer)
        conversation.append({"role": "user", "content": line})
        conversation.append({"role": "assistant", "content": answer})
        if len(conversation) > 20:
            conversation = conversation[-20:]

        if persist_conversation_path:
            path = Path(persist_conversation_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"role": "user", "content": line}) + "\n")
                f.write(json.dumps({"role": "assistant", "content": answer}) + "\n")

    print("Bye.")
