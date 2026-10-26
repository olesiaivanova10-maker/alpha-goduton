"""Local PDF RAG fallback: page extraction + lexical hybrid retrieval.

The module keeps the same interface that a Qdrant/BGE implementation can later replace.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib, re, json, os, logging
from datetime import date
from dataclasses import replace
from pypdf import PdfReader

@dataclass
class RagChunk:
    chunk_id: str
    filename: str
    page: int
    text: str
    score: float = 0.0
    extraction_method: str = "text"
    report_date: str | None = None
    checksum: str = ""
    confidence: float = 1.0

_INDEX: list[RagChunk] = []
_INDEXED = False

def index_pdf_directory(directory: str | Path = "data_alfbnk") -> list[RagChunk]:
    global _INDEX, _INDEXED
    chunks=[]; root=Path(directory)
    report_dates=json.loads(os.getenv("PDF_REPORT_DATES_JSON","{}"))
    for path in sorted(root.glob("*.pdf")):
        try:
            checksum=hashlib.sha256(path.read_bytes()).hexdigest()
            cache=path.with_suffix('.pages.json')
            if cache.exists() and json.loads(cache.read_text()).get('checksum') == checksum:
                pages=json.loads(cache.read_text())['pages']
            else:
                pages=[{'page':number,'text':page.extract_text() or '', 'extraction_method':'text'} for number,page in enumerate(PdfReader(str(path)).pages,1)]
            for page in pages:
                number=page['page']
                text=page['text'].strip()
                if not text: continue
                for part_no in range(0,len(text),1800):
                    part=" ".join(text[part_no:part_no+1800].split())
                    if not part: continue
                    digest=hashlib.sha1(f"{checksum}:{path.name}:{number}:{part_no}:{part}:v2".encode()).hexdigest()[:16]
                    chunks.append(RagChunk(f"{path.stem}-{number}-{digest}",path.name,number,part,extraction_method=page.get("extraction_method", "text"),report_date=report_dates.get(path.name),checksum=checksum,confidence=page.get("confidence",.75 if page.get("extraction_method")=="ocr" else 1.)))
        except Exception as error:
            logging.getLogger(__name__).warning("PDF extraction failed: %s (%s)",path.name,type(error).__name__)
            continue
    _INDEX=chunks; _INDEXED=True; return chunks

def retrieve_bank_context(query: str, company: dict | None = None, top_k: int = 8, filenames: list[str] | None = None) -> list[RagChunk]:
    if os.getenv('RAG_MODE','lexical')=='hybrid':
        from backend.app.rag_service import retrieve
        fields=RagChunk.__dataclass_fields__
        profile=' '.join(str(v) for v in (company or {}).values())
        return [RagChunk(**{k:v for k,v in c.items() if k in fields}) for c in retrieve(query+' '+profile,filenames=filenames,top_k=top_k)]
    if not _INDEXED: index_pdf_directory(os.getenv('PDF_DIR','data_alfbnk'))
    # Public research cannot establish an individual customer's private contracts.
    if private_company_question(query):
        return []
    words = tokens(query)
    if not words:
        return []
    eligible = [c for c in _INDEX if (filenames is None or c.filename in filenames)
                and c.confidence >= .65 and (not c.report_date or c.report_date <= date.today().isoformat())]
    if not eligible:
        return []
    from collections import Counter
    import math
    documents = [tokens(c.text) for c in eligible]
    df = Counter(t for doc in documents for t in set(doc))
    average = sum(map(len, documents)) / len(documents) or 1
    ranked = []
    query_terms = set(words)
    for chunk, doc in zip(eligible, documents):
        counts = Counter(doc)
        matched = query_terms & counts.keys()
        # Company metadata may guide generation, but must not manufacture a retrieval match.
        if len(matched) < min(2, len(query_terms)):
            continue
        score = sum(math.log(1 + (len(documents)-df[t]+.5)/(df[t]+.5)) *
                    counts[t]*2.2/(counts[t]+1.2*(.25+.75*len(doc)/average)) for t in matched)
        coverage = len(matched)/len(query_terms)
        if coverage < float(os.getenv("RAG_LEXICAL_THRESHOLD", "0.15")):
            continue
        ranked.append((score * coverage, chunk))
    ranked.sort(key=lambda item: item[0], reverse=True)
    # Different fragments on one page should not crowd out other primary sources.
    seen = set(); result = []
    for score, chunk in ranked:
        key = (chunk.filename, chunk.page)
        if key not in seen:
            result.append(replace(chunk, score=round(score, 4))); seen.add(key)
        if len(result) >= top_k:
            break
    return result


_STOP = set("почему какой какая какие как что это при для после перед между или без над под про его уже было будет были этой этого этом компании компания аналитики аналитиков отчет отчёт году года год квартале квартала квартал ждать ожидают ждут изменился изменится прогноз роста размер индивидуальный график пожалуйста согласно показать расскажи подробнее".split())


def tokens(text):
    return _stems(tuple(w for w in re.findall(r"[а-яёa-z0-9]+", text.lower()) if len(w) >= 3 and w not in _STOP and not w.isdigit()))


from functools import lru_cache
@lru_cache(maxsize=8192)
def _stems(words):
    import snowballstemmer
    # Related noun/adjective forms that Snowball deliberately leaves separate.
    # This expands topic matching, never establishes a factual claim.
    aliases = {"потребительск": "потреблен", "инфляцион": "инфляц", "кредитован": "кредит"}
    return [aliases.get(t, t) for t in snowballstemmer.stemmer("russian").stemWords(list(words))]


def private_company_question(query):
    return bool(re.search(r"\bU_\w+", query, re.I) and re.search(r"задолженн|график.{0,30}платеж|остаток.{0,20}(долг|кредит)|ковенант|номер.{0,20}договор", query, re.I))
