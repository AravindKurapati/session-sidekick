import numpy as np
import pytest
from sidekick import embeddings

@pytest.fixture(scope="module")
def emb():
    return embeddings.Embedder()

def test_dimension(emb):
    assert emb.dim == 384

def test_embed_one(emb):
    v = emb.embed_one("hello world")
    assert v.shape == (384,)
    assert v.dtype == np.float32
    assert abs(np.linalg.norm(v) - 1.0) < 1e-3

def test_embed_many(emb):
    vs = emb.embed_many(["a", "b", "c"])
    assert vs.shape == (3, 384)

def test_to_blob_roundtrip(emb):
    v = emb.embed_one("roundtrip")
    blob = embeddings.to_blob(v)
    v2 = embeddings.from_blob(blob)
    np.testing.assert_array_equal(v, v2)
