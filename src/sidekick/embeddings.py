"""Embeddings via fastembed (ONNX MiniLM). 384 dims, L2-normalized."""
from __future__ import annotations
import numpy as np
from fastembed import TextEmbedding

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

class Embedder:
    def __init__(self) -> None:
        self._model = TextEmbedding(model_name=MODEL_NAME)
        self.dim = 384

    def embed_one(self, text: str) -> np.ndarray:
        v = next(iter(self._model.embed([text])))
        v = v.astype(np.float32)
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def embed_many(self, texts: list[str]) -> np.ndarray:
        out = list(self._model.embed(texts))
        arr = np.stack([v.astype(np.float32) for v in out])
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms

def to_blob(v: np.ndarray) -> bytes:
    return v.astype(np.float32).tobytes()

def from_blob(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32)
