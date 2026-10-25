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
