"""
Адаптер контекста компании (agent/adapter.py).
Преобразует сырой словарь `company_context` из бэкенда в типизированную модель `CompanyProfile`.
"""

from typing import Dict, Any
from .schemas import CompanyProfile


def adapt_backend_context_to_profile(ctx: Dict[str, Any]) -> CompanyProfile:
    """Преобразует ответ GET /companies/{id}/context в CompanyProfile."""
    industry = ctx.get("industry") or {}
    scale = ctx.get("scale") or {}
    location = ctx.get("location") or {}
    org = ctx.get("organization") or {}
    bank_prods = ctx.get("bank_products") or {}
    trade = ctx.get("foreign_trade") or {}

    raw_revenue = scale.get("revenue")
    revenue = 0.0
    if raw_revenue is not None:
        try:
            revenue = float(raw_revenue)
        except (ValueError, TypeError):
            revenue = 0.0

    return CompanyProfile(
        synthetic_u=str(ctx.get("company_id", "UNKNOWN")),
        display_name=f"{org.get('type') or 'Компания'} {ctx.get('company_id')}",
        mainokved_code=str(industry.get("okved_code") or "00.00"),
        mainokved_name=str(industry.get("name") or "Не указана"),
        revenue_company=revenue,
        org_type=org.get("type"),
        group_id=ctx.get("group_id"),
        city=location.get("city"),
        region=location.get("region"),
        cl_product_rko=bool(bank_prods.get("rko")),
        cl_product_gar=bool(bank_prods.get("guarantees")),
        cl_product_loa=bool(bank_prods.get("credit")),
        cl_product_lea=bool(bank_prods.get("leasing")),
        cl_product_dep=bool(bank_prods.get("deposits")),
        cl_product_zpp=bool(bank_prods.get("salary_project")),
        factoring_mark=bool(bank_prods.get("factoring")),
        fts_flag=bool(trade.get("has_fts_data")),
        fts_country_name=trade.get("country")
    )
