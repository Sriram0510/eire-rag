"""Embed every chunk and load it into Postgres + pgvector.

Safe to re-run: it rebuilds the table contents inside one transaction,
so a failed run leaves the previous data untouched.
"""

import json
import time
from pathlib import Path

from eire_rag.db import connect
from eire_rag.embeddings import DIM, MODEL_NAME, embed_passages

CHUNKS_FILE = Path("data/processed/chunks.jsonl")
BATCH = 64

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id    text PRIMARY KEY,
    doc_id      text NOT NULL,
    url         text NOT NULL,
    title       text NOT NULL,
    section     text NOT NULL,
    part        int  NOT NULL,
    lastmod     timestamptz,
    n_words     int  NOT NULL,
    text        text NOT NULL,
    embed_model text NOT NULL,
    embedding   vector({DIM}) NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);
"""


def main() -> None:
    chunks = [json.loads(line) for line in CHUNKS_FILE.open(encoding="utf-8")]
    print(f"Loaded {len(chunks)} chunks. Embedding with {MODEL_NAME} ...")

    start = time.perf_counter()
    vectors = []
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        vectors.extend(embed_passages([c["text"] for c in batch]))
        print(f"  embedded {min(i + BATCH, len(chunks))}/{len(chunks)}")
    print(f"Embedding took {time.perf_counter() - start:.1f}s")

    with connect() as conn:
        conn.execute(SCHEMA)
        conn.execute("TRUNCATE chunks")
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO chunks (chunk_id, doc_id, url, title, section, part,
                                       lastmod, n_words, text, embed_model, embedding)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    (c["chunk_id"], c["doc_id"], c["url"], c["title"], c["section"],
                     c["part"], c["lastmod"] or None, c["n_words"], c["text"],
                     MODEL_NAME, v)
                    for c, v in zip(chunks, vectors)
                ],
            )
        count = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    print(f"Stored {count} chunks in Postgres.")


if __name__ == "__main__":
    main()