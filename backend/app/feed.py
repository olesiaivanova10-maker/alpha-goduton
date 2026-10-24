from typing import Any

from agent.bank_knowledge_base import ALFA_REPORTS_INDEX

from .company_context import get_company_context


def build_feed(company_id: str, role: str = "CFO") -> dict[str, Any]:
    """Build a stable feed contract from the company profile and bank reports."""
    context = get_company_context(company_id)
    industry = (context.get("industry") or {}).get("name") or "бизнес"
    cards = []
    for index, report in enumerate(ALFA_REPORTS_INDEX[:5], 1):
        cards.append({
            "card_id": f"{company_id}:{report.chunk_id}",
            "title": report.report_title,
            "summary": report.summary,
            "why_it_matters": f"Материал сопоставлен с профилем компании в отрасли «{industry}». Роль пользователя: {role}.",
            "importance": "medium",
            "risks": [],
            "opportunities": [],
            "recommended_action": "Открыть аналитический материал и обсудить сценарий с менеджером.",
            "origin": "alfa_bank",
            "sources": [report.source_filename],
            "company_id": company_id,
        })
    return {"company_id": company_id, "role": role, "items": cards}


def find_card(card_id: str) -> dict[str, Any] | None:
    for report in ALFA_REPORTS_INDEX:
        if card_id.endswith(f":{report.chunk_id}"):
            return {"title": report.report_title, "summary": report.summary, "source": report.source_filename}
    return None
