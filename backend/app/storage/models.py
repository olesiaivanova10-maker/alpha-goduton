from datetime import datetime, timezone
from sqlalchemy import (
    String,
    Text,
    JSON,
    DateTime,
    Integer,
    Float,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def utc():
    return datetime.now(timezone.utc)


class News(Base):
    __tablename__ = "news"
    id: Mapped[str] = mapped_column(String(512), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON)
    possible_duplicate_group: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc)


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    url: Mapped[str] = mapped_column(Text)
    health: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc)


class Insight(Base):
    __tablename__ = "stored_insights"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    news_id: Mapped[str] = mapped_column(ForeignKey("news.id"), index=True)
    company_id: Mapped[str] = mapped_column(String(128), index=True)
    role: Mapped[str] = mapped_column(String(32))
    version: Mapped[str] = mapped_column(String(64), index=True)
    content_version: Mapped[str] = mapped_column(String(64), default="legacy")
    status: Mapped[str] = mapped_column(String(32))
    event: Mapped[dict] = mapped_column(JSON)
    audit: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc)
    __table_args__ = (
        UniqueConstraint(
            "news_id",
            "company_id",
            "role",
            "version",
            "content_version",
            name="uq_insight_result",
        ),
        Index("ix_feed", "company_id", "role", "status"),
    )


class Citation(Base):
    __tablename__ = "citations"
    id: Mapped[int] = mapped_column(primary_key=True)
    insight_id: Mapped[str] = mapped_column(
        ForeignKey("stored_insights.id", ondelete="CASCADE"), index=True
    )
    payload: Mapped[dict] = mapped_column(JSON)


class Feedback(Base):
    __tablename__ = "stored_feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    insight_id: Mapped[str] = mapped_column(
        ForeignKey("stored_insights.id"), index=True
    )
    company_id: Mapped[str] = mapped_column(String(128), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc)
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),)


class Job(Base):
    __tablename__ = "stored_jobs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(64))
    company_id: Mapped[str | None] = mapped_column(String(128), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), index=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc)


class Processing(Base):
    __tablename__ = "processing"
    news_id: Mapped[str] = mapped_column(ForeignKey("news.id"), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    stage: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("stored_jobs.id"))
    card_id: Mapped[str | None] = mapped_column(String(160))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc)


class ProcessingEvent(Base):
    __tablename__ = "processing_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    news_id: Mapped[str] = mapped_column(ForeignKey("news.id"), index=True)
    company_id: Mapped[str] = mapped_column(String(128), index=True)
    role: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc)


class Classification(Base):
    __tablename__ = "classifications"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    news_id: Mapped[str] = mapped_column(ForeignKey("news.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class Probe(Base):
    __tablename__ = "model_probes"
    model_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc)


class ModelCall(Base):
    __tablename__ = "model_calls"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    company_id: Mapped[str | None] = mapped_column(String(128), index=True)
    job_id: Mapped[str | None] = mapped_column(String(64), index=True)
    model_id: Mapped[str] = mapped_column(String(160))
    task: Mapped[str] = mapped_column(String(96))
    prompt_version: Mapped[str] = mapped_column(String(64))
    latency_ms: Mapped[int] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(String(96))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc, index=True
    )


class Corpus(Base):
    __tablename__ = "corpora"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    active: Mapped[bool] = mapped_column(default=False, index=True)
    manifest: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc)
