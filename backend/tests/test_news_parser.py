import unittest

from app.news_parser import normalize_news


class NewsParserTests(unittest.TestCase):
    def test_normalizes_whitespace_and_generates_id(self):
        result = normalize_news({"title": "  Ставка 14% ", "body": "  Текст\nновости ", "source_name": "ЦБ"})
        self.assertEqual(result["title"], "Ставка 14%")
        self.assertEqual(result["body"], "Текст новости")
        self.assertTrue(result["news_id"])

    def test_requires_title_and_body(self):
        with self.assertRaises(ValueError):
            normalize_news({"title": "Только заголовок"})


if __name__ == "__main__":
    unittest.main()
