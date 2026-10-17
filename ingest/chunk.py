"""Split clean documents into search-sized chunks along their headings.

Each chunk carries its page title and section path (e.g. "Conditions"), so
search can match on context and answers can cite the exact section.
"""

import json
import re
from pathlib import Path

DOCS_FILE = Path("data/processed/docs.jsonl")
CHUNKS_FILE = Path("data/processed/chunks.jsonl")
MAX_WORDS = 300   # upper limit per chunk (about 400 tokens, under the embedder's 512)
MIN_WORDS = 40    # sections smaller than this get merged with the next one
OVERLAP_WORDS = 40  # when a long section is split, repeat this much context

HEADING = re.compile(r"^(#{2,6})\s+(.*)$")
FOOTER = re.compile(r"\s*This page was last updated on [A-Z][a-z]+ \d{1,2}, \d{4}\.?")


def split_sections(text: str) -> list[tuple[list[str], str]]:
    """Return (heading path, body) pairs, e.g. (["Duration", "Up to 24 months"], "...")."""
    sections = []
    path: list[str] = []
    levels: list[int] = []
    buf: list[str] = []

    def flush():
        body = "\n".join(buf).strip()
        if body:
            sections.append((list(path), body))
        buf.clear()

    for line in text.splitlines():
        m = HEADING.match(line)
        if m:
            flush()
            level, title = len(m.group(1)), m.group(2).strip().strip("*").strip()
            while levels and levels[-1] >= level:
                levels.pop()
                path.pop()
            levels.append(level)
            path.append(title)
        else:
            buf.append(line)
    flush()
    return sections


def merge_small(sections):
    """Merge sections under MIN_WORDS into the following one (same page).

    A merged chunk keeps ALL its section names, e.g. "Required documents; How to apply",
    so its label never hides what is inside it.
    """
    merged = []
    carry_paths, carry_body = [], ""
    for path, body in sections:
        paths = [path]
        if carry_body:
            heading = " > ".join(path)
            body = f"{carry_body}\n\n{heading}:\n{body}" if heading else f"{carry_body}\n\n{body}"
            paths = carry_paths + paths
            carry_paths, carry_body = [], ""
        if len(body.split()) < MIN_WORDS:
            carry_paths, carry_body = paths, body
        else:
            merged.append((paths, body))
    if carry_body:
        if merged:
            last_paths, last_body = merged.pop()
            merged.append((last_paths + carry_paths, f"{last_body}\n\n{carry_body}"))
        else:
            merged.append((carry_paths, carry_body))
    return merged


def split_long(body: str) -> list[str]:
    """Split a long section on paragraph boundaries, with a little overlap."""
    if len(body.split()) <= MAX_WORDS:
        return [body]
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    pieces, current = [], []
    for para in paragraphs:
        words = para.split()
        if len(words) > MAX_WORDS:  # one huge paragraph: cut it by words
            for i in range(0, len(words), MAX_WORDS - OVERLAP_WORDS):
                pieces.append(" ".join(words[i:i + MAX_WORDS]))
            continue
        if current and len(" ".join(current).split()) + len(words) > MAX_WORDS:
            pieces.append("\n\n".join(current))
            tail = " ".join(" ".join(current).split()[-OVERLAP_WORDS:])
            current = [f"... {tail}"]
        current.append(para)
    if current:
        pieces.append("\n\n".join(current))
    return pieces


def main() -> None:
    n_docs, chunks = 0, []
    with DOCS_FILE.open(encoding="utf-8") as f:
        for line in f:
            doc = json.loads(line)
            n_docs += 1
            text = FOOTER.sub("", doc["text"]).strip()
            sections = merge_small(split_sections(text))
            for paths, body in sections:
                section = "; ".join(" > ".join(p) or "Overview" for p in paths)
                for part_no, piece in enumerate(split_long(body)):
                    chunks.append({
                        "chunk_id": f"{doc['doc_id']}#{len(chunks)}",
                        "doc_id": doc["doc_id"],
                        "url": doc["url"],
                        "title": doc["title"],
                        "section": section,
                        "part": part_no,
                        "lastmod": doc["lastmod"],
                        # What gets embedded: context header + the chunk itself
                        "text": f"{doc['title']} > {section}\n\n{piece}",
                        "n_words": len(piece.split()),
                    })

    with CHUNKS_FILE.open("w", encoding="utf-8") as out:
        for c in chunks:
            out.write(json.dumps(c, ensure_ascii=False) + "\n")

    sizes = sorted(c["n_words"] for c in chunks)
    print(f"{n_docs} documents -> {len(chunks)} chunks -> {CHUNKS_FILE}")
    print(f"Words per chunk: min {sizes[0]}, median {sizes[len(sizes) // 2]}, max {sizes[-1]}")
    print(f"Chunks under {MIN_WORDS} words: {sum(s < MIN_WORDS for s in sizes)}")


if __name__ == "__main__":
    main()