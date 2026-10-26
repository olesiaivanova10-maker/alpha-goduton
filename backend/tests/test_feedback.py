import unittest,tempfile,os
from unittest.mock import patch
from app.feedback import add_feedback,feedback_metrics
from app.storage import repositories as repo
class FeedbackTests(unittest.TestCase):
 def test_feedback_integrity_and_persistence(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'INSIGHT_DB_PATH':tmp+'/test.db'}):
   repo.put_news([{'news_id':'n','title':'Test'}])
   repo.save_insight('A','CFO',{'card_id':'c','news_id':'n','audit':{'is_valid':True,'hallucination_detected':False}},'v')
   add_feedback('c','A',5,'Полезно')
   self.assertEqual(feedback_metrics()['count'],1)
   with self.assertRaises(ValueError):add_feedback('c','B',5)
   with self.assertRaises(ValueError):add_feedback('missing','A',5)
   self.assertEqual(feedback_metrics(['B'])['count'],0)
 def test_rating_is_validated(self):
  with self.assertRaises(ValueError):add_feedback('I-test','U-test',6)
