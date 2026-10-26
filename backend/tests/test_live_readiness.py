import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import news_store, model_health
from app.news_ingestion import parse_rss

class LiveReadinessTests(unittest.TestCase):
    def test_news_survives_reload(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(news_store,'PATH',Path(temp)/'cache.json'):
            rows=parse_rss(b'<rss><channel><item><title>Rate</title><link>https://example.com</link><description>News</description></item></channel></rss>','Test')
            news_store.save_news(rows,{'loaded':['Test']})
            restored,status=news_store.load_news()
            self.assertEqual(restored[0].news_id,rows[0].news_id)
            self.assertEqual(status['loaded'],['Test'])

    def test_bad_url_never_calls_model(self):
        with patch.object(model_health.config,'base_url','invalid'),patch.object(model_health.config,'api_key','test'):
            result=model_health.check_models(force=True)
        self.assertTrue(all(i['status']=='not_configured' for i in result['items']))
        self.assertTrue(all('HTTP' in i['error'] for i in result['items']))
