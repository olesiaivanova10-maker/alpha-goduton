"""Persistent ingestion catalogue and per-company processing history."""
import json
from datetime import datetime, timezone
from .live_feed import connection

STATUSES = {'loaded', 'sent', 'rejected', 'published', 'error'}

def tables(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS journal_news(news_id TEXT PRIMARY KEY,title TEXT,source_name TEXT,source_url TEXT,published_at TEXT,loaded_at TEXT);
    CREATE TABLE IF NOT EXISTS journal_state(news_id TEXT,company_id TEXT,role TEXT,status TEXT,stage TEXT,reason TEXT,job_id TEXT,card_id TEXT,updated_at TEXT,PRIMARY KEY(news_id,company_id,role));
    CREATE TABLE IF NOT EXISTS journal_history(id INTEGER PRIMARY KEY AUTOINCREMENT,news_id TEXT,company_id TEXT,role TEXT,status TEXT,stage TEXT,reason TEXT,job_id TEXT,card_id TEXT,created_at TEXT);
    CREATE INDEX IF NOT EXISTS journal_history_news ON journal_history(news_id,company_id,role,id);
    ''')

def register(records):
    now=datetime.now(timezone.utc).isoformat()
    with connection() as db:
        tables(db)
        for record in records:
            r=record.model_dump(mode='json') if hasattr(record,'model_dump') else record
            db.execute('INSERT OR IGNORE INTO journal_news VALUES(?,?,?,?,?,?)',(r['news_id'],r['title'],r.get('source_name',''),r.get('source_url',''),r.get('published_at'),now))

def transition(news_id, company_id, role, status, stage, reason, job_id=None, card_id=None):
    if status not in STATUSES: raise ValueError('Unknown journal status')
    now=datetime.now(timezone.utc).isoformat()
    values=(news_id,company_id,role,status,stage,reason,job_id,card_id,now)
    with connection() as db:
        tables(db)
        db.execute('INSERT OR REPLACE INTO journal_state VALUES(?,?,?,?,?,?,?,?,?)',values)
        db.execute('INSERT INTO journal_history(news_id,company_id,role,status,stage,reason,job_id,card_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)',values)

def bootstrap(records):
    register(records)
    with connection() as db:
        rows=db.execute('SELECT company_id,role,event FROM insights').fetchall()
    for company,role,raw in rows:
        event=json.loads(raw)
        register([{'news_id':event['news_id'],'title':event['title'],'published_at':event.get('published_at')}])
        with connection() as db:
            exists=db.execute('SELECT 1 FROM journal_state WHERE news_id=? AND company_id=? AND role=?',(event['news_id'],company,role)).fetchone()
        if not exists:
            transition(event['news_id'],company,role,'published','migration','Ранее опубликованная карточка. История этапов до включения журнала не записывалась.',card_id=event['card_id'])
    # BackgroundTasks do not survive a process restart. Do not leave misleading running statuses.
    with connection() as db:
        rows=db.execute("SELECT news_id,company_id,role,job_id FROM journal_state WHERE status='sent'").fetchall()
    for news_id,company,role,job_id in rows:
        transition(news_id,company,role,'error','interrupted','Обработка прервана перезапуском сервиса. Требуется повторный запуск.',job_id)

def listing(company_id,role,status=None,search='',limit=50,offset=0):
    with connection() as db:
        tables(db)
        db.row_factory=__import__('sqlite3').Row
        join=' FROM journal_news n LEFT JOIN journal_state s ON n.news_id=s.news_id AND s.company_id=? AND s.role=? '
        params=[company_id,role]
        where=' WHERE 1=1 '
        if search:
            where+=' AND (n.title LIKE ? OR n.news_id LIKE ?) ';params.extend(['%'+search+'%']*2)
        summary={r['status']:r['count'] for r in db.execute("SELECT COALESCE(s.status,'loaded') AS status,COUNT(*) AS count"+join+where+' GROUP BY 1',params)}
        if status:
            where+=" AND COALESCE(s.status,'loaded')=? ";params.append(status)
        total=db.execute('SELECT COUNT(*)'+join+where,params).fetchone()[0]
        rows=db.execute("SELECT n.*,COALESCE(s.status,'loaded') AS status,COALESCE(s.stage,'ingestion') AS stage,COALESCE(s.reason,'Загружена из RSS; для выбранной компании ещё не отправлялась модели.') AS reason,s.job_id,s.card_id,COALESCE(s.updated_at,n.loaded_at) AS updated_at"+join+where+' ORDER BY updated_at DESC,n.news_id LIMIT ? OFFSET ?',params+[limit,offset]).fetchall()
        return {'company_id':company_id,'role':role,'summary':summary,'total':total,'limit':limit,'offset':offset,'items':[dict(r) for r in rows]}

def history(news_id,company_id,role):
    with connection() as db:
        tables(db);db.row_factory=__import__('sqlite3').Row
        return [dict(r) for r in db.execute('SELECT * FROM journal_history WHERE news_id=? AND company_id=? AND role=? ORDER BY id',(news_id,company_id,role))]
