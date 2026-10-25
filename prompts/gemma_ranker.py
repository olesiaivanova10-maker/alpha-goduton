"""
Промпты для модели: Gemma 4 26B A4B
Задача: Оценка релевантности новости профилю конкретной компании (Task #11)

Особенности Gemma 4:
- Быстрое сопоставление признаков (ОКВЭД, выручка, кредиты, ВЭД) с фактами новости.
- Формирование численного скора (0.0 - 1.0) и перечня затронутых факторов.
"""

from typing import Dict, Any

SYSTEM_PROMPT = """Ты — экспертная система скоринга релевантности новостей для корпоративных клиентов банка.
Твоя задача — сопоставить профиль компании с новостью и выставить балл релевантности от 0.0 до 1.0.

ШКАЛА СКОРИНГА:
- 0.85 - 1.00 (Критическая релевантность):
  * Прямое совпадение по отрасли (ОКВЭД).
  * Решения по ключевой ставке для компании с крупными кредитами/лизингом.
  * Решения по пошлинам/валютам для компании с активным ВЭД в указанных странах.
- 0.50 - 0.84 (Умеренная релевантность):
  * Косвенное влияние через смежные цепочки поставок или общее макроэкономическое охлаждение/разогрев.
- 0.00 - 0.49 (Низкая / нулевая релевантность):
  * Событие из другой отрасли, не связанной с деятельностью компании.
  * Локальные региональные новости из чужого региона.

ФОРМАТ ВЫВОДА (ТОЛЬКО JSON):
{
  "relevance_score": 0.85,
  "is_critical": true/false,
  "relevance_rationale": "1-2 предложения, почему новость затрагивает именно этот бизнес",
  "affected_factors": ["кредитная нагрузка", "себестоимость сырья", "экспортная выручка"]
}
"""

USER_PROMPT_TEMPLATE = """СОПОСТАВЬ КОНТЕКСТ КОМПАНИИ И НОВОСТЬ:

[ПРОФИЛЬ КОМПАНИИ]:
- Название / ID: {company_name} ({company_id})
- ОКВЭД: {okved_code} — {okved_name}
- Выручка: {revenue_billions:.1f} млрд руб.
- Продукты банка: Кредиты={has_loans}, Лизинг={has_leasing}, Депозиты={has_deposits}, ВЭД={has_ved} (Страны: {ved_countries})

[НОВОСТЬ]:
- Заголовок: {news_title}
- Суть: {news_essence}
- Категория: {news_category}

Выдай оценку релевантности в JSON."""


def build_ranker_prompt(company: dict, news: dict) -> Dict[str, str]:
    return {
        "system": SYSTEM_PROMPT,
        "user": USER_PROMPT_TEMPLATE.format(
            company_name=company.get("display_name", "Клиент"),
            company_id=company.get("synthetic_u", "U_UNKNOWN"),
            okved_code=company.get("mainokved_code", "00.00"),
            okved_name=company.get("mainokved_name", "Не указан"),
            revenue_billions=company.get("revenue_company", 0) / 1e9,
            has_loans=company.get("cl_product_loa", False),
            has_leasing=company.get("cl_product_lea", False),
            has_deposits=company.get("cl_product_dep", False),
            has_ved=company.get("fts_flag", False),
            ved_countries=company.get("fts_country_name") or "Нет",
            news_title=news.get("title", ""),
            news_essence=news.get("factual_essence", news.get("body", "")[:300]),
            news_category=news.get("category", "ОБЩЕЕ")
        )
    }
