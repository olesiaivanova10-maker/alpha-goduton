"""Explicit local Compose test: actual PostgreSQL/Redis/Qdrant; fixture model, no external API."""

import os, tempfile, uuid
from pathlib import Path
from unittest.mock import patch
from rq import Queue, SimpleWorker
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from backend.app import main, jobs, news_ingestion
from backend.app.storage.db import transaction, engine
from backend.app.storage import repositories as repo
from backend.app.storage.models import Job
from agent.schemas import (
    NewsClassification,
    RelevanceAssessment,
    AlfaBankPosition,
    PersonalizedInsight,
    NextBestAction,
    ValidationReport,
)
from agent.rag import retriever


def fixture_pdf(path):
    w = PdfWriter()
    for text in [
        "Unrelated weather report",
        "Central bank policy rate held at 14 percent. Credit costs depend on loan contract.",
    ]:
        page = w.add_blank_page(width=600, height=800)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): w._add_object(font)}
                )
            }
        )
        stream = DecodedStreamObject()
        stream.set_data(("BT /F1 12 Tf 30 700 Td (" + text + ") Tj ET").encode())
        page[NameObject("/Contents")] = w._add_object(stream)
    with path.open("wb") as f:
        w.write(f)


class FixtureAgent:
    def step_1_classify(self, n):
        return NewsClassification(
            is_relevant_business_event=True, category="macro", factual_essence=n.title
        )

    def step_2_rank_relevance(self, *a):
        return RelevanceAssessment(
            relevance_score=0.8,
            is_critical=False,
            relevance_rationale="Credit product present",
            affected_factors=["credit"],
        )

    def step_3_rag_bank_context(self, n, *a):
        chunks = retriever.retrieve_bank_context(n.title, top_k=1)
        assert chunks and chunks[0].page == 2
        c = chunks[0]
        return AlfaBankPosition(
            has_bank_report=True,
            source_report_title=c.filename,
            position_text=c.text,
            is_official_view=False,
            sources=[{"filename": c.filename, "page": c.page, "chunk_id": c.chunk_id}],
        )

    def step_4_deep_insight(self, c, n, b, r):
        return PersonalizedInsight(
            news_id=n.news_id,
            company_id=c.synthetic_u,
            target_role=r,
            fact_summary=n.title,
            why_it_matters="Conditional credit risk",
            alfa_bank_position=b,
            next_best_action=NextBestAction(
                action_type="CONSULTATION",
                title="Check contract",
                description="Check rate terms",
            ),
        )

    def step_5_fact_check_and_audit(self, *a):
        return ValidationReport(
            is_valid=True, hallucination_detected=False, notes="Fixture audit"
        )


def drain():
    SimpleWorker(
        [Queue("alpha", connection=jobs.redis())], connection=jobs.redis()
    ).work(burst=True, logging_level="WARNING")


def run():
    headers = {"X-Admin-Key": os.environ["ADMIN_API_KEY"]}
    client = TestClient(main.app, headers=headers)
    suffix = uuid.uuid4().hex[:12]
    xml = (
        "<rss><channel><item><guid>e2e-"
        + suffix
        + "</guid><title>Кредит Credit policy rate held "
        + suffix
        + "</title><link>https://example.com/"
        + suffix
        + "</link><description>Credit rate held at 14 percent</description></item></channel></rss>"
    ).encode()
    records = news_ingestion.parse_rss(xml, "Fixture")
    with (
        tempfile.TemporaryDirectory() as tmp,
        patch.dict(os.environ, {"PDF_DIR": tmp, "RAG_MODE": "lexical"}),
    ):
        fixture_pdf(Path(tmp) / "bank.pdf")
        retriever.index_pdf_directory(tmp)
        with patch(
            "backend.app.news_ingestion.collect_sources",
            return_value=(
                records,
                {"loaded": ["Fixture"], "counts": {"Fixture": 1}, "failed": []},
            ),
        ):
            result = client.post("/api/news/refresh")
            assert result.status_code == 202, result.text
            drain()
        assert any(n["news_id"] == records[0].news_id for n in repo.all_news())
        # The queue is real. Only provider inference is a fixture, so no key or budget is used.
        with (
            patch.object(main.orchestrator, "has_live_api", True),
            patch("agent.orchestrator.AgentOrchestrator", return_value=FixtureAgent()),
        ):
            result = client.post(
                "/api/feed/refresh?company_id=U_26030&role=CFO&limit=1"
            )
            assert result.status_code == 202, result.text
            job_id = result.json()["job_id"]
            drain()
        job = repo.get_job(job_id)
        assert job["status"] == "completed", job
        result = client.get("/api/feed?company_id=U_26030&role=CFO")
        assert result.status_code == 200, result.text
        event = next(
            e for e in result.json()["events"] if e["news_id"] == records[0].news_id
        )
        assert (
            event["six_questions"]["q6_basis_of_conclusion"]["sources"][1]["page"] == 2
        )
        # Simulate redelivery: completed SQL job is not executed twice.
        with patch(
            "backend.app.live_feed.generate",
            side_effect=AssertionError("duplicate execution"),
        ):
            jobs.execute(job_id)
        with (
            patch.object(main.orchestrator, "has_live_api", True),
            patch.object(
                main.orchestrator,
                "_call_llm",
                return_value="The contract type is not known.",
            ),
        ):
            chat = client.post(
                "/chat",
                json={"card_id": event["card_id"], "question": "Credit rate contract?"},
            )
            assert chat.status_code == 200 and chat.json()["fallback"] is False, (
                chat.text
            )
            assert chat.json()["sources"][0]["page"] == 2
            legacy = client.post(
                "/api/chat",
                json={
                    "company_id": "U_26030",
                    "news_title": event["title"],
                    "insight_summary": "Untrusted client summary",
                    "user_message": "Credit rate contract?",
                    "user_role": "CFO",
                },
            )
            assert (
                legacy.status_code == 200
                and legacy.json()["reply"] == "The contract type is not known."
            ), legacy.text
        feedback = client.post(
            "/feedback",
            json={"insight_id": event["card_id"], "company_id": "U_26030", "rating": 5},
        )
        assert feedback.status_code == 200, feedback.text
        engine().dispose()
        assert repo.insight(event["card_id"])
        print(
            "PASS RSS -> PostgreSQL -> Redis/RQ worker -> profile/relevance -> real PDF page 2 -> fixture synthesis -> audit -> feed -> chat -> feedback; redelivery and reconnect"
        )
        # Actual Qdrant operations, with deterministic vectors to test storage/filtering independently of model weights.
        from qdrant_client import QdrantClient, models

        q = QdrantClient(url=os.environ["QDRANT_URL"])
        name = "integration_" + suffix
        try:
            q.create_collection(
                name,
                vectors_config=models.VectorParams(
                    size=3, distance=models.Distance.COSINE
                ),
            )
            q.upsert(
                name,
                [
                    models.PointStruct(
                        id=1,
                        vector=[1.0, 0.0, 0.0],
                        payload={"filename": "allowed.pdf", "page": 2},
                    ),
                    models.PointStruct(
                        id=2,
                        vector=[1.0, 0.0, 0.0],
                        payload={"filename": "forbidden.pdf", "page": 7},
                    ),
                ],
                wait=True,
            )
            hits = q.query_points(
                name,
                query=[1.0, 0.0, 0.0],
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="filename", match=models.MatchValue(value="allowed.pdf")
                        )
                    ]
                ),
            ).points
            assert len(hits) == 1 and hits[0].payload["page"] == 2
        finally:
            q.delete_collection(name)
        print(
            "PASS actual Qdrant storage, vector query and metadata isolation (fixture embeddings)"
        )


def queue_guards():
    from backend.app.model_gateway import permit
    from datetime import timedelta
    from backend.app.storage.models import utc

    r = jobs.redis()
    model = "fixture-" + uuid.uuid4().hex
    with patch.dict(os.environ, {"MODEL_CONCURRENCY": "1"}):
        with permit(model, 1):
            try:
                with permit(model, 1):
                    raise AssertionError("concurrency limit bypassed")
            except RuntimeError:
                pass
    # Owner-token lease cannot be released by a different worker.
    first = r.lock("test-owner", timeout=10)
    second = r.lock("test-owner", timeout=10)
    assert first.acquire(blocking=False) and not second.acquire(blocking=False)
    assert first.owned() and not second.owned()
    first.release()
    # Durable expired SQL work becomes queued again without needing the old API process.
    job_id = uuid.uuid4().hex
    repo.put_job(job_id, "running", {}, "probes")
    with transaction() as db:
        row = db.get(Job, job_id)
        row.lease_until = utc() - timedelta(seconds=1)
        row.attempts = 3
    jobs.recover()
    assert repo.get_job(job_id)["status"] == "failed"
    print("PASS Redis concurrency, owner-token locks and exhausted-lease recovery")


if __name__ == "__main__":
    run()
    queue_guards()
