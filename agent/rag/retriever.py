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
    profile=" ".join(str(v) for v in (company or {}).values()).lower()
    words=set(re.findall(r"[а-яa-z0-9]{4,}", f"{query} {profile}".lower())); ranked=[]
    for chunk in _INDEX:
        if filenames is not None and chunk.filename not in filenames:
            continue
        if chunk.confidence<.65:continue
        if chunk.report_date and chunk.report_date>date.today().isoformat():continue
        tokens=set(re.findall(r"[а-яa-z0-9]{4,}", chunk.text.lower())); overlap=len(words & tokens); score=overlap/max(len(words),1)
        if score>=float(os.getenv("RAG_LEXICAL_THRESHOLD","0.1")): ranked.append((score,chunk))
    ranked.sort(key=lambda item:item[0], reverse=True)
    return [replace(chunk,score=round(score,4)) for score,chunk in ranked[:top_k]]
