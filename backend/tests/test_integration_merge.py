import unittest
from fastapi.testclient import TestClient
from app.main import app
from agent.orchestrator import AgentOrchestrator
from orchestrator import AgentOrchestrator as CompatibilityOrchestrator

class IntegrationMergeTests(unittest.TestCase):
    def setUp(self):
        from helpers import company_fixture
        self.enterContext(company_fixture())

    def test_canonical_agent(self):
        self.assertIs(AgentOrchestrator, CompatibilityOrchestrator)

    def test_frontend_api_contract(self):
        client = TestClient(app)
        self.assertEqual(client.get('/health').status_code, 200)
        for company in ['U_14366', 'U_26030']:
            feed = client.get('/api/feed', params={'company_id': company, 'role': 'CFO'})
            self.assertEqual(feed.status_code, 200)
            self.assertIn('events',feed.json())
        self.assertEqual(client.post('/chat',json={'card_id':'unknown','question':'Почему?'}).status_code,404)
