from typing import Any
from agent.bank_knowledge_base import ALFA_REPORTS_INDEX
from .company_context import get_company_context

def _features(context: dict) -> dict[str, Any]:
    industry=context.get('industry') or {}; scale=context.get('scale') or {}; products=context.get('bank_products') or {}; trade=context.get('foreign_trade') or {}
    revenue=scale.get('revenue'); revenue=float(revenue) if revenue is not None else None; country=trade.get('country')
    return {'matched_okved': f"{industry.get('okved_code') or '—'} {industry.get('name') or 'Отрасль не указана'}", 'revenue_rub': revenue, 'has_loans': bool(products.get('credit')), 'has_leasing': bool(products.get('leasing')), 'has_deposits': bool(products.get('deposits')), 'foreign_trade_countries': country, 'influencing_signals': [f"Отрасль ОКВЭД: {industry.get('okved_code') or 'не указана'}", f"Выручка: {revenue / 1e9:.1f} млрд ₽" if revenue else 'Выручка не указана', 'Есть кредитные продукты' if products.get('credit') else 'Кредитные продукты не указаны', f"ВЭД: {country}" if country else 'Данные о ВЭД отсутствуют']}

def _event(company_id: str, context: dict, report, score: float, role: str) -> dict[str, Any]:
    features=_features(context); source=report.source_filename
    return {'card_id': f'card-{company_id}-{report.chunk_id}', 'news_id': f'news-{report.chunk_id}', 'published_at': '2026-09-11T13:30:00Z', 'title': report.report_title.strip('«»'), 'relevance': {'score': score, 'is_critical': score >= .8, 'rationale': f'Материал сопоставлен с отраслью клиента и банковскими продуктами; роль: {role}', 'affected_areas': list(report.macro_topics[:3]) or ['бизнес-контекст']}, 'client_features': features, 'six_questions': {'q1_what_happened': {'question': 'Что произошло?', 'origin': 'ФАКТ', 'text': report.summary}, 'q2_why_matters': {'question': 'Почему это важно для этой компании?', 'origin': 'ВЫВОД ИИ', 'text': f"Событие относится к деятельности компании по ОКВЭД {features['matched_okved']}."}, 'q3_bank_evaluation': {'question': 'Как это оценивает банк?', 'origin': 'ПОЗИЦИЯ БАНКА', 'has_report': True, 'report_title': report.report_title, 'source_file': source, 'text': report.detailed_text}, 'q4_consequences': {'question': 'Какие последствия возможны?', 'origin': 'ВЫВОД ИИ', 'risks': [f"Изменение факторов: {', '.join(report.macro_topics[:2])}"], 'opportunities': [report.official_recommendation]}, 'q5_recommended_actions': {'question': 'Какие действия могут быть релевантны?', 'origin': 'РЕКОМЕНДАЦИЯ БАНКА', 'action_type': 'CONSULTATION', 'title': 'Обсудить сценарий с менеджером', 'description': report.official_recommendation, 'bank_product_tag': 'Корпоративные решения', 'button_text': 'Оставить заявку менеджеру'}, 'q6_basis_of_conclusion': {'question': 'На чем основан вывод?', 'origin': 'ИСТОЧНИКИ', 'sources': [{'type': 'ALFA_RESEARCH', 'name': 'Центр макроисследований Альфа-Банка', 'url_or_file': source, 'page': 1}], 'client_signals_used': features['influencing_signals']}}, 'disclaimer': 'Не является индивидуальной инвестиционной рекомендацией'}

def build_feed(company_id: str, role: str = 'CFO') -> dict[str, Any]:
    context=get_company_context(company_id); industry=((context.get('industry') or {}).get('name') or '').lower(); trade=bool((context.get('foreign_trade') or {}).get('has_fts_data')); credit=bool((context.get('bank_products') or {}).get('credit')); ranked=[]
    for report in ALFA_REPORTS_INDEX:
        text=' '.join(report.target_sectors + report.macro_topics).lower(); score=.55 + (.12 if any(w in text for w in industry.split() if len(w)>4) else 0) + (.08 if trade and any(x in text for x in ('экспорт','вэд','валют','китай')) else 0) + (.08 if credit and any(x in text for x in ('кредит','ставк','финанс')) else 0); ranked.append((min(round(score,2),.99), report))
    ranked.sort(key=lambda item:(-item[0], item[1].chunk_id)); events=[_event(company_id, context, report, score, role) for score, report in ranked[:3]]
    return {'company_id': company_id, 'company_name': f'Обезличенная компания {company_id}', 'target_role': role, 'total_events': len(events), 'critical_events_count': sum(e['relevance']['is_critical'] for e in events), 'events': events}

def find_card(card_id: str) -> dict[str, Any] | None:
    for report in ALFA_REPORTS_INDEX:
        if report.chunk_id in card_id: return {'title': report.report_title, 'summary': report.summary, 'source': report.source_filename}
    return None
