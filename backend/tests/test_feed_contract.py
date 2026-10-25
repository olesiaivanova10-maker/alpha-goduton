import unittest
from unittest.mock import patch
from app.feed import build_feed, find_card

class FeedContractTests(unittest.TestCase):
    def test_empty_feed_has_no_static_news(self):
        with patch('app.live_feed.events',return_value=[]):
            response=build_feed('U_26030','CFO')
        self.assertEqual(response['events'],[])
        self.assertEqual(response['total_events'],0)

    def test_stored_event_is_used(self):
        event={'card_id':'test','relevance':{'is_critical':True}}
        with patch('app.live_feed.events',return_value=[event]):
            response=build_feed('U_26030','CFO')
        self.assertEqual(response['events'],[event])
        self.assertEqual(response['critical_events_count'],1)

    def test_unknown_card_has_no_catalog_fallback(self):
        with patch('app.live_feed.card',return_value=None):
            self.assertIsNone(find_card('card-U_26030-rep-cb-rate-11sep'))
