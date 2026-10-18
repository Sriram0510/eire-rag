"""One place for everything about the embedding model.

Ingestion and search MUST use the same model: vectors from two different
models live in different "spaces" and comparing them is meaningless.
"""

from functools import lru_cache

import numpy as np
from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIM = 384  # this model outputs 384 numbers per text
# bge models are trained to see this instruction in front of short search queries
# (not in front of the passages being searched).
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@lru_cache(maxsize=1)
def get_model() -> TextEmbedding:
    # Downloads the model (~70 MB) on first use, then loads it from a local cache.
    return TextEmbedding(MODEL_NAME)


def embed_passages(texts: list[str], batch_size: int = 32) -> list[np.ndarray]:
    return list(get_model().embed(texts, batch_size=batch_size))


def embed_query(question: str) -> np.ndarray:
    return next(iter(get_model().embed([QUERY_PREFIX + question])))