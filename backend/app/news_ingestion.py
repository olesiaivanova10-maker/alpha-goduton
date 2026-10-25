"""Free RSS ingestion, normalization, deduplication and profile-aware ranking."""
from __future__ import annotations
import hashlib, html, logging, re, time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Literal
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)
SOURCE_RELIABILITY = {"ТАСС": .90, "РИА Новости": .90, "Интерфакс": .92, "Коммерсантъ": .88, "Банк России": 1.00}
SOURCES = {"ТАСС": "https://tass.ru/rss/v2.xml", "РИА Новости": "https://ria.ru/export/rss2/archive/index.xml", "Интерфакс": "https://www.interfax.ru/rss.asp", "Коммерсантъ": "https://www.kommersant.ru/RSS/news.xml", "Банк России": "https://www.cbr.ru/rss/RssNews"}
TOPICS = ("ставк", "кредит", "курс", "инфляц", "санкц", "экспорт", "импорт", "логист", "налог", "банкрот", "регулир", "сырь", "производств")

class NewsRecord(BaseModel):
    news_id: str; title: str; body: str; summary: str | None = None; published_at: datetime | None = None; source_name: str; source_url: str; source_type: Literal["rss", "api"] = "rss"; source_reliability: float; language: str = "ru"; categories: list[str] = Field(default_factory=list); tags: list[str] = Field(default_factory=list); entities: list[str] = Field(default_factory=list); content_hash: str; collected_at: datetime; duplicate_sources: list[dict[str, str]] = Field(default_factory=list)

def _clean(value: str | None) -> str: return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(value or ""))).strip()
def _date(value: str | None) -> datetime | None:
    if not value: return None
    try: return parsedate_to_datetime(value).astimezone(timezone.utc)
    except Exception:
        try: return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception: return None

def parse_rss(xml: bytes, source_name: str, collected_at: datetime | None = None) -> list[NewsRecord]:
    collected_at=collected_at or datetime.now(timezone.utc); root=ET.fromstring(xml); records=[]
    for node in list(root.findall(".//item")) or list(root.findall(".//{*}entry")):
        def val(*names):
            for name in names:
                child=node.find(name)
                if child is None: child=node.find(f"{{*}}{name}")
                if child is not None and (child.text or child.get("href")): return child.text or child.get("href")
            return ""
        title=_clean(val("title")); url=_clean(val("link", "guid")); body=_clean(val("description", "summary", "content")); published=_date(val("pubDate", "published", "updated")); guid=_clean(val("guid"))
        if not title or not url: continue
        raw=f"{title.lower()}|{body.lower()}"; content_hash=hashlib.sha256(raw.encode()).hexdigest(); news_id=guid or hashlib.sha256(f"{url}|{title}|{published}".encode()).hexdigest()[:20]; tags=[topic for topic in TOPICS if topic in raw]
        records.append(NewsRecord(news_id=news_id,title=title,body=body,summary=body[:500] or None,published_at=published,source_name=source_name,source_url=url,source_reliability=SOURCE_RELIABILITY.get(source_name,.5),tags=tags,content_hash=content_hash,collected_at=collected_at))
    return records

def deduplicate_news(news: list[NewsRecord]) -> list[NewsRecord]:
    result=[]; by_key={}
    for item in news:
        key=item.content_hash or item.source_url.lower().rstrip('/')
        if key not in by_key: by_key[key]=item; result.append(item); continue
        existing=by_key[key]; duplicate={"source_name":item.source_name,"source_url":item.source_url}
        if item.source_reliability > existing.source_reliability:
            item.duplicate_sources=existing.duplicate_sources + [{"source_name":existing.source_name,"source_url":existing.source_url}]; by_key[key]=item; result[result.index(existing)]=item
        else: existing.duplicate_sources.append(duplicate)
    return result

def sort_news(news: list[NewsRecord], company_context: dict | None = None, limit: int = 50) -> list[dict[str, Any]]:
    now=datetime.now(timezone.utc); industry=((company_context or {}).get("industry") or {}); haystack=" ".join(str(v) for v in (company_context or {}).values()).lower(); scored=[]
    for item in news:
        age=max((now-(item.published_at or item.collected_at).astimezone(timezone.utc)).total_seconds(),0); freshness=max(0,1-age/(7*86400)); topic=min(len(item.tags)/3,1); profile=1.0 if industry.get("name") and any(w in (industry.get("name") or '').lower() for w in item.title.lower().split() if len(w)>4) else (0.5 if haystack and any(t in haystack for t in item.tags) else 0); score=round(.35*freshness+.25*item.source_reliability+.25*profile+.15*topic,4); signals=[]
        if profile: signals.append("профиль компании")
        if item.tags: signals.extend(item.tags[:3])
        scored.append((score,{**item.model_dump(mode="json"),"relevance":{"score":score,"freshness_score":round(freshness,4),"source_score":item.source_reliability,"profile_match_score":profile,"matched_signals":signals,"reason":"; ".join(signals) or "свежесть и качество источника"}}))
    return [item for _,item in sorted(scored,key=lambda x:x[0],reverse=True)[:limit]]

def collect_sources(source_map: dict[str,str] | None = None, timeout: int = 8, retries: int = 2) -> tuple[list[NewsRecord], dict[str,Any]]:
    loaded=[]; failed=[]; counts={}; all_news=[]; source_map=source_map or SOURCES
    for name,url in source_map.items():
        last=""
        for attempt in range(retries+1):
            try:
                data=urlopen(Request(url,headers={"User-Agent":"alpha-hack-news/1.0"}),timeout=timeout).read(5_000_000); records=parse_rss(data,name); all_news.extend(records); loaded.append(name); counts[name]=len(records); break
            except (HTTPError, URLError, TimeoutError, ET.ParseError, ValueError) as error:
                last=str(error); log.warning("news source %s failed: %s",name,error); time.sleep(.2*(2**attempt))
        else: failed.append({"source":name,"url":url,"error":last})
    return deduplicate_news(all_news), {"loaded":loaded,"failed":failed,"counts":counts}
