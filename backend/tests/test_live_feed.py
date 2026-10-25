import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from agent.schemas import (NewsClassification, RelevanceAssessment, AlfaBankPosition,
                          PersonalizedInsight, NextBestAction, UserRole, ValidationReport)
from app import live_feed

class FakeAgent:
    valid=True
    def step_1_classify(self,news):
        return NewsClassification(is_relevant_business_event=True,category='macro',factual_essence='Факт')
    def step_2_rank_relevance(self,*args):
        return RelevanceAssessment(relevance_score=.8,is_critical=True,relevance_rationale='Есть кредит',affected_factors=['кредитование'])
    def step_3_rag_bank_context(self,*args):
        return AlfaBankPosition(has_bank_report=False,source_report_title=None,position_text='Источник не найден',is_official_view=False)
    def step_4_deep_insight(self,company,news,bank,role):
        return PersonalizedInsight(news_id=news.news_id,company_id=company.synthetic_u,target_role=role,fact_summary='Факт',why_it_matters='Есть кредитный продукт',alfa_bank_position=bank,next_best_action=NextBestAction(action_type='CONSULTATION',title='Проверить',description='Уточнить условия'))
    def step_5_fact_check_and_audit(self,*args):
        return ValidationReport(is_valid=self.valid,hallucination_detected=not self.valid,notes='Тест')

class LiveFeedTests(unittest.TestCase):
    def test_persistence_and_rejected_audit(self):
        from app.agent_service import AgentService
        record={'news_id':'N1','title':'Ставка','body':'Тест','source_name':'Тест','source_url':'https://example.com','published_at':'2026-10-25T00:00:00Z'}
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'INSIGHT_DB_PATH':tmp+'/insights.db'}):
            agent=FakeAgent();service=AgentService(agent)
            live_feed.generate('j1','U_26030','CFO',[record],service)
            first=live_feed.events('U_26030','CFO')
            self.assertEqual(len(first),1)
            self.assertEqual(live_feed.card(first[0]['card_id'])['news_id'],'N1')
            live_feed.generate('j2','U_26030','CFO',[record],service)
            self.assertEqual(len(live_feed.events('U_26030','CFO')),1)
            agent.valid=False
            live_feed.generate('j3','U_14366','CFO',[record],service)
            self.assertEqual(live_feed.events('U_14366','CFO'),[])
            self.assertEqual(live_feed.job('j3')['status'],'failed')
