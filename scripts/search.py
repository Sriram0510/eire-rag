"""Semantic search from the command line.

Usage:  uv run python scripts/search.py "how much does stamp 1g cost"
"""

import sys

from eire_rag.db import connect
from eire_rag.embeddings import embed_query

TOP_K = 5


def main() -> None:
    question = " ".join(sys.argv[1:]) or "How much does it cost to register for Stamp 1G?"
    qvec = embed_query(question)

    with connect() as conn:
        rows = conn.execute(
            """SELECT embedding <=> %s AS distance, title, section, url, text
               FROM chunks
               ORDER BY embedding <=> %s
               LIMIT %s""",
            (qvec, qvec, TOP_K),
        ).fetchall()

    print(f"Question: {question}\n")
    for rank, (distance, title, section, url, text) in enumerate(rows, start=1):
        body = text.split("\n\n", 1)[-1].replace("\n", " ")
        print(f"#{rank}  distance {distance:.3f}  |  {title} > {section}")
        print(f"    {body[:220]}...")
        print(f"    {url}\n")


if __name__ == "__main__":
    main()