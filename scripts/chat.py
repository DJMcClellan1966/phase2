"""
Run Phase2 chat REPL from project root: python scripts/chat.py

Ensures src is on PYTHONPATH so phase2 can be imported.
"""

import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if str(root / "src") not in sys.path:
    sys.path.insert(0, str(root / "src"))

from phase2.chat import load_config, run_repl

if __name__ == "__main__":
    config = load_config(root)
    store_dir = Path(config["store_dir"])
    if not store_dir.is_absolute():
        store_dir = root / store_dir
    persist_path = store_dir / "conversation.jsonl"
    run_repl(config=config, base_dir=root, persist_conversation_path=persist_path)
