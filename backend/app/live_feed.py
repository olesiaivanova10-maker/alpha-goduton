"""Company-specific persisted insights; explicit background generation."""

import hashlib
import json
from agent.schemas import NewsItem, UserRole


from .storage import repositories as repo


def events(company_id, role, limit=100, offset=0):
    from .versions import analysis_version

    return sorted(
        repo.feed(company_id, role, analysis_version(company_id), limit, offset),
        key=lambda e: e["relevance"]["score"],
        reverse=True,
    )


def card(card_id):
    return repo.insight(card_id)


def job(job_id):
    return repo.get_job(job_id)


def set_job(job_id, status, detail):
    repo.put_job(job_id, status, detail)


def generate(job_id, company_id, role, records, service):
    from .company_context import get_company_context
    from .versions import analysis_version

    version = analysis_version(company_id)
    from .feed import _features

    set_job(job_id, "running", {"processed": 0})
    context = get_company_context(company_id)
    profile = service.profile(company_id)
    from agent.adapter import adapt_backend_context_to_profile

    company = adapt_backend_context_to_profile(profile)
    from .news_journal import register, transition

    register(records)
    published = 0
    failures = []
    for record in records:
        revision = record.get("content_hash") or repo.digest_payload(record)
        try:
            expected_id = (
                "card-"
                + company_id
                + "-"
                + hashlib.sha256(
                    (
                        record["news_id"] + "|" + role + "|" + version + "|" + revision
                    ).encode()
                ).hexdigest()[:20]
            )
            if card(expected_id):
                transition(
                    record["news_id"],
                    company_id,
                    role,
                    "published",
                    "deduplicated",
                    "Карточка уже опубликована; повторного вызова модели не было.",
                    job_id,
                    expected_id,
                )
                published += 1
                continue
            news = NewsItem(
                news_id=record["news_id"],
                title=record["title"],
                body=record["body"],
                source_name=record["source_name"],
                source_url=record["source_url"],
                published_at=record.get("published_at"),
            )
            agent = service.orchestrator
            set_job(
                job_id,
                "running",
                {
                    "stage": "Проверяем деловую значимость новости",
                    "published": published,
                },
            )
            transition(
                record["news_id"],
                company_id,
                role,
                "sent",
                "classify",
                "Проверяем деловую значимость новости",
                job_id,
            )
            from .classification import classify_once

            classification = classify_once(agent, news)
            if not classification.is_relevant_business_event:
                transition(
                    news.news_id,
                    company_id,
                    role,
                    "rejected",
                    "classify",
                    "Модель не признала новость значимым деловым событием. "
                    + classification.factual_essence,
                    job_id,
                )
                continue
            set_job(
                job_id,
                "running",
                {"stage": "Сопоставляем с профилем компании", "published": published},
            )
            transition(
                record["news_id"],
                company_id,
                role,
                "sent",
                "relevance",
                "Сопоставляем с профилем компании",
                job_id,
            )
            relevance = agent.step_2_rank_relevance(company, news, classification)
            if relevance.relevance_score < 0.5:
                transition(
                    news.news_id,
                    company_id,
                    role,
                    "rejected",
                    "relevance",
                    f"Релевантность {relevance.relevance_score:.2f} ниже порога 0.50. "
                    + relevance.relevance_rationale,
                    job_id,
                )
                continue
            set_job(
                job_id,
                "running",
                {"stage": "Ищем и анализируем PDF-источники", "published": published},
            )
            transition(
                record["news_id"],
                company_id,
                role,
                "sent",
                "rag",
                "Ищем и анализируем PDF-источники",
                job_id,
            )
            bank = agent.step_3_rag_bank_context(news, classification, company)
            set_job(
                job_id,
                "running",
                {"stage": "Готовим персональный вывод", "published": published},
            )
            transition(
                record["news_id"],
                company_id,
                role,
                "sent",
                "generation",
                "Готовим персональный вывод",
                job_id,
            )
            insight = agent.step_4_deep_insight(company, news, bank, UserRole(role))
            set_job(
                job_id,
                "running",
                {"stage": "Проверяем обоснованность вывода", "published": published},
            )
            transition(
                record["news_id"],
                company_id,
                role,
                "sent",
                "audit",
                "Проверяем обоснованность вывода",
                job_id,
            )
            audit = agent.step_5_fact_check_and_audit(company, news, bank, insight)
            cid = (
                "card-"
                + company_id
                + "-"
                + hashlib.sha256(
                    (
                        news.news_id + "|" + role + "|" + version + "|" + revision
                    ).encode()
                ).hexdigest()[:20]
            )
            sources = [
                {
                    "type": "NEWS",
                    "name": news.source_name,
                    "url_or_file": news.source_url,
                }
            ]
            sources += [
                {
                    "type": "ALFA_RESEARCH",
                    "name": x["filename"],
                    "url_or_file": x["filename"],
                    "page": x["page"],
                }
                for x in bank.sources
            ]
            q = {
                "q1_what_happened": {
                    "question": "Что произошло?",
                    "origin": "ФАКТ",
                    "text": insight.fact_summary,
                },
                "q2_why_matters": {
                    "question": "Почему это важно для этой компании?",
                    "origin": "ВЫВОД ИИ",
                    "text": insight.why_it_matters,
                },
                "q3_bank_evaluation": {
                    "question": "Как это оценивает банк?",
                    "origin": "ПОЗИЦИЯ БАНКА" if bank.is_official_view else "ВЫВОД ИИ",
                    "has_report": bank.has_bank_report,
                    "report_title": bank.source_report_title,
                    "source_file": bank.sources[0]["filename"]
                    if bank.sources
                    else None,
                    "text": bank.position_text,
                },
                "q4_consequences": {
                    "question": "Какие последствия возможны?",
                    "origin": "ВЫВОД ИИ",
                    "risks": insight.risks,
                    "opportunities": insight.opportunities,
                },
                "q5_recommended_actions": {
                    "question": "Какие действия могут быть релевантны?",
                    "origin": "ВЫВОД ИИ",
                    **insight.next_best_action.model_dump(),
                    "button_text": "Обсудить с менеджером",
                },
                "q6_basis_of_conclusion": {
                    "question": "На чем основан вывод?",
                    "origin": "ИСТОЧНИКИ",
                    "sources": sources,
                    "client_signals_used": _features(context)["influencing_signals"],
                },
            }
            event = {
                "card_id": cid,
                "news_id": news.news_id,
                "published_at": news.published_at,
                "title": news.title,
                "relevance": {
                    "score": relevance.relevance_score,
                    "is_critical": relevance.is_critical,
                    "rationale": relevance.relevance_rationale,
                    "affected_areas": relevance.affected_factors or ["бизнес"],
                },
                "client_features": _features(context),
                "six_questions": q,
                "disclaimer": insight.disclaimer,
                "audit": audit.model_dump(),
                "generation_mode": "live",
            }
            event["news_version"] = revision
            event["audit_status"] = (
                "verified"
                if audit.is_valid and not audit.hallucination_detected
                else "rejected"
            )
            if not audit.is_valid or audit.hallucination_detected:
                repo.save_insight(company_id, role, event, version, status="rejected")
                transition(
                    news.news_id,
                    company_id,
                    role,
                    "rejected",
                    "audit",
                    "Аудит отклонил вывод: " + audit.notes,
                    job_id,
                )
                failures.append(
                    {
                        "news_id": news.news_id,
                        "reason": "audit_rejected",
                        "notes": audit.notes,
                    }
                )
                continue
            event["analysis_status"] = (
                "degraded" if bank.synthesis_status == "extracts_only" else "verified"
            )
            repo.save_insight(
                company_id, role, event, version, status=event["analysis_status"]
            )
            transition(
                news.news_id,
                company_id,
                role,
                "published",
                "published",
                "Анализ завершён, аудит пройден, карточка сохранена.",
                job_id,
                cid,
            )
            published += 1
        except Exception as error:
            transition(
                record["news_id"],
                company_id,
                role,
                "error",
                "error",
                "Ошибка обработки: "
                + type(error).__name__
                + ". Подробности запроса скрыты, чтобы не раскрывать ключи.",
                job_id,
            )
            failures.append(
                {"news_id": record["news_id"], "reason": type(error).__name__}
            )
    set_job(
        job_id,
        "completed" if published else "failed",
        {"published": published, "failures": failures},
    )
