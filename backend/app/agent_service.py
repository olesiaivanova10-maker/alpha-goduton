"""Stable boundary between HTTP handlers and the AI orchestrator."""

from agent.adapter import adapt_backend_context_to_profile
from agent.orchestrator import AgentOrchestrator
from agent.schemas import NewsItem, UserRole

from .company_context import get_company_context


class AgentService:
    def __init__(self, orchestrator: AgentOrchestrator | None = None):
        self.orchestrator = orchestrator or AgentOrchestrator()

    def analyze(self, company_id: str, news: NewsItem, role: UserRole):
        context = get_company_context(company_id)
        profile = adapt_backend_context_to_profile(context)
        return self.orchestrator.run_pipeline(profile, news, role=role)

    def profile(self, company_id: str):
        return get_company_context(company_id)
