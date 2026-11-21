"""Legacy vector packing helpers; HSPTL 4.0 product routes disable model inference."""
from __future__ import annotations

import math
import struct
from typing import Protocol, Sequence


class EmbeddingProvider(Protocol):
    """An explicitly injected repository adapter; never configured by the app."""
    name: str
    model: str

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class LocalSentenceTransformerProvider:
    """Compatibility sentinel: HSPTL 4.0 does not execute embedding models."""
    name = "disabled-model-free"

    def __init__(self, model: str = ""):
        raise RuntimeError(
            "Embedding models are disabled in HSPTL 4.0. Use deterministic lexical retrieval."
        )


def pack_vector(vector: Sequence[float]) -> bytes:
    if not vector or any(not math.isfinite(float(x)) for x in vector):
        raise ValueError("Embedding vector must contain finite values")
    return struct.pack(f"<{len(vector)}f", *[float(x) for x in vector])


def unpack_vector(blob: bytes, dimensions: int) -> list[float]:
    return list(struct.unpack(f"<{dimensions}f", blob))


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    norm_l = math.sqrt(sum(a * a for a in left))
    norm_r = math.sqrt(sum(b * b for b in right))
    return dot / (norm_l * norm_r) if norm_l and norm_r else 0.0
