from typing import Any
from pydantic import BaseModel


class CompanyContext(BaseModel):
    company_id: str
    group_id: str | None = None
    industry: dict[str, Any]
    organization: dict[str, Any]
    location: dict[str, Any]
    scale: dict[str, Any]
    bank_products: dict[str, Any]
    foreign_trade: dict[str, Any]
    group_companies: list[str]
    related_persons: list[dict[str, Any]]
    counterparties: list[dict[str, Any]]
    warnings: list[str] = []


class FeedCard(BaseModel):
    card_id: str
    title: str
    summary: str
    why_it_matters: str
    importance: str
    risks: list[str] = []
    opportunities: list[str] = []
    recommended_action: str
    origin: str
    sources: list[str | dict[str, Any]] = []
    company_id: str


class NewsFeedResponse(BaseModel):
    company_id: str
    company_name: str
    target_role: str
    total_events: int
    critical_events_count: int
    events: list[dict[str, Any]]


class ChatRequest(BaseModel):
    card_id: str
    question: str


class ChatResponse(BaseModel):
    answer: str
    origin: str
    sources: list[str | dict[str, Any]] = []
