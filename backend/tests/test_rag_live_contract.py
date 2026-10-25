import unittest
from unittest.mock import patch
from agent.rag.retriever import RagChunk
from agent.orchestrator import AgentOrchestrator
from agent.schemas import NewsItem, NewsClassification

class RagLiveContractTests(unittest.TestCase):
    def test_qwen_receives_real_chunk_context(self):
        agent=AgentOrchestrator()
        agent.has_live_api=True
        news=NewsItem(news_id='test',title='Ставка',body='Ставка сохранена')
        classification=NewsClassification(is_relevant_business_event=True, category='macro',factual_essence='Ставка')
        chunk=RagChunk('c1','report.pdf',2,'Подтверждённый фрагмент',.8,'ocr')
        with patch('agent.rag.retriever.retrieve_bank_context',return_value=[chunk]),patch.object(agent,'_call_llm',return_value='{"has_matching_report":true,"bank_official_view":"Позиция из фрагмента"}') as model:
            result=agent.step_3_rag_bank_context(news,classification)
        self.assertEqual(result.position_text,'Позиция из фрагмента')
        self.assertEqual(result.sources[0]['page'],2)
        self.assertIn('Подтверждённый фрагмент',model.call_args.args[2])

    def test_no_source_means_no_official_position(self):
        news=NewsItem(news_id='test',title='Ставка',body='Ставка сохранена')
        classification=NewsClassification(is_relevant_business_event=True,category='macro',factual_essence='Ставка')
        with patch('agent.rag.retriever.retrieve_bank_context',return_value=[]):
            result=AgentOrchestrator().step_3_rag_bank_context(news,classification)
        self.assertFalse(result.is_official_view)
        self.assertFalse(result.has_bank_report)

    def test_audit_uses_real_model_fallback_and_fails_closed(self):
        from agent.schemas import CompanyProfile, PersonalizedInsight, AlfaBankPosition, NextBestAction, UserRole
        agent=AgentOrchestrator()
        company=CompanyProfile(synthetic_u='U1',mainokved_code='46',mainokved_name='Торговля',revenue_company=10)
        news=NewsItem(news_id='N1',title='Ставка',body='Ставка сохранена')
        bank=AlfaBankPosition(has_bank_report=False,source_report_title=None,position_text='Нет отчёта',is_official_view=False)
        insight=PersonalizedInsight(news_id='N1',company_id='U1',target_role=UserRole.CFO,fact_summary='Ставка сохранена',why_it_matters='Условный риск',alfa_bank_position=bank,next_best_action=NextBestAction(action_type='CONSULTATION',title='Уточнить',description='Запросить данные'))
        with patch.object(agent,'_call_llm',side_effect=[TimeoutError(),'{"is_valid":true,"hallucination_detected":false,"audit_comment":"Проверено"}']):
            audit=agent.step_5_fact_check_and_audit(company,news,bank,insight)
        self.assertTrue(audit.is_valid)
        self.assertIn('Gemma',audit.notes)
        with patch.object(agent,'_call_llm',side_effect=[TimeoutError(),ValueError()]):
            self.assertFalse(agent.step_5_fact_check_and_audit(company,news,bank,insight).is_valid)
