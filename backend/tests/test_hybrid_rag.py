import unittest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
import numpy as np
from app import rag_service


class HybridRagTests(unittest.TestCase):
    def test_scope_dates_and_confidence_precede_reranking(self):
        allowed = {
            "chunk_id": "a",
            "filename": "allowed.pdf",
            "page": 2,
            "text": "credit rate policy",
            "report_date": "2026-09-11",
            "confidence": 0.95,
        }
        future = {**allowed, "chunk_id": "future", "report_date": "2027-01-01"}
        forbidden = {**allowed, "chunk_id": "forbidden", "filename": "private.pdf"}
        low = {**allowed, "chunk_id": "low", "confidence": 0.2}
        model = MagicMock()
        model.encode.return_value = np.array([[1.0, 0.0, 0.0]])
        rank = MagicMock()
        rank.predict.return_value = np.array([2.0])
        q = MagicMock()
        q.query_points.return_value = SimpleNamespace(
            points=[
                SimpleNamespace(payload=c, score=0.9)
                for c in [allowed, future, forbidden, low]
            ]
        )
        with (
            patch.object(
                rag_service,
                "active",
                return_value={
                    "collection": "test",
                    "chunks": [allowed, future, forbidden, low],
                },
            ),
            patch.object(rag_service, "embedding", return_value=model),
            patch.object(rag_service, "reranker", return_value=rank),
            patch.object(rag_service, "client", return_value=q),
        ):
            result = rag_service.retrieve(
                "credit rate", filenames=["allowed.pdf"], as_of="2026-10-25"
            )
        self.assertEqual([c["chunk_id"] for c in result], ["a"])
        self.assertEqual(result[0]["page"], 2)
        self.assertEqual(len(q.query_points.call_args.kwargs["query_filter"].must), 2)

    def test_no_active_corpus_never_loads_models(self):
        with (
            patch.object(rag_service, "active", return_value=None),
            patch.object(rag_service, "embedding") as model,
        ):
            self.assertEqual(rag_service.retrieve("query"), [])
            model.assert_not_called()

    def test_missing_artifact_never_downloads(self):
        import os, tempfile

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(os.environ, {"BGE_MODEL_PATH": tmp + "/missing"}),
        ):
            # No sentence_transformers import is needed to determine that an artifact is absent.
            with self.assertRaises((RuntimeError, ImportError)):
                rag_service.embedding()
