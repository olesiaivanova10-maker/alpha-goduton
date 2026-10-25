import unittest

from app.feed import build_feed, find_card


class FeedContractTests(unittest.TestCase):
    def test_feed_contains_cards_for_real_company(self):
        response = build_feed("U_26030", "CFO")
        self.assertEqual(response["company_id"], "U_26030")
        self.assertEqual(response["target_role"], "CFO")
        self.assertTrue(response["events"])
        self.assertIn("card_id", response["events"][0])
        self.assertIn("q6_basis_of_conclusion", response["events"][0]["six_questions"])

    def test_card_can_be_resolved_for_chat(self):
        response = build_feed("U_26030", "CFO")
        self.assertIsNotNone(find_card(response["events"][0]["card_id"]))

    def test_company_feeds_differ(self):
        first = build_feed("U_14366", "CFO")
        second = build_feed("U_26030", "CFO")
        self.assertNotEqual([e["card_id"] for e in first["events"]], [e["card_id"] for e in second["events"]])
        self.assertNotEqual([e["title"] for e in first["events"]], [e["title"] for e in second["events"]])
        self.assertTrue(all(e["relevance"]["affected_areas"] for e in first["events"] + second["events"]))


if __name__ == "__main__":
    unittest.main()
