import unittest

from app.feed import build_feed, find_card


class FeedContractTests(unittest.TestCase):
    def test_feed_contains_cards_for_real_company(self):
        response = build_feed("U_26030", "CFO")
        self.assertEqual(response["company_id"], "U_26030")
        self.assertEqual(response["role"], "CFO")
        self.assertTrue(response["items"])
        self.assertIn("card_id", response["items"][0])

    def test_card_can_be_resolved_for_chat(self):
        response = build_feed("U_26030", "CFO")
        self.assertIsNotNone(find_card(response["items"][0]["card_id"]))


if __name__ == "__main__":
    unittest.main()
