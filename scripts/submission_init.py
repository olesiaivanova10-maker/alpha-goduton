"""Reproducible fictional companies. Never inserts generated cards or bank opinions."""
import os, json, csv, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def initialize():
    from backend.app.data_loader import _synthetic_bundle
    data = Path(os.environ["DATA_DIR"]); data.mkdir(parents=True, exist_ok=True)
    base = _synthetic_bundle("fixture").companies.iloc[0].to_dict()
    companies = [
        {**base, "SYNTHETIC_U":"U_14366", "MAINOKVED_CODE":"64.91", "MAINOKVED_NAME":"Финансовая аренда (лизинг)", "FTS_FLAG":0, "FTS_COUNTRY_NAME":"", "REVENUE_COMPANY":18000000000, "CL_PRODUCT_DEP_MARK":1, "GROUP_ID":"G_FIXTURE_1"},
        {**base, "SYNTHETIC_U":"U_26030", "CITY":"Уфа", "REGION":"Республика Башкортостан", "CL_PRODUCT_LEA_MARK":0, "REVENUE_COMPANY":32000000000, "GROUP_ID":"G_FIXTURE_2"},
    ]
    tables = {
        "df_Uid_data_hack.csv": companies,
        "df_Fid_Uid_link_hack.csv": [{"SYNTHETIC_F":"F_FIXTURE", "SYNTHETIC_U":c["SYNTHETIC_U"], "CITY_NAME":"", "RC_NAME":""} for c in companies],
        "df_Uid_payment_hack.csv": [{"PAYER":"U_14366", "BENEFICIARY":"U_26030", "PAY_AMT":7000000, "PAY_CNT":12}, {"PAYER":"U_26030", "BENEFICIARY":"U_14366", "PAY_AMT":2000000, "PAY_CNT":3}],
    }
    for name, rows in tables.items():
        target=data/name
        with target.open("w", encoding="utf-8-sig", newline="") as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=";");writer.writeheader();writer.writerows(rows)
    print("Prepared two fictional companies and payment/person links. No cards or bank material seeded.")

if __name__ == "__main__": initialize()
