import unittest

from app.agent_service import AgentService
from agent.schemas import NewsItem, UserRole


class FakeOrchestrator:
    def run_pipeline(self, company, news, role):
        return {"company": company.synthetic_u, "news": news.news_id, "role": role.value}


class AgentServiceTests(unittest.TestCase):
    def test_service_passes_real_company_context_to_agent(self):
        service = AgentService(FakeOrchestrator())
        result = service.analyze(
            "U_428697",
            NewsItem(news_id="N1", title="Ставка", body="Ставка сохранена"),
            UserRole.CFO,
        )
        self.assertEqual(result["company"], "U_428697")
        self.assertEqual(result["news"], "N1")
        self.assertEqual(result["role"], "CFO")


if __name__ == "__main__":
    unittest.main()
