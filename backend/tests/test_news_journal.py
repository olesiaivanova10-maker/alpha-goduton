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
   self.assertEqual(j.listing('B','CFO')['items'][0]['status'],'error')
   self.assertEqual(j.listing('A','CFO')['items'][0]['status'],'rejected')
   self.assertEqual(j.listing('A','CFO',search='нет')['total'],0)
