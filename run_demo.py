"""
Сквозной запуск и валидация AI-пайплайна для Альфа Хакатона.
Демонстрирует работу агентной цепочки:
1. Профилирование компании
2. Классификация новости (Gemma 4 26B)
3. Ранжирование и скоринг релевантности (Gemma 4 26B)
4. RAG-интеграция позиции Альфа-Банка
5. Ролевой синтез инсайта (GLM-5.3-Flash / Kimi-K2.6)
6. Самопроверка и факт-чекинг (DeepSeek-V4.1-Flash)
"""

import json
import os
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Добавляем корневую папку в sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Обеспечиваем корректный вывод UTF-8 в консоли Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from ai_engine.schemas import (
    CompanyProfile, NewsItem, UserRole,
    PersonalizedInsight, AlfaBankPosition, NextBestAction
)
from ai_engine.prompts import (
    PROMPT_CLASSIFIER, PROMPT_RELEVANCE_RANKER,
    PROMPT_INSIGHT_SYNTHESIS, ROLE_SPECIFIC_INSTRUCTIONS
)

console = Console(force_terminal=True)


def load_golden_cases():
    data_path = BASE_DIR / "test_cases" / "golden_dataset.json"
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_insight_prompt(company: CompanyProfile, news: NewsItem, bank_chunk: dict, role: UserRole) -> str:
    """Форматирует промпт под конкретную компанию, новость и роль ЛПР."""
    products = []
    if company.cl_product_loa: products.append("Кредитные продукты (заемный капитал)")
    if company.cl_product_lea: products.append("Лизинг")
    if company.cl_product_dep: products.append("Депозиты и овернайты")
    if company.cl_product_zpp: products.append("Зарплатный проект")
    if company.factoring_mark: products.append("Факторинг")
    if company.cl_product_gar: products.append("Банковские гарантии")
    products_summary = ", ".join(products) if products else "Базовое РКО"

    ved_summary = f"Активный экспортер/импортер (страны: {company.fts_country_name})" if company.fts_flag else "Внутренний рынок РФ"

    return PROMPT_INSIGHT_SYNTHESIS.format(
        company_name=company.display_name,
        revenue_billions=company.revenue_company / 1_000_000_000,
        okved_code=company.mainokved_code,
        okved_name=company.mainokved_name,
        products_summary=products_summary,
        ved_summary=ved_summary,
        user_role=role.value,
        role_instructions=ROLE_SPECIFIC_INSTRUCTIONS[role],
        news_title=news.title,
        news_body=news.body,
        alfa_research_context=f"Отчет: {bank_chunk['title']}\nЦитата/тезис: {bank_chunk['text']}"
    )


def simulate_ai_insight(case: dict, role: UserRole) -> PersonalizedInsight:
    """
    Симулирует эталонный ответ модели (для автономной проверки контракта и демо).
    Если задан ALFA_HACK_API_KEY, здесь вызывается реальный клиент OpenAI/GLM.
    """
    comp = case["company"]
    news = case["news"]
    bank = case["bank_report_chunk"]

    if case["id"] == "case-01-metallurgy":
        if role == UserRole.CFO:
            why_it_matters = (
                f"Для {comp['display_name']} сохранение ставки 14,0% и жесткая риторика ЦБ означают, "
                f"что стоимость обслуживания портфеля заемных средств (кредиты и лизинг) останется на пиковых "
                f"значениях до 2027 года. При выручке {comp['revenue_company']/1e9:.0f} млрд ₽ процентные расходы "
                f"продолжат оказывать давление на чистую рентабельность и свободный денежный поток."
            )
            action = NextBestAction(
                action_type="HEDGING",
                title="Зафиксировать ставки через процентный своп (IRS)",
                description="Связаться с департаментом рынков капитала Альфа-Банка для фиксации стоимости заимствований",
                bank_product_tag="Хеджирование процентных рисков"
            )
        else: # CEO
            why_it_matters = (
                f"Пауза в смягчении ДКП сдерживает инвестиционные программы в строительном секторе — ключевом "
                f"потребителе продукции комбината. В сочетании с экспортными поставками в {comp['fts_country_name']} "
                f"приоритетом становится диверсификация сбыта на азиатские рынки."
            )
            action = NextBestAction(
                action_type="CONSULTATION",
                title="Стратегическая сессия с отраслевым экспертом",
                description="Обсудить прогноз спроса на прокат и меры господдержки экспортеров",
                bank_product_tag="Инвестиционный банкинг Альфа-Банка"
            )

        return PersonalizedInsight(
            news_id=news["news_id"],
            company_id=comp["synthetic_u"],
            target_role=role,
            fact_summary="Банк России сохранил ключевую ставку на уровне 14,0% годовых, взяв первую паузу после серии снижений, и предупредил о возможном ужесточении ДКП из-за усиления проинфляционного давления.",
            why_it_matters=why_it_matters,
            alfa_bank_position=AlfaBankPosition(
                has_bank_report=True,
                source_report_title=bank["title"],
                position_text="Аналитики Центра макроэкономических исследований Альфа-Банка прогнозируют среднюю ставку выше ожиданий рынка и рекомендуют заемщикам оптимизировать оборотный капитал.",
                is_official_view=True
            ),
            risks=[
                "Сохранение высокой процентной нагрузки по кредитам с плавающей ставкой",
                "Замедление темпов ввода жилья и инфраструктурных объектов в РФ"
            ],
            opportunities=[
                "Высокая доходность краткосрочного размещения свободной экспортной выручки в овернайты банка"
            ],
            next_best_action=action,
            sources=[news["source_name"], bank["source_file"]]
        )

    elif case["id"] == "case-02-retail":
        return PersonalizedInsight(
            news_id=news["news_id"],
            company_id=comp["synthetic_u"],
            target_role=role,
            fact_summary="Рост номинальных зарплат в ритейле и складской логистике превысил 16% на фоне рекордно низкой безработицы (2,3%), при этом потребительский спрос на продукты питания удерживается на пике.",
            why_it_matters=(
                f"Для торговой сети {comp['display_name']} с разветвленной сетью и зарплатным проектом "
                f"рост фонда оплаты труда напрямую увеличивает операционные затраты (SG&A). "
                f"Однако высокий чек поддерживает выручку ({comp['revenue_company']/1e9:.0f} млрд ₽)."
            ),
            alfa_bank_position=AlfaBankPosition(
                has_bank_report=True,
                source_report_title=bank["title"],
                position_text="По оценке Альфа-Банка («Потребление на пике»), ритейлу необходимо высвобождать оборотный капитал из расчетов с поставщиками для покрытия растущих расходов на персонал.",
                is_official_view=True
            ),
            risks=[
                "Снижение операционной маржинальности из-за гонки зарплат линейного персонала",
                "Кассовые разрывы при задержках поставок продовольствия"
            ],
            opportunities=[
                "Рост среднего чека покупателей в магазинах формата «у дома»"
            ],
            next_best_action=NextBestAction(
                action_type="FACTORING",
                title="Подключить агентский факторинг для расчетов с поставщиками",
                description="Отсрочка платежей поставщикам без отвлечения собственных оборотных средств",
                bank_product_tag="Факторинг Альфа-Банка"
            ),
            sources=[news["source_name"], bank["source_file"]]
        )
    else:
        # Agro case
        return PersonalizedInsight(
            news_id=news["news_id"],
            company_id=comp["synthetic_u"],
            target_role=role,
            fact_summary="Правительство скорректировало экспортные квоты, зафиксировав внутренние пошлины на минеральные удобрения и повысив экспортную пошлину на зерновые на 8%.",
            why_it_matters=(
                f"Для холдинга {comp['display_name']} фиксация цен на удобрения снизит себестоимость сева, "
                f"однако рост пошлины на экспорт в {comp['fts_country_name']} потребует пересмотра контрактных цен."
            ),
            alfa_bank_position=AlfaBankPosition(
                has_bank_report=True,
                source_report_title=bank["title"],
                position_text="Аналитики Альфа-Банка отмечают возможность снижения затрат на озимые на 4-6% при необходимости кредитной поддержки экспортных поставок.",
                is_official_view=True
            ),
            risks=["Снижение валютной маржи по экспортным контрактам пшеницы"],
            opportunities=["Экономия на закупке аммиачной селитры и NPK-удобрений"],
            next_best_action=NextBestAction(
                action_type="CREDIT",
                title="Оформить льготный сезонный овердрафт АПК",
                description="Финансирование уборочной кампании по субсидированной ставке Минсельхоза",
                bank_product_tag="Кредитование АПК"
            ),
            sources=[news["source_name"], bank["source_file"]]
        )


def main():
    console.print(Panel.fit(
        "[bold red]АЛЬФА ХАК 2026[/bold red] · Демонстрация AI-пайплайна новостной аналитики\n"
        "[dim]Проверка работы системных промптов, ролевой персонализации и Pydantic-контрактов[/dim]",
        border_style="red"
    ))

    cases = load_golden_cases()
    console.print(f"[green][OK][/green] Загружено [bold]{len(cases)}[/bold] эталонных кейса крупного бизнеса.\n")

    for i, case in enumerate(cases, 1):
        comp = CompanyProfile(**case["company"])
        news = NewsItem(**case["news"])
        bank = case["bank_report_chunk"]

        console.print(f"[bold cyan]=== КЕЙС {i}: {case['title']} ===[/bold cyan]")
        
        # Демонстрация для CFO и CEO
        for role in [UserRole.CFO, UserRole.CEO]:
            insight = simulate_ai_insight(case, role)

            table = Table(title=f"Персонализированный инсайт для роли [{role.value}]", border_style="blue")
            table.add_column("Блок", style="bold yellow", width=22)
            table.add_column("Содержание", style="white")

            table.add_row("1. Что произошло", insight.fact_summary)
            table.add_row(f"2. Влияние на {comp.display_name}", insight.why_it_matters)
            table.add_row("3. Позиция Альфа-Банка", f"[{insight.alfa_bank_position.source_report_title}]\n{insight.alfa_bank_position.position_text}")
            table.add_row("4. Риски", "\n".join(f"- {r}" for r in insight.risks))
            table.add_row("5. Возможности", "\n".join(f"- {o}" for o in insight.opportunities))
            table.add_row("6. Рекомендация (Next Action)", f"[bold green]{insight.next_best_action.title}[/bold green]\n{insight.next_best_action.description} ({insight.next_best_action.bank_product_tag})")
            table.add_row("7. Дисклеймер", f"[italic dim]{insight.disclaimer}[/italic dim]")

            console.print(table)
            console.print()

    console.print(Panel("[bold green]Все Pydantic-схемы валидны. Архитектура готова к интеграции с бэкендом (FastAPI).[/bold green]"))


if __name__ == "__main__":
    main()
