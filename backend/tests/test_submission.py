import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from agent.adapter import adapt_backend_context_to_profile
from agent.schemas import UserRole
from agent.prompts.deepseek_insight import build_deepseek_insight_prompt
from agent.rag import retriever


class SubmissionTests(unittest.TestCase):
    def test_fixtures_are_distinct_and_loadable(self):
        from scripts.submission_init import initialize
        from app.data_loader import load_data
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'DATA_DIR':d, 'PAYMENTS_FILE':'df_Uid_payment_hack.csv'}):
            initialize()
            bundle = load_data(d)
            self.assertEqual(len(bundle.companies), 2)
            self.assertEqual(bundle.companies.MAINOKVED_CODE.nunique(), 2)
            self.assertEqual(len(bundle.payments), 2)
            self.assertEqual(bundle.persons.SYNTHETIC_F.nunique(), 1)

    def test_generation_prompt_carries_graph_and_unknowns(self):
        p = adapt_backend_context_to_profile({'company_id':'U_X', 'scale':{'revenue':float('nan')}, 'location':{'city':'Уфа'}, 'counterparties':[{'company_id':'U_Y','direction':'incoming','payment_amount':17}], 'warnings':['Нет ставки кредита']})
        self.assertEqual(p.revenue_company, 0)
        prompt = build_deepseek_insight_prompt(p.model_dump(), {'title':'Новое событие','body':'Изменение рынка'}, {}, UserRole.CFO)
        self.assertIn('Уфа', prompt['user'])
        self.assertIn('incoming_total', prompt['user'])
        self.assertIn('Нет ставки кредита', prompt['user'])
        self.assertNotIn('Базовое РКО', prompt['user'])

    def test_russian_forms_and_private_data_abstention(self):
        chunks=[retriever.RagChunk('one','research.pdf',1,'Ключевая ставка сохраняется. Кредитование компаний остаётся дорогим.'), retriever.RagChunk('two','other.pdf',1,'Урожай пшеницы и цены на зерно растут.')]
        with patch.object(retriever,'_INDEX',chunks), patch.object(retriever,'_INDEXED',True), patch.dict(os.environ,{'RAG_MODE':'lexical'}):
            result=retriever.retrieve_bank_context('Сохранение ключевой ставки и стоимость кредитования')
            self.assertEqual(result[0].filename,'research.pdf')
            self.assertEqual(retriever.retrieve_bank_context('Какой остаток долга и график платежей U_26030?'),[])
            self.assertEqual(retriever.retrieve_bank_context('Технические характеристики космической ракеты'),[])

    def test_pdf_links_follow_configured_corpus_directory(self):
        from fastapi.testclient import TestClient
        from app.main import app
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'APP_ENV':'test','REQUIRE_AUTH':'false','PDF_DIR':d}):
            Path(d, 'bank.pdf').write_bytes(b'%PDF-1.4\n')
            response=TestClient(app).get('/api/reports/files/bank.pdf')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.content,b'%PDF-1.4\n')
            self.assertEqual(TestClient(app).get('/api/reports/files/missing.pdf').status_code,404)

    def test_empty_archive_refreshes_rss_in_worker(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from helpers import company_fixture
        with company_fixture(), patch('app.main.load_news',return_value=([],{})), patch('app.main.orchestrator.has_live_api',True), patch('app.main._enqueue',return_value={'job_id':'test','status':'queued'}) as enqueue:
            response=TestClient(app).post('/api/feed/refresh?company_id=U_14366')
            self.assertEqual(response.status_code,202)
            self.assertTrue(enqueue.call_args.args[1]['refresh_sources'])

    def test_saved_card_link_survives_new_feed_version_and_is_scoped(self):
        from app.storage import repositories as repo
        from app.main import app
        from fastapi.testclient import TestClient
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'APP_ENV':'test','REDIS_URL':'','INSIGHT_DB_PATH':d+'/db.sqlite','REQUIRE_AUTH':'true','ADMIN_API_KEY':'fixture-admin','GATEWAY_SIGNING_SECRET':''}):
            repo.put_news([{'news_id':'N','title':'Факт','body':'Текст'}])
            repo.save_insight('U_14366','CFO',{'card_id':'C','news_id':'N','title':'Факт','audit':{'is_valid':True,'hallucination_detected':False}},'historical-version')
            client=TestClient(app)
            self.assertEqual(client.get('/api/cards/C').status_code,401)
            with patch('app.security.identity',return_value={'user':'other','companies':['U_26030'],'admin':False}):
                self.assertEqual(client.get('/api/cards/C').status_code,404)
            response=client.get('/api/cards/C',headers={'X-Admin-Key':'fixture-admin'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['card_id'],'C')
            self.assertEqual(repo.feed('U_14366','CFO','new-version'),[])

    def test_short_qwen_mode_is_actually_sent_to_provider(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from agent.models_cfg import TASK_MODEL_MAPPING, PipelineTask
        from app.model_gateway import call
        fake=MagicMock()
        fake.chat.completions.create.return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{}'))],usage=None)
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'APP_ENV':'test','REDIS_URL':'','INSIGHT_DB_PATH':d+'/db.sqlite'}):
            call(fake,PipelineTask.RAG,TASK_MODEL_MAPPING[PipelineTask.RAG],'system','data',10)
        self.assertEqual(fake.chat.completions.create.call_args.kwargs['extra_body'],{'reasoning':{'effort':'none'}})

    def test_rag_timeout_retains_real_evidence_and_marks_degradation(self):
        from agent.orchestrator import AgentOrchestrator
        from agent.schemas import NewsItem, NewsClassification
        agent=AgentOrchestrator();agent.has_live_api=True
        chunk=retriever.RagChunk('c','bank.pdf',3,'Проверяемый исходный фрагмент',.7)
        with patch.object(retriever,'retrieve_bank_context',return_value=[chunk]), patch.object(agent,'_call_llm',side_effect=RuntimeError('timeout')):
            bank=agent.step_3_rag_bank_context(NewsItem(news_id='N',title='Ставка',body='Новость'), NewsClassification(is_relevant_business_event=True,category='macro',factual_essence='Ставка'))
        self.assertEqual(bank.synthesis_status,'extracts_only')
        self.assertIn(chunk.text,bank.evidence_text)
        self.assertFalse(bank.is_official_view)

    def test_rag_retains_exact_excerpt_separate_from_summary(self):
        from agent.orchestrator import AgentOrchestrator
        from agent.schemas import NewsItem, NewsClassification
        agent=AgentOrchestrator();agent.has_live_api=True
        chunk=retriever.RagChunk('c','source.pdf',7,'Исходный текст документа.',.7,'ocr')
        with patch.object(retriever,'retrieve_bank_context',return_value=[chunk]), patch.object(agent,'_call_llm',return_value='{"has_matching_report":true,"bank_official_view":"Сводка ИИ","citation_ids":["c"]}'):
            bank=agent.step_3_rag_bank_context(NewsItem(news_id='N',title='Новость',body='Текст'),NewsClassification(is_relevant_business_event=True,category='macro',factual_essence='Факт'))
        self.assertEqual(bank.sources[0]['excerpt'],chunk.text)
        self.assertEqual(bank.position_text,'Сводка ИИ')
        self.assertFalse(bank.is_official_view)

if __name__=='__main__':unittest.main()
