from .data_loader import companies, persons, payments
import pandas as pd


def _value(row, column):
    value = row.get(column)
    if pd.isna(value):return None
    return value.item() if hasattr(value,"item") else value


def get_company_context(company_id: str) -> dict:
    company_id = str(company_id)
    if "SYNTHETIC_U" not in companies.columns:
        raise ValueError("Файл юридических лиц не загружен")
    rows = companies[companies["SYNTHETIC_U"] == company_id]
    if rows.empty:
        raise ValueError(f"Компания {company_id} не найдена")

    company = rows.iloc[0]
    group_id = _value(company, "GROUP_ID")
    group_rows = companies[companies["GROUP_ID"] == group_id] if group_id else rows
    warnings = []
    if not _value(company, "REVENUE_COMPANY"):
        warnings.append("Выручка отсутствует или является технической заглушкой")

    related = []
    if {"SYNTHETIC_U", "SYNTHETIC_F"}.issubset(persons.columns):
        for _, row in persons[persons["SYNTHETIC_U"] == company_id].head(50).iterrows():
            related.append({"person_id": _value(row, "SYNTHETIC_F"), "city": _value(row, "CITY_NAME"), "region": _value(row, "RC_NAME")})

    counterparties = []
    if {"PAYER", "BENEFICIARY"}.issubset(payments.columns):
        outgoing = payments[payments["PAYER"] == company_id]
        incoming = payments[payments["BENEFICIARY"] == company_id]
        for _, row in outgoing.iterrows():
            counterparties.append({"company_id": _value(row, "BENEFICIARY"), "direction": "outgoing", "payment_amount": _value(row, "PAY_AMT"), "payment_count": _value(row, "PAY_CNT")})
        for _, row in incoming.iterrows():
            counterparties.append({"company_id": _value(row, "PAYER"), "direction": "incoming", "payment_amount": _value(row, "PAY_AMT"), "payment_count": _value(row, "PAY_CNT")})

    return {
        "company_id": company_id,
        "group_id": str(group_id) if group_id else None,
        "industry": {"okved_code": _value(company, "MAINOKVED_CODE"), "name": _value(company, "MAINOKVED_NAME")},
        "organization": {"type": _value(company, "ORG_TYPE"), "ownership": _value(company, "OKFS_NAME"), "age": _value(company, "COMPANY_AGE_YEARS_GRADATION"), "development_stage": _value(company, "ECO_MARK_LABEL")},
        "location": {"city": _value(company, "CITY"), "region": _value(company, "REGION")},
        "scale": {"revenue": _value(company, "REVENUE_COMPANY"), "employees_fns": _value(company, "AMOUNT_WORKERS_FNS_GRADATION"), "employees_spark": _value(company, "AMOUNT_WORKERS_SPARK_GRADATION")},
        "bank_products": {key: _value(company, column) for key, column in {"rko": "CL_PRODUCT_RKO_MARK", "credit": "CL_PRODUCT_LOA_MARK", "leasing": "CL_PRODUCT_LEA_MARK", "guarantees": "CL_PRODUCT_GAR_MARK", "deposits": "CL_PRODUCT_DEP_MARK", "salary_project": "CL_PRODUCT_ZPP_MARK", "factoring": "FACTORING_MARK"}.items()},
        "foreign_trade": {"has_fts_data": _value(company, "FTS_FLAG"), "country": _value(company, "FTS_COUNTRY_NAME")},
        "group_companies": [str(value) for value in group_rows["SYNTHETIC_U"].tolist()],
        "related_persons": related,
        "counterparties": counterparties,
        "warnings": warnings,
    }
