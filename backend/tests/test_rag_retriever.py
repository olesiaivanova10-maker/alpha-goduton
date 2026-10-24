import tempfile
import unittest
from pathlib import Path
from agent.rag.retriever import index_pdf_directory, retrieve_bank_context

class RagRetrieverTests(unittest.TestCase):
    def test_empty_directory_returns_empty_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(index_pdf_directory(Path(directory)), [])
            self.assertEqual(retrieve_bank_context("ключевая ставка", {}, 3), [])

if __name__ == '__main__': unittest.main()
