"""Regression tests for embed_pending fail-silent behaviour.

Root cause: fastembed stores the ONNX model in %TEMP%/fastembed_cache/ which
Windows cleans up, leaving the snapshot directory but removing model.onnx.
The stop hook must never raise -- it should return 0 and let Claude Code exit cleanly.
"""
from __future__ import annotations
from unittest.mock import MagicMock, patch


def _mock_conn(rows: list) -> MagicMock:
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = rows
    return conn


class TestEmbedPendingFailSilent:
    def test_returns_zero_when_no_pending_rows(self):
        with patch("sidekick.db.connect", return_value=_mock_conn([])):
            from sidekick import indexer
            assert indexer.embed_pending() == 0

    def test_returns_zero_not_raises_when_onnx_model_missing(self):
        """Reproduces: corrupt/missing ONNX cache crashes the stop hook."""
        rows = [("ses-abc", 0, "hello world")]
        with patch("sidekick.db.connect", return_value=_mock_conn(rows)), \
             patch("sidekick.embeddings.TextEmbedding",
                   side_effect=Exception("[ONNXRuntimeError] : 3 : NO_SUCHFILE : model.onnx")):
            from sidekick import indexer
            result = indexer.embed_pending()
        assert result == 0

    def test_returns_zero_not_raises_on_generic_embedder_error(self):
        """Any unexpected error from the embedder must not propagate to the hook."""
        rows = [("ses-xyz", 1, "some text")]
        with patch("sidekick.db.connect", return_value=_mock_conn(rows)), \
             patch("sidekick.embeddings.TextEmbedding", side_effect=RuntimeError("download failed")):
            from sidekick import indexer
            result = indexer.embed_pending()
        assert result == 0
