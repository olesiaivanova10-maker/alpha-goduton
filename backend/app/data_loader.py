from dataclasses import dataclass
import os
from pathlib import Path
import pandas as pd

COMPANY_COLUMNS = {"SYNTHETIC_U", "MAINOKVED_CODE", "MAINOKVED_NAME", "GROUP_ID", "REVENUE_COMPANY", "CITY", "REGION"}
PERSON_COLUMNS = {"SYNTHETIC_F", "SYNTHETIC_U", "CITY_NAME", "RC_NAME"}
PAYMENT_COLUMNS = {"BENEFICIARY", "PAYER", "PAY_AMT", "PAY_CNT"}

@dataclass(frozen=True)
class DataBundle:
    companies: pd.DataFrame
    persons: pd.DataFrame
    payments: pd.DataFrame
    warnings: tuple[str, ...] = ()

def _synthetic_bundle(reason: str) -> DataBundle:
    companies = pd.DataFrame([{"SYNTHETIC_U":"U_DEMO_001","ORG_TYPE":"ООО","OKFS_NAME":"Частная собственность","COMPANY_AGE_YEARS_GRADATION":"8-15","ECO_MARK_LABEL":"Зрелый бизнес","MAINOKVED_CODE":"46.71.2","MAINOKVED_NAME":"Оптовая торговля моторным топливом","NEGATIVEMARK":0,"AMOUNT_WORKERS_FNS_GRADATION":"101-250","AMOUNT_WORKERS_SPARK_GRADATION":"101-250","CL_TYPE":"CLIENT","CL_PRODUCT_RKO_MARK":1,"CL_PRODUCT_GAR_MARK":0,"CL_PRODUCT_LOA_MARK":1,"CL_PRODUCT_LEA_MARK":1,"CL_PRODUCT_DEP_MARK":0,"CL_PRODUCT_ZPP_MARK":1,"FTS_FLAG":1,"FTS_COUNTRY_NAME":"Китай","FACTORING_MARK":0,"REVENUE_COMPANY":20000000000,"GROUP_ID":"G_DEMO","CITY":"Москва","REGION":"Москва"}])
    persons = pd.DataFrame([{"SYNTHETIC_F":"F_DEMO_001","CITY_NAME":"Москва","RC_NAME":"Москва","SYNTHETIC_U":"U_DEMO_001"}])
    payments = pd.DataFrame([{"BENEFICIARY":"U_DEMO_SUPPLIER","PAYER":"U_DEMO_001","PAY_AMT":1000000.0,"PAY_CNT":10}])
    return DataBundle(companies, persons, payments, (f"DEMO_FALLBACK: {reason}",))

def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Файл данных не найден: {path}")
    return pd.read_csv(path, sep=";", encoding="utf-8-sig", low_memory=False)

def _validate_columns(name: str, frame: pd.DataFrame, required: set[str]) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{name}: отсутствуют обязательные колонки: {', '.join(missing)}")

def load_data(data_dir: str | Path | None = None) -> DataBundle:
    directory = Path(data_dir or os.getenv("DATA_DIR", Path(__file__).parents[1] / "data"))
    paths = [directory / os.getenv("COMPANIES_FILE", "df_Uid_data_hack.csv"), directory / os.getenv("PERSONS_FILE", "df_Fid_Uid_link_hack.csv"), directory / os.getenv("PAYMENTS_FILE", "df_Uid_payment_hack.csv")]
    if not all(path.exists() for path in paths):
        if os.getenv("ALLOW_SYNTHETIC_FALLBACK", "1").lower() in {"1", "true", "yes"}:
            return _synthetic_bundle("один или несколько CSV не найдены")
        missing = ", ".join(str(path) for path in paths if not path.exists())
        raise FileNotFoundError(f"Файлы данных не найдены: {missing}")
    companies = _read_csv(paths[0])
    persons = _read_csv(paths[1])
    payments = _read_csv(paths[2])
    _validate_columns("companies", companies, COMPANY_COLUMNS)
    _validate_columns("persons", persons, PERSON_COLUMNS)
    _validate_columns("payments", payments, PAYMENT_COLUMNS)
    for frame, columns in [(companies, ["SYNTHETIC_U", "GROUP_ID"]), (persons, ["SYNTHETIC_F", "SYNTHETIC_U"]), (payments, ["PAYER", "BENEFICIARY"] )]:
        for column in columns:
            frame[column] = frame[column].astype("string").str.strip()
    warnings = []
    duplicate_count = int(companies["SYNTHETIC_U"].duplicated().sum())
    if duplicate_count:
        warnings.append(
            f"companies: найдено {duplicate_count} повторных SYNTHETIC_U; "
            "при поиске профиля используется первая строка"
        )
    payments["PAY_AMT"] = pd.to_numeric(payments["PAY_AMT"], errors="coerce")
    payments["PAY_CNT"] = pd.to_numeric(payments["PAY_CNT"], errors="coerce")
    if payments[["PAY_AMT", "PAY_CNT"]].isna().any().any():
        raise ValueError("payments: PAY_AMT и PAY_CNT должны быть числовыми")
    return DataBundle(companies, persons, payments, tuple(warnings))

DATA = load_data()
companies, persons, payments = DATA.companies, DATA.persons, DATA.payments
