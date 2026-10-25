"""Company-specific persisted insights; explicit background generation."""
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from agent.schemas import NewsItem, UserRole


@contextmanager
def connection():
    path=Path(os.getenv('INSIGHT_DB_PATH','/app/storage/insights.db' if Path('/app/storage').exists() else 'backend/data/insights.db'))
    path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path)
    db.execute('CREATE TABLE IF NOT EXISTS insights(card_id TEXT PRIMARY KEY,company_id TEXT,role TEXT,event TEXT,created_at TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS jobs(job_id TEXT PRIMARY KEY,status TEXT,detail TEXT)')
    db.commit()
    try:
        yield db
        db.commit()
    finally:
        db.close()


def events(company_id,role):
    with connection() as db:
        rows=db.execute('SELECT event FROM insights WHERE company_id=? AND role=? ORDER BY created_at DESC',(company_id,role)).fetchall()
    return sorted([json.loads(r[0]) for r in rows],key=lambda e:e['relevance']['score'],reverse=True)


def card(card_id):
    with connection() as db: row=db.execute('SELECT event FROM insights WHERE card_id=?',(card_id,)).fetchone()
    return json.loads(row[0]) if row else None


def job(job_id):
    with connection() as db: row=db.execute('SELECT status,detail FROM jobs WHERE job_id=?',(job_id,)).fetchone()
    return {'job_id':job_id,'status':row[0],'detail':json.loads(row[1])} if row else None


def set_job(job_id,status,detail):
    with connection() as db: db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?,?)',(job_id,status,json.dumps(detail,ensure_ascii=False)))


def generate(job_id,company_id,role,records,service):
    from .company_context import get_company_context
    from .feed import _features
    set_job(job_id,'running',{'processed':0})
    context=get_company_context(company_id)
    profile=service.profile(company_id)
    from agent.adapter import adapt_backend_context_to_profile
    company=adapt_backend_context_to_profile(profile)
    from .news_journal import register, transition
    register(records)
    published=0; failures=[]
    for record in records:
        try:
            expected_id='card-'+company_id+'-'+hashlib.sha256((record['news_id']+'|'+role).encode()).hexdigest()[:20]
            if card(expected_id):
                transition(record['news_id'],company_id,role,'published','deduplicated','Карточка уже опубликована; повторного вызова модели не было.',job_id,expected_id)
                published+=1
                continue
            news=NewsItem(news_id=record['news_id'],title=record['title'],body=record['body'],source_name=record['source_name'],source_url=record['source_url'],published_at=record.get('published_at'))
            agent=service.orchestrator
            set_job(job_id,'running',{'stage':'Проверяем деловую значимость новости','published':published})
            transition(record['news_id'],company_id,role,'sent','classify','Проверяем деловую значимость новости',job_id)
            classification=agent.step_1_classify(news)
            if not classification.is_relevant_business_event:
                transition(news.news_id,company_id,role,'rejected','classify','Модель не признала новость значимым деловым событием. '+classification.factual_essence,job_id)
                continue
            set_job(job_id,'running',{'stage':'Сопоставляем с профилем компании','published':published})
            transition(record['news_id'],company_id,role,'sent','relevance','Сопоставляем с профилем компании',job_id)
            relevance=agent.step_2_rank_relevance(company,news,classification)
            if relevance.relevance_score<.5:
                transition(news.news_id,company_id,role,'rejected','relevance',f'Релевантность {relevance.relevance_score:.2f} ниже порога 0.50. '+relevance.relevance_rationale,job_id)
                continue
            set_job(job_id,'running',{'stage':'Ищем и анализируем PDF-источники','published':published})
            transition(record['news_id'],company_id,role,'sent','rag','Ищем и анализируем PDF-источники',job_id)
            bank=agent.step_3_rag_bank_context(news,classification,company)
            set_job(job_id,'running',{'stage':'Готовим персональный вывод','published':published})
            transition(record['news_id'],company_id,role,'sent','generation','Готовим персональный вывод',job_id)
            insight=agent.step_4_deep_insight(company,news,bank,UserRole(role))
            set_job(job_id,'running',{'stage':'Проверяем обоснованность вывода','published':published})
            transition(record['news_id'],company_id,role,'sent','audit','Проверяем обоснованность вывода',job_id)
            audit=agent.step_5_fact_check_and_audit(company,news,bank,insight)
            if not audit.is_valid or audit.hallucination_detected:
                transition(news.news_id,company_id,role,'rejected','audit','Аудит отклонил вывод: '+audit.notes,job_id)
                failures.append({'news_id':news.news_id,'reason':'audit_rejected','notes':audit.notes});continue
            cid='card-'+company_id+'-'+hashlib.sha256((news.news_id+'|'+role).encode()).hexdigest()[:20]
            sources=[{'type':'NEWS','name':news.source_name,'url_or_file':news.source_url}]
            sources += [{'type':'ALFA_RESEARCH','name':x['filename'],'url_or_file':x['filename'],'page':x['page']} for x in bank.sources]
            q={
                'q1_what_happened':{'question':'Что произошло?','origin':'ФАКТ','text':insight.fact_summary},
                'q2_why_matters':{'question':'Почему это важно для этой компании?','origin':'ВЫВОД ИИ','text':insight.why_it_matters},
                'q3_bank_evaluation':{'question':'Как это оценивает банк?','origin':'ПОЗИЦИЯ БАНКА' if bank.is_official_view else 'ВЫВОД ИИ','has_report':bank.has_bank_report,'report_title':bank.source_report_title,'source_file':bank.sources[0]['filename'] if bank.sources else None,'text':bank.position_text},
                'q4_consequences':{'question':'Какие последствия возможны?','origin':'ВЫВОД ИИ','risks':insight.risks,'opportunities':insight.opportunities},
                'q5_recommended_actions':{'question':'Какие действия могут быть релевантны?','origin':'ВЫВОД ИИ',**insight.next_best_action.model_dump(),'button_text':'Обсудить с менеджером'},
                'q6_basis_of_conclusion':{'question':'На чем основан вывод?','origin':'ИСТОЧНИКИ','sources':sources,'client_signals_used':_features(context)['influencing_signals']}}
            event={'card_id':cid,'news_id':news.news_id,'published_at':news.published_at,'title':news.title,'relevance':{'score':relevance.relevance_score,'is_critical':relevance.is_critical,'rationale':relevance.relevance_rationale,'affected_areas':relevance.affected_factors or ['бизнес']},'client_features':_features(context),'six_questions':q,'disclaimer':insight.disclaimer,'audit':audit.model_dump(),'generation_mode':'live'}
            with connection() as db: db.execute('INSERT OR REPLACE INTO insights VALUES(?,?,?,?,?)',(cid,company_id,role,json.dumps(event,ensure_ascii=False),datetime.now(timezone.utc).isoformat()))
            transition(news.news_id,company_id,role,'published','published','Анализ завершён, аудит пройден, карточка сохранена.',job_id,cid)
            published+=1
        except Exception as error:
            transition(record['news_id'],company_id,role,'error','error','Ошибка обработки: '+type(error).__name__+'. Подробности запроса скрыты, чтобы не раскрывать ключи.',job_id)
            failures.append({'news_id':record['news_id'],'reason':type(error).__name__})
    set_job(job_id,'completed' if published else 'failed',{'published':published,'failures':failures})
