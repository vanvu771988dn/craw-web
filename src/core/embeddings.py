import math
from dataclasses import dataclass

from src.utils.content_utils import extract_meaningful_tokens


@dataclass(frozen=True, slots=True)
class HashingEmbeddingConfig:
    dimensions: int = 128


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def build_hashing_embedding(text: str | None, config: HashingEmbeddingConfig | None = None) -> list[float]:
    """Builds a deterministic lightweight embedding using hashed token buckets."""
    cfg = config or HashingEmbeddingConfig()
    vector = [0.0] * max(cfg.dimensions, 8)
    for token in extract_meaningful_tokens(text):
        index = hash(token) % len(vector)
        vector[index] += 1.0
    return _normalize_vector(vector)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return max(0.0, min(1.0, sum(a * b for a, b in zip(left, right))))


def compute_hashing_embedding_similarity(
    left_text: str | None,
    right_text: str | None,
    *,
    dimensions: int = 128,
) -> float:
    config = HashingEmbeddingConfig(dimensions=dimensions)
    left = build_hashing_embedding(left_text, config)
    right = build_hashing_embedding(right_text, config)
    return round(cosine_similarity(left, right), 4)
