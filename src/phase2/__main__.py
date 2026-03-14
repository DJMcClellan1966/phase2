"""
Run Phase2 chat REPL: python -m phase2

Requires: data/corpus/ with sentences.jsonl and slice_index.json (run scripts/build_corpus.py first).
Optional: Ollama running locally for LLM path; otherwise use traceable path for "what is X" style queries.
"""

from .chat import load_config, run_repl
from pathlib import Path

if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    config = load_config(base)
    store_dir = Path(config["store_dir"])
    if not store_dir.is_absolute():
        store_dir = base / store_dir
    persist_path = store_dir / "conversation.jsonl"
    run_repl(config=config, base_dir=base, persist_conversation_path=persist_path)
