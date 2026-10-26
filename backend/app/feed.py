from typing import Any
from .company_context import get_company_context

def _features(context: dict) -> dict[str, Any]:
    industry=context.get('industry') or {}; scale=context.get('scale') or {}; products=context.get('bank_products') or {}; trade=context.get('foreign_trade') or {}
    revenue=scale.get('revenue'); revenue=float(revenue) if revenue is not None else None; country=trade.get('country')
    return {'matched_okved': f"{industry.get('okved_code') or '—'} {industry.get('name') or 'Отрасль не указана'}", 'revenue_rub': revenue, 'has_loans': bool(products.get('credit')), 'has_leasing': bool(products.get('leasing')), 'has_deposits': bool(products.get('deposits')), 'foreign_trade_countries': country, 'influencing_signals': [f"Отрасль ОКВЭД: {industry.get('okved_code') or 'не указана'}", f"Выручка: {revenue / 1e9:.1f} млрд ₽" if revenue else 'Выручка не указана', 'Есть кредитные продукты' if products.get('credit') else 'Кредитные продукты не указаны', f"ВЭД: {country}" if country else 'Данные о ВЭД отсутствуют']}

def build_feed(company_id: str, role: str = 'CFO',limit: int=100,offset: int=0) -> dict[str, Any]:
    from .live_feed import events
    saved=events(company_id,role,limit,offset)
    from .storage.repositories import feed_counts
    from .versions import analysis_version
    total,critical=feed_counts(company_id,role,analysis_version(company_id))
    get_company_context(company_id)
    return {'company_id':company_id,'company_name':f'Обезличенная компания {company_id}','target_role':role,'total_events':total,'critical_events_count':critical,'events':saved}

def find_card(card_id: str) -> dict[str, Any] | None:
    from .live_feed import card
    saved=card(card_id)
    if saved:
        q=saved['six_questions']
        return {'title':saved['title'],'summary':q['q2_why_matters']['text'],'source':q['q3_bank_evaluation'].get('source_file') or '', 'event':saved}
    return None
