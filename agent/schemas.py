"""
Pydantic схемы данных для AI-пайплайна «Альфа Хак — Новостная аналитика».
Используются бэкендом (FastAPI), промпт-цепочками и интерфейсом.
"""

from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class UserRole(str, Enum):
    CEO = "CEO"                  # Генеральный директор / Собственник (стратегия, рынки, регулирование)
    CFO = "CFO"                  # Финансовый директор (ликвидность, кредиты, налоги, курс, ставка ЦБ)
    TREASURER = "TREASURER"      # Казначей / Главбух (овернайты, РКО, факторинг, транзакции)


class CompanyProfile(BaseModel):
    """Профиль компании из датасета банка (df_Uid_data_hack.csv)."""
    synthetic_u: str = Field(..., description="Уникальный идентификатор компании")
    display_name: str = Field(default="Крупное предприятие", description="Название для интерфейса")
    mainokved_code: str = Field(..., description="Код ОКВЭД")
    mainokved_name: str = Field(..., description="Наименование отрасли / деятельности")
    revenue_company: float = Field(..., description="Годовая выручка в рублях (>15 млрд)")
    org_type: Optional[str] = "Юридическое лицо"
    group_id: Optional[str] = Field(None, description="ID группы компаний (холдинга)")
    city: Optional[str] = None
    region: Optional[str] = None
    
    # Банковские продукты
    cl_product_rko: bool = Field(default=True, description="Наличие РКО")
    cl_product_gar: bool = Field(default=False, description="Банковские гарантии")
    cl_product_loa: bool = Field(default=False, description="Кредитные продукты (заемные средства)")
    cl_product_lea: bool = Field(default=False, description="Лизинг")
    cl_product_dep: bool = Field(default=False, description="Депозиты / овернайты")
    cl_product_zpp: bool = Field(default=False, description="Зарплатный проект")
    factoring_mark: bool = Field(default=False, description="Факторинг")
    
    # ВЭД
    fts_flag: bool = Field(default=False, description="Участие во внешнеэкономической деятельности")
    fts_country_name: Optional[str] = Field(None, description="Страны ВЭД (Китай, Индия, ОАЭ и т.д.)")


class NewsItem(BaseModel):
    """Сырая новость из внешних источников (Интерфакс, РБК, Коммерсантъ)."""
    news_id: str
    title: str
    body: str
    published_at: Optional[str] = None
    source_name: str = "СМИ"
    source_url: Optional[str] = None


class NewsClassification(BaseModel):
    """Результат работы Task #1 (Gemma 4 26B)."""
    is_relevant_business_event: bool = Field(..., description="Является ли реальным бизнес-событием (отсев спама)")
    category: str = Field(..., description="Категория: МАКРОЭКОНОМИКА, ОТРАСЛЬ, РЕГУЛИРОВАНИЕ, СЫРЬЕ, ВЭД")
    key_entities: List[str] = Field(default_factory=list, description="Компании, регуляторы, страны, товары")
    factual_essence: str = Field(..., description="Сжатая суть факта в 1-2 предложениях")


class RelevanceAssessment(BaseModel):
    """Результат работы Task #11: скоринг соответствия новости профилю клиента."""
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Оценка релевантности от 0.0 до 1.0")
    is_critical: bool = Field(..., description="Требует ли срочного внимания руководителя")
    relevance_rationale: str = Field(..., description="Почему новость затрагивает именно этот бизнес")
    affected_factors: List[str] = Field(default_factory=list, description="Кредиты, валюта, спрос, налоги, логистика")


class AlfaBankPosition(BaseModel):
    """Экспертная позиция Центра макроэкономических исследований Альфа-Банка (Task #4)."""
    synthesis_status: str = "no_sources"
    has_bank_report: bool = Field(..., description="Есть ли релевантный макро-отчет банка")
    source_report_title: Optional[str] = Field(None, description="Название отчета банка")
    position_text: str = Field(..., description="Позиция банка по данному событию")
    is_official_view: bool = Field(default=True, description="True если из отчета, False если гипотеза AI")
    sources: list[dict] = Field(default_factory=list)
    retrieval_query: Optional[str] = None
    evidence_text: Optional[str] = None


class NextBestAction(BaseModel):
    """Рекомендуемое следующее действие (Next Best Action) в банке."""
    action_type: str = Field(..., description="CONSULTATION | CREDIT | HEDGING | FACTORING | DEPOSIT")
    title: str = Field(..., description="Короткий заголовок кнопки действия")
    description: str = Field(..., description="Обоснование, зачем клиенту это действие")
    bank_product_tag: Optional[str] = Field(None, description="Связанный продукт Альфа-Банка")


class PersonalizedInsight(BaseModel):
    """Итоговая карточка инсайта для отображения в Альфа-Бизнес (Task #10)."""
    news_id: str
    company_id: str
    target_role: UserRole
    
    # 5 обязательных блоков по кейсу
    fact_summary: str = Field(..., description="Что произошло (факты без предположений)")
    why_it_matters: str = Field(..., description="Почему это важно именно для этой компании")
    alfa_bank_position: AlfaBankPosition
    
    risks: List[str] = Field(default_factory=list, description="Потенциальные риски для бизнеса")
    opportunities: List[str] = Field(default_factory=list, description="Потенциальные возможности")
    
    next_best_action: NextBestAction
    
    # Трассируемость и обязательные дисклеймеры
    sources: List[str] = Field(default_factory=list, description="Ссылки на источники")
    disclaimer: str = Field(
        default="Не является индивидуальной инвестиционной рекомендацией",
        description="Обязательный юридический дисклеймер"
    )


class ValidationReport(BaseModel):
    """Результат работы агента самопроверки / Fact-Checker (Task #12)."""
    is_valid: bool
    hallucination_detected: bool
    notes: str


class RagSynthesis(BaseModel):
    has_matching_report: bool = Field(strict=True)
    bank_official_view: str = Field(min_length=1,max_length=10000)
    citation_ids: list[str] = Field(default_factory=list)
