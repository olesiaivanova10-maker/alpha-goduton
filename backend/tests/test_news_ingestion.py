import unittest
from datetime import datetime, timezone
from app.news_ingestion import parse_rss, deduplicate_news, sort_news

XML='''<rss><channel><item><guid>x1</guid><title> Ставка &amp; кредит </title><description><![CDATA[ЦБ изменил ставку]]></description><pubDate>Thu, 24 Oct 2026 10:00:00 GMT</pubDate><link>https://example/a</link></item><item><title>Пустая</title><link></link></item></channel></rss>'''.encode()
class NewsIngestionTests(unittest.TestCase):
    def test_parse_and_clean_rss(self):
        rows=parse_rss(XML,'Банк России',datetime(2026,10,24,tzinfo=timezone.utc)); self.assertEqual(len(rows),1); self.assertEqual(rows[0].title,'Ставка & кредит'); self.assertEqual(rows[0].news_id,'x1')
    def test_dedup(self):
        rows=parse_rss(XML,'Банк России'); other=rows[0].model_copy(update={'source_name':'ТАСС','source_reliability':.9}); self.assertEqual(len(deduplicate_news(rows+[other])),1)
    def test_sort_without_profile(self):
        rows=parse_rss(XML,'Банк России'); result=sort_news(rows); self.assertTrue(result[0]['relevance']['score'] >= 0); self.assertIn('relevance',result[0])
if __name__=='__main__': unittest.main()
