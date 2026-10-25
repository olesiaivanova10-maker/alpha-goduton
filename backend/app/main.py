import sys
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Обеспечиваем доступ к agent и app
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from .company_context import get_company_context
from .data_loader import DATA
from .news_ingestion import collect_sources, sort_news, NewsRecord
from .model_health import check_models
from .agent_service import AgentService
from .news_parser import normalize_news
from .feedback import add_feedback, feedback_metrics
from .schemas import CompanyContext, NewsFeedResponse, ChatRequest as FeedChatRequest, ChatResponse as FeedChatResponse
from .feed import build_feed, find_card
from agent.adapter import adapt_backend_context_to_profile
from agent.schemas import UserRole, NewsItem, PersonalizedInsight, ValidationReport
from agent.orchestrator import AgentOrchestrator
from agent.bank_knowledge_base import ALFA_REPORTS_INDEX
from agent.prompts.qwen_chat import build_chat_prompt
from agent.models_cfg import config, PipelineTask

app = FastAPI(
    title="Альфа Хак — API Новостной аналитики и Агента",
    version="1.0.0",
    description="Сервис персонализированных бизнес-инсайтов для руководителей крупного бизнеса."
)

# Настройка CORS для работы с фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = AgentOrchestrator()
agent_service = AgentService(orchestrator)
NEWS_CACHE: list[NewsRecord] = []
NEWS_STATUS: dict = {"loaded": [], "failed": [], "counts": {}}


class AnalyzeRequest(BaseModel):
    company_id: str
    news_title: str
    news_body: str
    news_id: Optional[str] = "news-01"
    source_name: Optional[str] = "СМИ"
    role: Optional[UserRole] = UserRole.CFO


class AnalyzeResponse(BaseModel):
    insight: Optional[PersonalizedInsight]
    audit: Optional[ValidationReport]
    filtered_out: bool = False
    message: str = "Анализ завершен успешно"


class ChatRequest(BaseModel):
    company_id: str
    news_title: str
    insight_summary: str
    user_message: str
    user_role: Optional[UserRole] = UserRole.CFO
    chat_history: Optional[str] = ""


class ChatResponse(BaseModel):
    reply: str


class FeedbackRequest(BaseModel):
    insight_id: str
    company_id: str
    rating: int
    comment: Optional[str] = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "live_llm_api": orchestrator.has_live_api,
        "models_configured": [task.value for task in PipelineTask],
        "data_mode": "synthetic" if any(w.startswith("DEMO_FALLBACK") for w in DATA.warnings) else "csv",
        "data_warnings": list(DATA.warnings),
        "news_cache_size": len(NEWS_CACHE),
    }

@app.get("/health/models")
def models_health(force: bool = False):
    return check_models(force=force)


@app.post("/api/feedback")
def submit_feedback(req: FeedbackRequest):
    try:
        return add_feedback(req.insight_id, req.company_id, req.rating, req.comment)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/feedback/metrics")
def get_feedback_metrics():
    return feedback_metrics()


@app.get("/feed", response_model=NewsFeedResponse)
@app.get("/api/feed", response_model=NewsFeedResponse)
def news_feed(company_id: str, role: UserRole = UserRole.CFO):
    try:
        return build_feed(company_id, role.value)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/chat", response_model=FeedChatResponse)
def feed_chat(req: FeedChatRequest):
    card = find_card(req.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Карточка не найдена")
    if not req.question.strip():
        raise HTTPException(status_code=422, detail="question не должен быть пустым")
    return FeedChatResponse(
        answer=f"По материалу «{card['title']}»: {card['summary']} Ваш вопрос: {req.question}",
        origin="ВЫВОД ИИ",
        sources=[{"type":"ALFA_RESEARCH","name":card["title"],"url_or_file":card["source"]}],
    )


@app.post("/feedback")
def submit_feedback_short(req: FeedbackRequest):
    return submit_feedback(req)


@app.get("/api/companies/{company_id}/context", response_model=CompanyContext)
@app.get("/companies/{company_id}/context", response_model=CompanyContext)
def company_context(company_id: str):
    """Возвращает сырой профиль компании из датасета банка."""
    try:
        return get_company_context(company_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/insights/analyze", response_model=AnalyzeResponse)
def analyze_news_for_company(req: AnalyzeRequest):
    """
    Основной агентный эндпоинт:
    1. Получает контекст компании
    2. Запускает агентный пайплайн (Gemma 4 -> Qwen 3.6 -> DeepSeek-V4.1 -> GLM-5.3)
    3. Возвращает готовый инсайт и отчет факт-чекинга для фронтенда
    """
    try:
        normalized = normalize_news({
            "news_id": req.news_id,
            "title": req.news_title,
            "body": req.news_body,
            "source_name": req.source_name,
        })
        agent_service.profile(req.company_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Компания {req.company_id} не найдена: {e}")

    news_item = NewsItem(**normalized)

    result = agent_service.analyze(req.company_id, news_item, req.role or UserRole.CFO)

    if result is None:
        return AnalyzeResponse(
            insight=None,
            audit=None,
            filtered_out=True,
            message="Новость отсеяна как нерелевантная для профиля данной компании."
        )

    insight, audit = result
    return AnalyzeResponse(
        insight=insight,
        audit=audit,
        filtered_out=False,
        message="Персонализированный инсайт успешно сформирован."
    )


@app.post("/api/chat", response_model=ChatResponse)
def interactive_qa_chat(req: ChatRequest):
    """Интерактивный диалог с Qwen 3.6 по карточке инсайта."""
    try:
        raw_ctx = get_company_context(req.company_id)
        comp_profile = adapt_backend_context_to_profile(raw_ctx)
        company_summary = f"{comp_profile.display_name}, ОКВЭД: {comp_profile.mainokved_name}, Выручка: {comp_profile.revenue_company/1e9:.1f} млрд ₽"
    except Exception:
        company_summary = f"Компания ID: {req.company_id}"

    prompt = build_chat_prompt(
        company_name=company_summary,
        user_role=req.user_role.value if req.user_role else "CFO",
        news_title=req.news_title,
        insight_summary=req.insight_summary,
        company_summary=company_summary,
        chat_history=req.chat_history or "",
        user_message=req.user_message
    )

    reply_text = orchestrator._call_llm(
        PipelineTask.INTERACTIVE_CHAT,
        system_prompt=prompt["system"],
        user_prompt=prompt["user"]
    )

    if not reply_text or reply_text == "{}":
        reply_text = (
            f"Учитывая профиль вашей компании ({company_summary}), изменение рыночных условий "
            f"в первую очередь отразится на графике финансирования оборотного капитала. "
            f"Рекомендуем обратиться к персональному менеджеру для детального расчета ковенантов."
        )

    return ChatResponse(reply=reply_text)


@app.get("/api/reports")
def list_alfa_reports():
    """Возвращает список 9 индексированных отчетов Центра макроисследований Альфа-Банка."""
    return [
        {
            "chunk_id": rep.chunk_id,
            "title": rep.report_title,
            "filename": rep.source_filename,
            "target_sectors": rep.target_sectors,
            "macro_topics": rep.macro_topics,
            "summary": rep.summary,
            "official_recommendation": rep.official_recommendation
        }
        for rep in ALFA_REPORTS_INDEX
    ]


@app.get("/api/news")
def get_news(company_id: str | None = None, limit: int = 20):
    context = None
    if company_id:
        try: context = get_company_context(company_id)
        except ValueError as error: raise HTTPException(status_code=404, detail=str(error)) from error
    return {"generated_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(), "sources": NEWS_STATUS, "items": sort_news(NEWS_CACHE, context, max(1, min(limit, 100)))}


@app.post("/api/news/refresh")
def refresh_news():
    global NEWS_CACHE, NEWS_STATUS
    NEWS_CACHE, NEWS_STATUS = collect_sources()
    return {"status": "ok", "items_count": len(NEWS_CACHE), "sources": NEWS_STATUS}
