import os, tempfile, unittest, time, hmac, hashlib
from unittest.mock import patch, MagicMock
from app.storage import repositories as repo
from app.storage.db import transaction
from app.storage.models import Feedback
from sqlalchemy.exc import IntegrityError


class ProductTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {
                "APP_ENV": "test",
                "INSIGHT_DB_PATH": self.tmp.name + "/db.sqlite",
                "REDIS_URL": "",
            },
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def seed(self):
        repo.put_news([{"news_id": "N", "title": "News", "body": "Credit"}])
        event = {
            "card_id": "C",
            "news_id": "N",
            "audit": {"is_valid": True, "hallucination_detected": False},
            "title": "News",
        }
        repo.save_insight("A", "CFO", event, "v1")
        return event

    def test_transaction_rollback_and_foreign_keys(self):
        self.seed()
        with self.assertRaises(IntegrityError):
            with transaction() as s:
                s.add(Feedback(insight_id="missing", company_id="A", rating=3))
        with self.assertRaises(IntegrityError):
            with transaction() as s:
                s.add(Feedback(insight_id="C", company_id="A", rating=8))
        self.assertEqual(repo.feedback_metrics()["count"], 0)

    def test_audit_blocks_publication(self):
        e = self.seed()
        e["audit"]["is_valid"] = False
        with self.assertRaises(ValueError):
            repo.save_insight("A", "CFO", e, "v2")
        self.assertEqual(len(repo.feed("A", "CFO", "v1")), 1)
        self.assertEqual(repo.feed("A", "CFO", "v2"), [])

    def test_ingestion_is_idempotent_retains_old_on_failure(self):
        repo.put_news(
            [{"news_id": "N", "title": "News", "body": "One"}],
            {"loaded": ["s"], "counts": {"s": 1}},
        )
        repo.put_news([{"news_id": "N", "title": "News", "body": "One"}])
        repo.put_news([], {"failed": [{"source": "s"}]})
        self.assertEqual(len(repo.all_news()), 1)
        self.assertEqual(repo.source_status()["failed"][0]["source"], "s")

    def test_production_does_not_fall_back_to_sqlite(self):
        from app.settings import settings

        with patch.dict(
            os.environ, {"APP_ENV": "prod", "DATABASE_URL": "sqlite:///bad.db"}
        ):
            with self.assertRaises(ValueError):
                settings()

    def test_authorization_across_companies_and_cards(self):
        from app.main import app
        from fastapi.testclient import TestClient

        self.seed()
        client = TestClient(app)

        def identity(user):
            return {"user": "test", "companies": ["B"], "admin": False}

        with patch("app.security.identity", side_effect=identity):
            self.assertEqual(
                client.get("/api/feed", params={"company_id": "A"}).status_code, 403
            )
            self.assertEqual(
                client.post(
                    "/chat", json={"card_id": "C", "question": "Question"}
                ).status_code,
                404,
            )
            self.assertEqual(
                client.post(
                    "/feedback",
                    json={"insight_id": "C", "company_id": "B", "rating": 5},
                ).status_code,
                404,
            )
            self.assertEqual(client.get("/api/developer").status_code, 403)
        with patch("app.security.identity", return_value=None):
            self.assertEqual(client.get("/api/feed?company_id=A").status_code, 401)

    def test_gateway_signature_validation(self):
        from app.security import identity, signed_message
        from starlette.requests import Request

        stamp = str(int(time.time()))
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/feed",
            "query_string": b"company_id=A",
            "headers": [],
            "scheme": "https",
            "server": ("example.com", 443),
        }
        request = Request(scope)
        message = signed_message(request, stamp, "user", "A")
        signature = hmac.new(b"secret", message.encode(), hashlib.sha256).hexdigest()
        scope["headers"] = [
            (k.encode(), v.encode())
            for k, v in {
                "x-auth-timestamp": stamp,
                "x-auth-user": "user",
                "x-auth-companies": "A",
                "x-auth-signature": signature,
            }.items()
        ]
        with patch.dict(
            os.environ, {"REQUIRE_AUTH": "true", "GATEWAY_SIGNING_SECRET": "secret"}
        ):
            self.assertEqual(identity(Request(scope))["companies"], ["A"])
            scope["query_string"] = b"company_id=B"
            self.assertIsNone(identity(Request(scope)))

    def test_untrusted_xml_and_source_allowlist(self):
        from app.news_ingestion import parse_rss, safe_fetch
        from defusedxml.common import DefusedXmlException

        with self.assertRaises(DefusedXmlException):
            parse_rss(b'<!DOCTYPE r [<!ENTITY a "x">]><rss>&a;</rss>', "s")
        with self.assertRaises(ValueError):
            safe_fetch("http://127.0.0.1", 1)

    def test_readiness_database_failure(self):
        from app.main import app
        from fastapi.testclient import TestClient

        with patch("app.storage.db.engine", side_effect=RuntimeError("down")):
            self.assertEqual(TestClient(app).get("/health/ready").status_code, 503)

    def test_model_gateway_tracks_usage_without_prompts(self):
        from app.model_gateway import call
        from agent.models_cfg import PipelineTask, TASK_MODEL_MAPPING
        from types import SimpleNamespace
        from app.storage.models import ModelCall

        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=4),
        )
        self.assertEqual(
            call(
                client,
                PipelineTask.CLASSIFICATION,
                TASK_MODEL_MAPPING[PipelineTask.CLASSIFICATION],
                "secret prompt",
                "private profile",
                1,
            ),
            '{"ok":true}',
        )
        with transaction() as s:
            row = s.query(ModelCall).one()
            self.assertEqual(row.input_tokens, 10)
            self.assertIsNone(row.cost)

    def test_capabilities_never_assume_vision(self):
        from app.capabilities import validate_model

        self.assertFalse(validate_model("qwen/qwen3.6-35b-a3b")["image"])
        with self.assertRaises(ValueError):
            validate_model("qwen/qwen3-vl-30b-a3b-instruct")

    def test_production_ready_rejects_synthetic_data(self):
        from app.main import app
        from fastapi.testclient import TestClient
        from types import SimpleNamespace

        cfg = SimpleNamespace(env="prod", redis_url="", qdrant_url="")
        with (
            patch("app.settings.settings", return_value=cfg),
            patch("app.storage.db.engine"),
            patch(
                "app.main.DATA",
                SimpleNamespace(warnings=["DEMO_FALLBACK: missing files"]),
            ),
        ):
            result = TestClient(app).get("/health/ready")
            self.assertEqual(result.status_code, 503)
            self.assertFalse(result.json()["checks"]["csv"])

    def test_public_redirect_validates_every_destination(self):
        from app.news_ingestion import PublicSourceRedirect
        from urllib.request import Request

        request = Request("https://www.cbr.ru/rss/RssNews")
        handler = PublicSourceRedirect()
        with patch(
            "app.news_ingestion.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("1.1.1.1", 443))],
        ):
            result = handler.redirect_request(
                request, None, 302, "Found", {}, "https://www.cbr.ru/rss/updated"
            )
            self.assertEqual(result.full_url, "https://www.cbr.ru/rss/updated")
            with self.assertRaises(ValueError):
                handler.redirect_request(
                    request, None, 302, "Found", {}, "http://127.0.0.1/private"
                )
        with patch(
            "app.news_ingestion.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("127.0.0.1", 443))],
        ):
            with self.assertRaises(ValueError):
                handler.redirect_request(
                    request, None, 302, "Found", {}, "https://www.cbr.ru/rss/updated"
                )

    def test_worker_heartbeat_restores_discovery_registration(self):
        from app.worker import ResilientWorker

        worker = ResilientWorker.__new__(ResilientWorker)
        with (
            patch("rq.Worker.heartbeat") as heartbeat,
            patch("app.worker.worker_registration.register") as register,
        ):
            worker.heartbeat(timeout=20)
            heartbeat.assert_called_once_with(timeout=20, pipeline=None)
            register.assert_called_once_with(worker, pipeline=None)

    def test_article_edit_invalidates_only_old_content_version(self):
        self.seed()
        self.assertEqual(len(repo.feed("A", "CFO", "v1")), 1)
        repo.put_news(
            [{"news_id": "N", "title": "News", "body": "Updated factual content"}]
        )
        self.assertEqual(repo.feed("A", "CFO", "v1"), [])
        repo.save_insight(
            "A",
            "CFO",
            {
                "card_id": "C2",
                "news_id": "N",
                "audit": {"is_valid": True, "hallucination_detected": False},
            },
            "v1",
        )
        self.assertEqual([e["card_id"] for e in repo.feed("A", "CFO", "v1")], ["C2"])
        self.assertIsNotNone(repo.insight("C"))  # Historical record is retained.
