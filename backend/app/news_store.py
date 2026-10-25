"""Atomic persistent RSS snapshot; separate from company-specific insights."""
import json
import os
from pathlib import Path
from .news_ingestion import NewsRecord

PATH = Path(os.getenv('NEWS_CACHE_PATH', '/app/storage/news.json' if Path('/app/storage').exists() else 'backend/data/news.json'))

def save_news(records, status):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = PATH.with_suffix('.tmp')
    temporary.write_text(json.dumps({'items':[r.model_dump(mode='json') for r in records], 'sources':status},ensure_ascii=False))
    os.replace(temporary,PATH)

def load_news():
    if not PATH.exists(): return [], {'loaded':[], 'failed':[], 'counts':{}}
    try:
        data=json.loads(PATH.read_text())
        return [NewsRecord.model_validate(x) for x in data['items']],data['sources']
    except (ValueError,KeyError):
        return [], {'loaded':[], 'failed':[{'error':'Invalid persistent cache'}], 'counts':{}}
