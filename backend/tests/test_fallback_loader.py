import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.data_loader import load_data

class FallbackLoaderTests(unittest.TestCase):
    def test_missing_files_use_demo_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"ALLOW_SYNTHETIC_FALLBACK": "1"}):
                bundle = load_data(Path(directory))
        self.assertEqual(bundle.companies.iloc[0]["SYNTHETIC_U"], "U_DEMO_001")
        self.assertTrue(bundle.warnings[0].startswith("DEMO_FALLBACK"))

if __name__ == "__main__":
    unittest.main()
