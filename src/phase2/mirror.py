"""
Mirror: user profile, goals, and episodic memory.

Persist conversations and user-related facts; write-back after each turn.
Retrieval can merge corpus slice + recent episodes + profile for context.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROFILE_JSON = "profile.json"
EPISODES_JSONL = "episodes.jsonl"


def get_mirror_dir(base_dir: Path) -> Path:
    """Return mirror directory under base_dir (e.g. data/mirror)."""
    return Path(base_dir) / "mirror"


def load_profile(mirror_dir: Path) -> dict[str, Any]:
    """Load profile.json; return default structure if missing."""
    path = Path(mirror_dir) / PROFILE_JSON
    if not path.exists():
        return {"goals": [], "preferences": {}, "tech_stack": [], "notes": ""}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_profile(mirror_dir: Path, profile: dict[str, Any]) -> None:
    """Write profile.json."""
    Path(mirror_dir).mkdir(parents=True, exist_ok=True)
    path = Path(mirror_dir) / PROFILE_JSON
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)


def load_episodes(mirror_dir: Path, last_n: int = 10) -> list[dict[str, Any]]:
    """Load last N episodes from episodes.jsonl (tail)."""
    path = Path(mirror_dir) / EPISODES_JSONL
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    episodes = []
    for line in lines:
        if not line.strip():
            continue
        try:
            episodes.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return episodes[-last_n:] if last_n else episodes


def append_episode(
    mirror_dir: Path,
    *,
    query: str = "",
    answer_summary: str = "",
    decisions: list[str] | None = None,
    code_snippets: list[str] | None = None,
    user_reminder: bool = False,
) -> None:
    """Append one episode to episodes.jsonl."""
    Path(mirror_dir).mkdir(parents=True, exist_ok=True)
    path = Path(mirror_dir) / EPISODES_JSONL
    import time
    rec = {
        "query": query,
        "answer_summary": answer_summary[:500] if answer_summary else "",
        "decisions": list(decisions or []),
        "code_snippets": list(code_snippets or []),
        "timestamp": time.time(),
        "user_reminder": user_reminder,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_back_turn(
    mirror_dir: Path,
    query: str,
    answer: str,
    *,
    decisions: list[str] | None = None,
    code_snippets: list[str] | None = None,
    user_reminder: bool = False,
) -> None:
    """
    After each turn: append episode with query, answer summary, decisions, code.
    Optionally extract goals/preferences (simple keyword pass) and merge into profile.
    """
    summary = answer[:500] + ("..." if len(answer) > 500 else "")
    append_episode(
        mirror_dir,
        query=query,
        answer_summary=summary,
        decisions=decisions,
        code_snippets=code_snippets,
        user_reminder=user_reminder,
    )


def add_goal(mirror_dir: Path, goal: str) -> None:
    """Add a goal to profile.goals if not already present."""
    profile = load_profile(mirror_dir)
    goals = list(profile.get("goals", []))
    if goal.strip() and goal.strip() not in goals:
        goals.append(goal.strip())
        profile["goals"] = goals
        save_profile(mirror_dir, profile)


def get_mirror_context(mirror_dir: Path, last_n_episodes: int = 5) -> str:
    """
    Build a context string from profile and recent episodes for inclusion in retrieval.
    Used by context assembly (Phase 4) so LLM/Refine see goals and recent conversation.
    """
    profile = load_profile(mirror_dir)
    episodes = load_episodes(mirror_dir, last_n=last_n_episodes)
    parts = []
    goals = profile.get("goals", [])
    if goals:
        parts.append("## Goals\n" + "\n".join(f"- {g}" for g in goals))
    prefs = profile.get("preferences", {})
    if prefs:
        parts.append("## Preferences\n" + json.dumps(prefs, indent=0))
    notes = profile.get("notes", "").strip()
    if notes:
        parts.append("## Notes\n" + notes)
    if episodes:
        parts.append("## Recent conversation")
        for ep in episodes:
            q = ep.get("query", "")
            a = ep.get("answer_summary", "")
            if q or a:
                parts.append(f"Q: {q}\nA: {a}")
    return "\n\n".join(parts) if parts else ""
