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
