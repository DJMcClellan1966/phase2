"""
Build corpus and slice index from input sources.

Scans a directory or manifest of inputs (text files, JSONL, past episodes),
assigns ids, writes data/corpus/sentences.jsonl and data/corpus/slice_index.json.
Vocabulary: term -> list of sentence ids containing that term (for query resolution).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SENTENCES_JSONL = "sentences.jsonl"
SLICE_INDEX_JSON = "slice_index.json"
CORPUS_DIR = "corpus"


def _tokenize(text: str) -> list[str]:
    """Lowercase, extract words (letters, optional apostrophe/dash)."""
    return [w for w in re.findall(r"[a-z][a-z'-]*[a-z]|[a-z]", text.lower()) if len(w) > 1]


# Common stop words to skip in vocabulary (optional)
_STOP = frozenset(
    {"a", "an", "the", "is", "are", "was", "were", "be", "been", "have", "has", "had",
     "do", "does", "did", "will", "would", "and", "or", "but", "not", "no", "in", "on",
     "at", "to", "for", "of", "with", "by", "from", "that", "this", "it", "its", "as"}
)


def _collect_inputs(
    input_paths: list[Path],
    *,
    extensions: tuple[str, ...] = (".txt", ".jsonl", ".json"),
) -> list[tuple[str, str | None, str | None]]:
    """
    Collect (text, term, genre_id) from files.
    - .txt: whole file content as one sentence; term=None, genre_id=None.
    - .jsonl: one JSON per line with "text", optional "term", "genre_id", "source".
    """
    out: list[tuple[str, str | None, str | None]] = []
    for path in input_paths:
        if not path.exists():
            continue
        suf = path.suffix.lower()
        if suf == ".txt":
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                out.append((text, None, None))
        elif suf == ".jsonl":
            for line in path.open(encoding="utf-8", errors="replace"):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    t = obj.get("text") or obj.get("definition") or ""
                    if t:
                        out.append((t, obj.get("term"), obj.get("genre_id")))
                except json.JSONDecodeError:
                    pass
        elif suf == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
                if isinstance(data, list):
                    for item in data:
                        t = (item.get("text") or item.get("definition") or "") if isinstance(item, dict) else ""
                        if t:
                            out.append((t, item.get("term") if isinstance(item, dict) else None,
                                        item.get("genre_id") if isinstance(item, dict) else None))
                elif isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, str) and v:
                            out.append((v, k, None))
                else:
                    pass
            except (json.JSONDecodeError, TypeError):
                pass
    return out


def build_corpus(
    output_dir: Path,
    input_paths: list[Path],
    *,
    corpus_subdir: str = CORPUS_DIR,
) -> tuple[Path, Path]:
    """
    Write sentences.jsonl and slice_index.json under output_dir/corpus_subdir.
    Returns (path_to_sentences_jsonl, path_to_slice_index_json).
    """
    corpus_dir = output_dir / corpus_subdir
    corpus_dir.mkdir(parents=True, exist_ok=True)
    sentences_path = corpus_dir / SENTENCES_JSONL
    index_path = corpus_dir / SLICE_INDEX_JSON

    rows = _collect_inputs(input_paths)
    ids: list[int] = []
    id_to_offset: dict[int, int] = {}
    term_to_ids: dict[str, list[int]] = {}

    with open(sentences_path, "w", encoding="utf-8") as f:
        for i, (text, term, genre_id) in enumerate(rows):
            sid = i
            offset = f.tell()
            rec = {"id": sid, "text": text}
            if term is not None:
                rec["term"] = term
            if genre_id is not None:
                rec["genre_id"] = genre_id
            rec["source"] = "build_corpus"
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            ids.append(sid)
            id_to_offset[sid] = offset
            for w in _tokenize(text):
                if w not in _STOP:
                    term_to_ids.setdefault(w, []).append(sid)
            if term:
                t = term.strip().lower()
                if t and t not in term_to_ids:
                    term_to_ids.setdefault(t, []).append(sid)

    # Deduplicate term_to_ids lists (keep order)
    vocabulary: dict[str, list[int]] = {}
    for term, id_list in term_to_ids.items():
        vocabulary[term] = list(dict.fromkeys(id_list))

    index_payload = {
        "ids": ids,
        "id_to_offset": id_to_offset,
        "sentences_file": SENTENCES_JSONL,
        "vocabulary": vocabulary,
    }
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_payload, f, indent=0)

    return sentences_path, index_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build corpus and slice index")
    parser.add_argument("inputs", nargs="+", type=Path, help="Input files or directories")
    parser.add_argument("-o", "--output-dir", type=Path, default=Path("data"), help="Output directory (default: data)")
    parser.add_argument("--corpus-dir", default=CORPUS_DIR, help="Subdir under output (default: corpus)")
    args = parser.parse_args()

    input_paths: list[Path] = []
    for p in args.inputs:
        p = p.resolve()
        if p.is_file():
            input_paths.append(p)
        elif p.is_dir():
            for ext in (".txt", ".jsonl", ".json"):
                input_paths.extend(p.glob(f"**/*{ext}"))

    if not input_paths:
        print("No input files found")
        return
    base = Path(__file__).resolve().parent.parent
    out_dir = args.output_dir if args.output_dir.is_absolute() else base / args.output_dir
    s_path, i_path = build_corpus(out_dir, input_paths, corpus_subdir=args.corpus_dir)
    print(f"Wrote {s_path} and {i_path}")


if __name__ == "__main__":
    main()
