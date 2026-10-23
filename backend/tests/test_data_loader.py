import pandas as pd
import unittest

from app.data_loader import load_data

def _write_csv(path, columns, rows):
    pd.DataFrame(rows, columns=columns).to_csv(path, sep=";", index=False)

class DataLoaderTests(unittest.TestCase):
  def test_load_real_dataset(self):
    from pathlib import Path
    data = load_data(Path(__file__).parents[1] / "data")
    self.assertGreater(len(data.companies), 0)
    self.assertGreater(len(data.persons), 0)
    self.assertGreater(len(data.payments), 0)
    self.assertEqual(data.companies["SYNTHETIC_U"].duplicated().sum(), 11)
    self.assertTrue(data.warnings)
    assert pd.api.types.is_numeric_dtype(data.payments["PAY_AMT"])

  def test_loader_rejects_missing_columns(self):
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
      from pathlib import Path
      tmp_path = Path(directory)
      _write_csv(tmp_path / "df_Uid_data_hack.csv", ["SYNTHETIC_U"], [["U1"]])
      _write_csv(tmp_path / "df_Fid_Uid_link_hack.csv", ["SYNTHETIC_F"], [["F1"]])
      _write_csv(tmp_path / "df_Uid_payment_hack.csv", ["PAYER"], [["U1"]])
      with self.assertRaisesRegex(ValueError, "отсутствуют обязательные колонки"):
        load_data(tmp_path)

  def test_loader_reports_duplicate_company_ids(self):
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as directory:
      tmp_path = Path(directory)
      columns = ["SYNTHETIC_U", "MAINOKVED_CODE", "MAINOKVED_NAME", "GROUP_ID", "REVENUE_COMPANY", "CITY", "REGION"]
      rows = [["U1", "1", "x", "G1", 1, "x", "x"], ["U1", "1", "x", "G1", 1, "x", "x"]]
      _write_csv(tmp_path / "df_Uid_data_hack.csv", columns, rows)
      _write_csv(tmp_path / "df_Fid_Uid_link_hack.csv", ["SYNTHETIC_F", "SYNTHETIC_U", "CITY_NAME", "RC_NAME"], [["F1", "U1", "x", "x"]])
      _write_csv(tmp_path / "df_Uid_payment_hack.csv", ["BENEFICIARY", "PAYER", "PAY_AMT", "PAY_CNT"], [["U1", "U1", 1, 1]])
      data = load_data(tmp_path)
      self.assertTrue(data.warnings)
      self.assertIn("повторных SYNTHETIC_U", data.warnings[0])

if __name__ == "__main__":
  unittest.main()
