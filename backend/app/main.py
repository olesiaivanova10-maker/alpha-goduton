import sys
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Обеспечиваем доступ к agent и app
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from .company_context import get_company_context
from .data_loader import DATA
from .news_ingestion import collect_sources, sort_news, NewsRecord
from .model_health import check_models
from .news_store import load_news, save_news
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
    allow_origins=list(__import__(__package__+'.settings',fromlist=['settings']).settings().origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = AgentOrchestrator()
agent_service = AgentService(orchestrator)
from . import news_journal
from .security import install
install(app)


class AnalyzeRequest(BaseModel):
    company_id: str
    news_title: str = Field(min_length=1,max_length=1000)
    news_body: str = Field(min_length=1,max_length=30000)
    news_id: Optional[str] = Field(default=None,max_length=512)
    source_name: Optional[str] = Field(default="СМИ",max_length=256)
    role: Optional[UserRole] = UserRole.CFO


class AnalyzeResponse(BaseModel):
    insight: Optional[PersonalizedInsight]
    audit: Optional[ValidationReport]
    filtered_out: bool = False
    message: str = "Анализ завершен успешно"


class ChatRequest(BaseModel):
    company_id: str
    news_title: str = Field(min_length=1,max_length=1000)
    insight_summary: str
    user_message: str = Field(min_length=1,max_length=3000)
    user_role: Optional[UserRole] = UserRole.CFO
    chat_history: Optional[str] = ""


class ChatResponse(BaseModel):
    reply: str


class FeedbackRequest(BaseModel):
    insight_id: str
    company_id: str
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None,max_length=4000)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "live_llm_api": orchestrator.has_live_api,
        "models_configured": [task.value for task in PipelineTask],
        "data_mode": "synthetic" if any(w.startswith("DEMO_FALLBACK") for w in DATA.warnings) else "csv",
        "data_warnings": list(DATA.warnings),
        "news_cache_size": len(load_news()[0]),
    }

@app.get("/health/models")
def models_health(force: bool = False):
    if force:
        from fastapi.responses import JSONResponse
        return JSONResponse(_enqueue('probes',{}),status_code=202)
    from .model_health import cached_models
    return cached_models()


@app.post("/api/feedback")
def submit_feedback(req: FeedbackRequest):
    try:
        return add_feedback(req.insight_id, req.company_id, req.rating, req.comment)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/feedback/metrics")
def get_feedback_metrics():
    from .security import principal
    who=principal.get()
    return feedback_metrics(None if who and who['admin'] else (who or {}).get('companies',[]))


@app.get("/feed", response_model=NewsFeedResponse)
@app.get("/api/feed", response_model=NewsFeedResponse)
def news_feed(company_id: str, role: UserRole = UserRole.CFO, limit: int = 100, offset: int = 0):
    try:
        return build_feed(company_id, role.value,max(1,min(limit,100)),max(0,offset))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/feed/refresh",status_code=202)
def refresh_personal_feed(company_id: str, background: BackgroundTasks, role: UserRole = UserRole.CFO, limit: int = 2):
    from . import live_feed
    import uuid
    try: context = get_company_context(company_id)
    except ValueError: raise HTTPException(status_code=404,detail="Компания не найдена")
    if not orchestrator.has_live_api: raise HTTPException(status_code=503,detail="Live API не настроен")
    NEWS_CACHE,_=load_news()
    business=[n for n in NEWS_CACHE if __import__('re').search(r'\b(?:ставк|кредит|инфляц|нефт|топлив|лизинг|налог|экспорт|импорт|сырь|производств|логист|банкрот)',n.title.lower())]
    candidates=sort_news(business,context,max(1,min(limit,3)))
    if not candidates: raise HTTPException(status_code=409,detail="Сначала загрузите новости")
    return _enqueue('analyze',{'company_id':company_id,'role':role.value,'records':candidates},company_id)

@app.get("/api/feed/jobs/{job_id}")
def feed_job(job_id: str):
    from .live_feed import job
    result=job(job_id)
    if not result: raise HTTPException(status_code=404,detail="Задача не найдена")
    return result

@app.post("/chat", response_model=FeedChatResponse)
def feed_chat(req: FeedChatRequest):
    if not req.question.strip():raise HTTPException(status_code=422,detail='Пустой вопрос')
    from .chat_service import answer
    try:return FeedChatResponse(**answer(orchestrator,req.card_id,req.question))
    except ValueError:raise HTTPException(status_code=404,detail='Карточка не найдена') from None


@app.post("/feedback")
def submit_feedback_short(req: FeedbackRequest):
    return submit_feedback(req)


@app.get("/api/companies/{company_id}/context", response_model=CompanyContext)
@app.get("/companies/{company_id}/context", response_model=CompanyContext)
def company_context(company_id: str):
    """Возвращает сырой профиль компании из датасета банка."""
    try:
        context=get_company_context(company_id)
        from .security import principal,allowed
        who=principal.get()
        if who and not who['admin']:
            context['group_companies']=[c for c in context['group_companies'] if allowed(c,who)]
            context['counterparties']=[c for c in context['counterparties'] if allowed(c['company_id'],who)]
        return context
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/insights/analyze",status_code=202)
def analyze_news_for_company(req: AnalyzeRequest):
    try:get_company_context(req.company_id)
    except ValueError:raise HTTPException(status_code=404,detail='Компания не найдена') from None
    if not orchestrator.has_live_api:raise HTTPException(status_code=503,detail='Live API не настроен')
    record={'news_id':'manual-'+__import__('hashlib').sha256((req.company_id+'|'+str(req.news_id)+'|'+req.news_title+'|'+req.news_body).encode()).hexdigest(),'title':req.news_title,'body':req.news_body,'source_name':req.source_name or 'Предоставленная новость','source_url':'','published_at':None}
    return _enqueue('analyze',{'company_id':req.company_id,'role':(req.role or UserRole.CFO).value,'records':[record]},req.company_id)


@app.post("/api/chat", response_model=ChatResponse)
def interactive_qa_chat(req: ChatRequest):
    from .storage.repositories import feed
    from .chat_service import answer
    # Compatibility contract: locate the exact stored title; ignore client-supplied summary/history.
    candidates=[e for e in feed(req.company_id,(req.user_role or UserRole.CFO).value) if e['title']==req.news_title]
    if len(candidates)!=1:raise HTTPException(status_code=404,detail='Сохранённая карточка не найдена однозначно')
    return ChatResponse(reply=answer(orchestrator,candidates[0]['card_id'],req.user_message)['answer'])


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
    NEWS_CACHE,NEWS_STATUS=load_news()
    context = None
    if company_id:
        try: context = get_company_context(company_id)
        except ValueError as error: raise HTTPException(status_code=404, detail=str(error)) from error
    return {"generated_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(), "sources": NEWS_STATUS, "items": sort_news(NEWS_CACHE, context, max(1, min(limit, 100)))}


@app.post("/api/news/refresh",status_code=202)
def refresh_news():return _enqueue('rss',{})

@app.post('/api/rag/index',status_code=202)
def index_rag():return _enqueue('index',{})

def _enqueue(kind,payload,company=None):
    from .jobs import enqueue
    try:return enqueue(kind,payload,company)
    except Exception:raise HTTPException(status_code=503,detail='Очередь заданий недоступна или переполнена') from None


@app.get("/api/reports/files/{filename}")
def report_file(filename: str):
    from fastapi.responses import FileResponse
    root=Path(__file__).resolve().parents[2]/'data_alfbnk'
    path=(root/filename).resolve()
    if path.parent != root.resolve() or path.suffix.lower() != '.pdf' or not path.is_file():
        raise HTTPException(status_code=404,detail="PDF не найден")
    return FileResponse(path,media_type='application/pdf')


@app.get("/api/developer", include_in_schema=False)
def developer_page():
    from fastapi.responses import FileResponse
    return FileResponse(Path(__file__).with_name('developer.html'),media_type='text/html')


@app.get("/api/developer/news")
def developer_news(company_id: str = 'U_14366', role: UserRole = UserRole.CFO, status: str | None = None, search: str = '', limit: int = 50, offset: int = 0):
    if status and status not in news_journal.STATUSES:
        raise HTTPException(status_code=422,detail='Неизвестный статус')
    return news_journal.listing(company_id,role.value,status,search[:200],max(1,min(limit,100)),max(0,offset))


@app.get("/api/developer/news-history")
def developer_news_history(news_id: str, company_id: str = 'U_14366', role: UserRole = UserRole.CFO):
    return {'items':news_journal.history(news_id,company_id,role.value)}


@app.get('/health/live')
def liveness():return {'status':'ok'}

@app.get('/health/ready')
def readiness():
    from .settings import settings
    from .storage.db import engine
    from sqlalchemy import text
    cfg=settings();checks={'csv':not any(w.startswith('DEMO_FALLBACK') for w in DATA.warnings)} if cfg.env=='prod' else {}
    try:
        with engine().connect() as c:c.execute(text('SELECT 1 FROM news LIMIT 1'))
        checks['database']=True
    except Exception:checks['database']=False
    if cfg.redis_url:
        try:
            from .jobs import redis
            checks['redis']=bool(redis().ping())
        except Exception:checks['redis']=False
    if cfg.qdrant_url:
        try:
            from qdrant_client import QdrantClient
            QdrantClient(url=cfg.qdrant_url,timeout=3).get_collections();checks['qdrant']=True
        except Exception:checks['qdrant']=False
    if __import__('os').getenv('RAG_MODE')=='hybrid':
        from .rag_service import active
        from pathlib import Path
        checks['model_artifacts']=Path(__import__('os').getenv('BGE_MODEL_PATH','/models/bge-m3')).is_dir() and Path(__import__('os').getenv('RERANKER_MODEL_PATH','/models/reranker')).is_dir()
        try:checks['active_corpus']=bool(active())
        except Exception:checks['active_corpus']=False
    from fastapi.responses import JSONResponse
    return JSONResponse({'status':'ok' if all(checks.values()) else 'unavailable','checks':checks},status_code=200 if all(checks.values()) else 503)


@app.get('/api/developer/usage')
def developer_usage():
    from .storage.db import transaction
    from .storage.models import ModelCall
    from sqlalchemy import select,func
    with transaction() as s:
        rows=s.execute(select(ModelCall.model_id,func.count(),func.sum(ModelCall.input_tokens),func.sum(ModelCall.output_tokens),func.sum(ModelCall.cost),func.count(ModelCall.cost)).group_by(ModelCall.model_id)).all()
    return {'items':[{'model_id':r[0],'calls':r[1],'input_tokens':r[2],'output_tokens':r[3],'estimated_cost_configured_units':r[4],'calls_with_pricing':r[5]} for r in rows],'note':'Стоимость неизвестна без MODEL_PRICES_JSON; это расчёт по настроенным тарифам, не банковская выписка провайдера.'}
