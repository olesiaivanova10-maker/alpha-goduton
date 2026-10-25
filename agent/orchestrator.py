"""
Модуль: Agent Orchestrator (Task #12)
Управляет агентным процессом многошаговой подготовки персонализированного бизнес-инсайта.

Модели в оркестрации (по архитектуре команды):
1. Gemma 4        -> Фильтрация и классификация новости
2. Gemma 4        -> Скоринг релевантности под контекст компании
3. Qwen 3.6 + BGE -> RAG-поиск и выжимка экспертной позиции Альфа-Банка
4. DeepSeek-V4.1  -> Глубокий синтез инсайта (причинно-следственные связи, баланс, риски)
5. GLM-5.3        -> Аудит, факт-чекинг и валидация перед отдачей в UI

Поддерживает работу как с живым API хакатона, так и в воспроизводимом оффлайн-режиме.
"""

import json
import logging
from urllib.parse import urlsplit
from typing import Dict, Any, Optional, Tuple
try:
    from openai import OpenAI
except ImportError:  # allows offline demo and data tests without the optional SDK
    OpenAI = None

from .schemas import (
    CompanyProfile, NewsItem, UserRole,
    NewsClassification, RelevanceAssessment,
    PersonalizedInsight, AlfaBankPosition, NextBestAction,
    ValidationReport
)
from .models_cfg import config, PipelineTask, ModelName
from .bank_knowledge_base import bank_retriever, BankReportChunk
from .prompts.gemma_classifier import build_classifier_prompt
from .prompts.gemma_ranker import build_ranker_prompt
from .prompts.qwen_rag import build_rag_prompt
from .prompts.deepseek_insight import build_deepseek_insight_prompt
from .prompts.glm_orchestrator import build_verification_prompt

logger = logging.getLogger("ai_engine.orchestrator")


class AgentOrchestrator:
    """Главный координатор агентного графа анализа новостей."""

    def __init__(self):
        self.cfg = config
        self.has_live_api = (
            urlsplit(self.cfg.base_url).scheme in {"https", "http"} and
            bool(urlsplit(self.cfg.base_url).hostname) and
            bool(self.cfg.api_key) and
            self.cfg.api_key != "mock-token" and
            not self.cfg.api_key.startswith("mock")
        )
        if self.has_live_api and OpenAI is not None:
            self.client = OpenAI(
                api_key=self.cfg.api_key,
                base_url=self.cfg.base_url,
                timeout=self.cfg.timeout_sec,
                max_retries=0
            )
        else:
            self.client = None
            self.has_live_api = False

    def _call_llm(self, task: PipelineTask, system_prompt: str, user_prompt: str) -> str:
        """Вызов конкретной LLM с параметрами из models_cfg.py."""
        model_cfg = self.cfg.get_config_for_task(task)

        if not self.has_live_api:
            # Оффлайн-заглушка для отладки без API
            return self._mock_response(task, user_prompt)

        response = self.client.chat.completions.create(
            model=model_cfg.model.value,
            temperature=model_cfg.temperature,
            max_tokens=model_cfg.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            timeout=20 if task == PipelineTask.ORCHESTRATOR else self.cfg.timeout_sec,
            response_format={"type": "json_object"} if model_cfg.supports_structured_output else None
        )
        return response.choices[0].message.content

    def step_1_classify(self, news: NewsItem) -> NewsClassification:
        """Шаг 1 (Gemma 4): Фильтрация и извлечение сути события."""
        prompt = build_classifier_prompt(title=news.title, body=news.body)
        raw_res = self._call_llm(PipelineTask.CLASSIFICATION, prompt["system"], prompt["user"])
        try:
            data = json.loads(raw_res)
            return NewsClassification(**data)
        except Exception:
            if self.has_live_api:
                raise ValueError("Невалидный ответ классификатора")
            return NewsClassification(
                is_relevant_business_event=True,
                category="МАКРОЭКОНОМИКА",
                key_entities=["Банк России"],
                factual_essence=news.title
            )

    def step_2_rank_relevance(self, company: CompanyProfile, news: NewsItem, classification: NewsClassification) -> RelevanceAssessment:
        """Шаг 2 (Gemma 4): Скоринг соответствия новости бизнесу клиента."""
        company_dict = company.model_dump()
        news_dict = {
            "title": news.title,
            "factual_essence": classification.factual_essence,
            "category": classification.category
        }
        prompt = build_ranker_prompt(company_dict, news_dict)
        raw_res = self._call_llm(PipelineTask.RELEVANCE, prompt["system"], prompt["user"])
        try:
            data = json.loads(raw_res)
            return RelevanceAssessment(**data)
        except Exception:
            if self.has_live_api:
                raise ValueError("Невалидный ответ ранжирования")
            # Детерминированный fallback по отрасли и кредитам
            has_debt_sensitivity = company.cl_product_loa and "СТАВКА" in classification.category
            score = 0.90 if has_debt_sensitivity else 0.70
            return RelevanceAssessment(
                relevance_score=score,
                is_critical=score >= 0.85,
                relevance_rationale=f"Влияние через отрасль {company.mainokved_name} и финансовую структуру",
                affected_factors=["кредитная нагрузка", "себестоимость"]
            )

    def step_3_rag_bank_context(
        self,
        news: NewsItem,
        classification: NewsClassification,
        company: Optional[CompanyProfile] = None,
        bank_chunk: Optional[dict] = None
    ) -> AlfaBankPosition:
        """Шаг 3 (Qwen 3.6 + BGE): RAG-поиск экспертной позиции Альфа-Банка."""
        if bank_chunk:
            return AlfaBankPosition(
                has_bank_report=True,
                source_report_title=bank_chunk.get("title"),
                position_text=bank_chunk.get("text", ""),
                is_official_view=True
            )

        from .rag.retriever import retrieve_bank_context
        query = f"{news.title} {classification.factual_essence}"
        chunks = retrieve_bank_context(query, company.model_dump() if company else None, top_k=2)
        if not chunks:
            return AlfaBankPosition(has_bank_report=False, source_report_title=None,
                position_text="Прямой аналитический отчёт не найден.", is_official_view=False)
        sources = [{"filename":c.filename,"page":c.page,"chunk_id":c.chunk_id,
                    "score":c.score,"extraction_method":c.extraction_method} for c in chunks]
        excerpts = "\n\n".join(f"{c.filename}, страница {c.page}: {c.text[:1200]}" for c in chunks)
        if self.has_live_api:
            prompt = build_rag_prompt({"title":news.title,"factual_essence":classification.factual_essence},excerpts)
            try:
                data = json.loads(self._call_llm(PipelineTask.RAG,prompt['system'],prompt['user']))
                text = data['bank_official_view']
                if not isinstance(text,str) or not text.strip(): raise ValueError('Empty RAG response')
                return AlfaBankPosition(has_bank_report=True,source_report_title=chunks[0].filename,
                    position_text=text,is_official_view=bool(data.get('has_matching_report')),sources=sources,retrieval_query=query,evidence_text=excerpts)
            except (ValueError,KeyError,TypeError):
                logger.warning('Invalid RAG synthesis JSON; returning excerpts')
        return AlfaBankPosition(has_bank_report=True,source_report_title=chunks[0].filename,
            position_text=excerpts,is_official_view=False,sources=sources,retrieval_query=query,evidence_text=excerpts)

    def step_4_deep_insight(
        self,
        company: CompanyProfile,
        news: NewsItem,
        bank_position: AlfaBankPosition,
        role: UserRole
    ) -> PersonalizedInsight:
        """Шаг 4 (DeepSeek-V4.1): Глубокий расчет влияния на баланс и синтез инсайта."""
        company_dict = company.model_dump()
        news_dict = news.model_dump()
        bank_dict = {
            "title": bank_position.source_report_title,
            "text": bank_position.position_text
        }
        prompt = build_deepseek_insight_prompt(company_dict, news_dict, bank_dict, role)
        raw_res = self._call_llm(PipelineTask.DEEP_INTERPRETATION, prompt["system"], prompt["user"])

        try:
            data = json.loads(raw_res)
            return PersonalizedInsight(
                news_id=news.news_id,
                company_id=company.synthetic_u,
                target_role=role,
                fact_summary=data["fact_summary"],
                why_it_matters=data["why_it_matters"],
                alfa_bank_position=bank_position,
                risks=data.get("risks", []),
                opportunities=data.get("opportunities", []),
                next_best_action=NextBestAction(**data["next_best_action"]),
                sources=([news.source_url or news.source_name] + [x["filename"] for x in bank_position.sources]),
                disclaimer="Не является индивидуальной инвестиционной рекомендацией"
            )
        except Exception:
            raise ValueError("Модель не вернула валидный персонализированный инсайт")

    def step_5_fact_check_and_audit(
        self,
        company: CompanyProfile,
        news: NewsItem,
        bank_position: AlfaBankPosition,
        insight: PersonalizedInsight
    ) -> ValidationReport:
        """Шаг 5 (GLM-5.3): Проверка фактологии, отсутствия галлюцинаций и наличия дисклеймера."""
        prompt = build_verification_prompt(
            news_text=f"Дата проверки: {__import__('datetime').datetime.now(__import__('datetime').timezone.utc).date().isoformat()}. Дата публикации: {news.published_at or 'не указана'}.\n{news.title}\n{news.body}",
            bank_context=bank_position.model_dump_json(),
            company_context="FTS_FLAG означает наличие данных внешней торговли; FTS_COUNTRY_NAME — известные страны ВЭД, но не направление и не валюта. Кредитный продукт не доказывает размер долга.\n"+company.model_dump_json(),
            insight_json=insight.model_dump_json(indent=2)
        )
        last_error = None
        for task in (PipelineTask.ORCHESTRATOR, PipelineTask.CLASSIFICATION):
            try:
                raw_res = self._call_llm(task, prompt["system"], prompt["user"])
                data = json.loads(raw_res)
                if type(data.get('is_valid')) is not bool or type(data.get('hallucination_detected')) is not bool:
                    raise ValueError('Audit verdict missing')
                prefix = 'Резервный аудит Gemma: ' if task == PipelineTask.CLASSIFICATION else ''
                return ValidationReport(is_valid=data['is_valid'],hallucination_detected=data['hallucination_detected'],notes=prefix+str(data.get('audit_comment','')))
            except Exception as error:
                last_error = type(error).__name__
        return ValidationReport(is_valid=False,hallucination_detected=False,
            notes=f'Аудит недоступен ({last_error}); публикация заблокирована.')

    def run_pipeline(
        self,
        company: CompanyProfile,
        news: NewsItem,
        bank_chunk: Optional[dict] = None,
        role: UserRole = UserRole.CFO,
        relevance_threshold: float = 0.50,
        save_to_disk: bool = True
    ) -> Optional[Tuple[PersonalizedInsight, ValidationReport]]:
        """
        Полный сквозной цикл агентного графа:
        1. Gemma 4 (Классификация)
        2. Gemma 4 (Ранжирование) -> Отсев нерелевантного
        3. Qwen 3.6 (RAG отчетов банка)
        4. DeepSeek-V4.1 (Глубокий синтез под роль)
        5. GLM-5.3 (Самопроверка и аудит)
        6. Сохранение отчета в файл на диск (data/reports/)
        """
        # Шаг 1: Фильтрация
        classification = self.step_1_classify(news)
        if not classification.is_relevant_business_event:
            logger.info("Новость отсеяна как нерелевантный шум.")
            return None

        # Шаг 2: Скоринг релевантности под компанию
        relevance = self.step_2_rank_relevance(company, news, classification)
        if relevance.relevance_score < relevance_threshold:
            logger.info(f"Релевантность новости ({relevance.relevance_score:.2f}) ниже порога {relevance_threshold}.")
            return None

        # Шаг 3: RAG позиция Альфа-Банка (Qwen 3.6 + BGE)
        bank_position = self.step_3_rag_bank_context(news, classification, company=company, bank_chunk=bank_chunk)

        # Шаг 4: Глубокая финансовая интерпретация (DeepSeek)
        insight = self.step_4_deep_insight(company, news, bank_position, role)

        # Шаг 5: Аудит и факт-чекинг (GLM-5.3)
        audit = self.step_5_fact_check_and_audit(company, news, bank_position, insight)

        # Шаг 6: Сохранение аналитической карточки в файл на диск
        if save_to_disk:
            try:
                self.save_insight_to_file(insight, company, news, audit)
            except Exception as e:
                logger.warning(f"Не удалось сохранить отчет на диск: {e}")

        return insight, audit

    def save_insight_to_file(
        self,
        insight: PersonalizedInsight,
        company: CompanyProfile,
        news: NewsItem,
        audit: Optional[ValidationReport] = None,
        output_dir: Optional[Any] = None
    ) -> Any:
        """Сохраняет сгенерированный инсайт в отдельный JSON-файл отчета для сервиса ленты."""
        from datetime import datetime
        from pathlib import Path

        target_dir = Path(output_dir or (Path(__file__).resolve().parent.parent / "backend" / "data" / "reports"))
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_company_id = str(company.synthetic_u).replace("/", "_")
        safe_news_id = str(news.news_id).replace("/", "_")
        filename = f"report_{safe_company_id}_{safe_news_id}.json"
        filepath = target_dir / filename

        card_data = {
            "card_id": f"{company.synthetic_u}:{news.news_id}",
            "company_id": company.synthetic_u,
            "company_name": company.display_name,
            "role": insight.target_role.value if hasattr(insight.target_role, "value") else str(insight.target_role),
            "title": news.title,
            "summary": insight.fact_summary,
            "fact_summary": insight.fact_summary,
            "why_it_matters": insight.why_it_matters,
            "importance": "high",
            "alfa_bank_position": {
                "has_bank_report": insight.alfa_bank_position.has_bank_report,
                "source_report_title": insight.alfa_bank_position.source_report_title,
                "position_text": insight.alfa_bank_position.position_text,
                "is_official_view": insight.alfa_bank_position.is_official_view,
            },
            "risks": insight.risks,
            "opportunities": insight.opportunities,
            "recommended_action": insight.next_best_action.title if insight.next_best_action else "Обсудить с банком",
            "next_best_action": {
                "action_type": insight.next_best_action.action_type,
                "title": insight.next_best_action.title,
                "description": insight.next_best_action.description,
                "bank_product_tag": insight.next_best_action.bank_product_tag,
            } if insight.next_best_action else None,
            "origin": "alfa_bank" if insight.alfa_bank_position.is_official_view else "ai_insight",
            "sources": insight.sources,
            "provenance": {
                "fact": news.source_name,
                "bank": insight.alfa_bank_position.source_report_title or "Аналитический центр Альфа-Банка",
                "ai": "DeepSeek-V4.1-Flash",
            },
            "audit": {
                "is_valid": audit.is_valid if audit else True,
                "hallucination_detected": audit.hallucination_detected if audit else False,
                "notes": audit.notes if audit else "Верифицировано",
            },
            "disclaimer": insight.disclaimer,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(card_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Отчет успешно сохранен на диск: {filepath}")
        return filepath

    def _build_fallback_insight(
        self,
        company: CompanyProfile,
        news: NewsItem,
        bank_pos: AlfaBankPosition,
        role: UserRole
    ) -> PersonalizedInsight:
        """Надежный фоллбэк генерации при недоступности сети."""
        if role == UserRole.CFO:
            why = (
                f"Для компании {company.display_name} (выручка {company.revenue_company/1e9:.1f} млрд ₽) "
                f"событие напрямую затрагивает структуру оборотного капитала и стоимость обслуживания долга."
            )
            action = NextBestAction(
                action_type="HEDGING",
                title="Оптимизировать процентную и кредитную нагрузку",
                description="Провести анализ кредитного портфеля с персональным менеджером банка",
                bank_product_tag="Кредитование и Хеджирование"
            )
        else:
            why = (
                f"Событие формирует новые отраслевые условия для {company.display_name} "
                f"в сегменте {company.mainokved_name}."
            )
            action = NextBestAction(
                action_type="CONSULTATION",
                title="Консультация с отраслевым аналитиком Альфа-Банка",
                description="Оценить влияние рыночных изменений на среднесрочные контракты",
                bank_product_tag="Корпоративное консультирование"
            )

        return PersonalizedInsight(
            news_id=news.news_id,
            company_id=company.synthetic_u,
            target_role=role,
            fact_summary=f"Событие: {news.title}. Зафиксированы изменения регуляторных или рыночных условий.",
            why_it_matters=why,
            alfa_bank_position=bank_pos,
            risks=["Повышение операционных издержек", "Волатильность условий финансирования"],
            opportunities=["Оптимизация структуры расчетов с контрагентами"],
            next_best_action=action,
            sources=[news.source_name],
            disclaimer="Не является индивидуальной инвестиционной рекомендацией"
        )

    def _mock_response(self, task: PipelineTask, prompt: str) -> str:
        """Мок-ответы для оффлайн тестирования с валидным JSON."""
        if task == PipelineTask.CLASSIFICATION:
            return json.dumps({
                "is_relevant_business_event": True,
                "category": "МАКРОЭКОНОМИКА",
                "key_entities": ["Банк России", "Ключевая ставка"],
                "factual_essence": "ЦБ РФ сохранил ставку на 14% и дал жесткий сигнал."
            })
        elif task == PipelineTask.RELEVANCE:
            return json.dumps({
                "relevance_score": 0.92,
                "is_critical": True,
                "relevance_rationale": "Прямое влияние на стоимость кредитного финансирования",
                "affected_factors": ["кредитная нагрузка", "ликвидность"]
            })
        elif task == PipelineTask.ORCHESTRATOR:
            return json.dumps({
                "is_valid": True,
                "hallucination_detected": False,
                "audit_comment": "Все факты соответствуют исходным документам, дисклеймер присутствует."
            })
        return "{}"
