import os,tempfile,unittest
from unittest.mock import patch
from app import news_journal as j
class JournalTests(unittest.TestCase):
 def test_company_isolation_history_and_restart(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'INSIGHT_DB_PATH':tmp+'/test.db'}):
   r={'news_id':'n','title':'Новость','source_url':'https://example.com'}
   j.register([r]);j.register([r])
   self.assertEqual(j.listing('A','CFO')['summary'],{'loaded':1})
   j.transition('n','A','CFO','sent','relevance','Проверка','job')
   j.transition('n','A','CFO','rejected','relevance','Ниже порога','job')
   self.assertEqual(j.listing('A','CFO',status='rejected')['total'],1)
   self.assertEqual(j.listing('B','CFO')['items'][0]['status'],'loaded')
   self.assertEqual(len(j.history('n','A','CFO')),2)
   j.transition('n','B','CFO','sent','audit','Аудит','job2')
   j.bootstrap([r])
   self.assertEqual(j.listing('B','CFO')['items'][0]['status'],'sent') # API startup cannot interrupt a separate worker
   self.assertEqual(j.listing('A','CFO')['items'][0]['status'],'rejected')
   self.assertEqual(j.listing('A','CFO',search='нет')['total'],0)
 def test_history_api_with_url_identifier(self):
  from fastapi.testclient import TestClient
  from app.main import app
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'INSIGHT_DB_PATH':tmp+'/api.db'}):
   news_id='https://example.com/news/123?x=1'
   j.register([{'news_id':news_id,'title':'Тест'}])
   j.transition(news_id,'A','CFO','rejected','audit','Причина')
   client=TestClient(app)
   r=client.get('/api/developer/news-history',params={'news_id':news_id,'company_id':'A'})
   self.assertEqual(r.status_code,200)
   self.assertEqual(r.json()['items'][0]['reason'],'Причина')
   self.assertEqual(client.get('/api/developer/news',params={'status':'bad'}).status_code,422)
   self.assertEqual(client.get('/api/developer').status_code,200)
