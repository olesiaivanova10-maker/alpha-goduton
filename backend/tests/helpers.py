"""In-memory company fixtures; ordinary tests do not require private CSV files."""

from contextlib import contextmanager
from unittest.mock import patch
import pandas as pd
from app.data_loader import _synthetic_bundle


@contextmanager
def company_fixture():
    row = _synthetic_bundle("test").companies.iloc[0].to_dict()
    rows = [
        {**row, "SYNTHETIC_U": company, "REVENUE_COMPANY": (i + 1) * 1_000_000_000}
        for i, company in enumerate(["U_14366", "U_26030", "U_428697"])
    ]
    with patch("app.company_context.companies", pd.DataFrame(rows)):
        yield
