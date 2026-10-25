"""Content fingerprints invalidate results when any dependency changes."""

import hashlib, json, os
from pathlib import Path
from agent.models_cfg import TASK_MODEL_MAPPING


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


def prompt_version():
    root = Path(__file__).resolve().parents[2] / "agent/prompts"
    return digest(
        {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.glob("*.py"))
        }
    )


def corpus_version():
    from .storage.db import transaction
    from .storage.models import Corpus
    from sqlalchemy import select

    with transaction() as s:
        row = s.scalar(select(Corpus).where(Corpus.active.is_(True)))
        if row:
            return row.id
    root = Path(os.getenv("PDF_DIR", "data_alfbnk"))
    from agent.rag.index_documents import EXTRACTOR_VERSION

    return digest(
        {
            "documents": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(root.glob("*.pdf"))
            },
            "dates": os.getenv("PDF_REPORT_DATES_JSON", "{}"),
            "extractor": EXTRACTOR_VERSION,
            "mode": os.getenv("RAG_MODE", "lexical"),
        }
    )


def analysis_version(company):
    from .company_context import get_company_context

    return digest(
        {
            "profile": get_company_context(company),
            "prompts": prompt_version(),
            "models": {
                k.value: v.model_dump(mode="json", exclude={"why"})
                for k, v in TASK_MODEL_MAPPING.items()
            },
            "corpus": corpus_version(),
            "pipeline": "2",
        }
    )
