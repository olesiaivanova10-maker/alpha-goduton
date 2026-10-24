import unittest

from app.feedback import add_feedback, feedback_metrics


class FeedbackTests(unittest.TestCase):
    def test_feedback_updates_metrics(self):
        before = feedback_metrics()["count"]
        add_feedback("I-test", "U-test", 5, "Полезно")
        after = feedback_metrics()
        self.assertEqual(after["count"], before + 1)
        self.assertGreaterEqual(after["average_rating"], 1)

    def test_rating_is_validated(self):
        with self.assertRaises(ValueError):
            add_feedback("I-test", "U-test", 6)


if __name__ == "__main__":
    unittest.main()
