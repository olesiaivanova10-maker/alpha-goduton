"""Explicit versioned BGE/Qdrant index. Model files must be provisioned offline."""

import hashlib, json, os, re, uuid
from datetime import date
from pathlib import Path
from functools import lru_cache
from sqlalchemy import select, update
from .storage.db import transaction
from .storage.models import Corpus
from .versions import digest

EMBED_MODEL = "BAAI/bge-m3"
EMBED_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
DIMENSION = 1024
FORMAT = "pdf-pages1800-v2"


@lru_cache(maxsize=1)
def embedding():
    path = os.getenv("BGE_MODEL_PATH", "/models/bge-m3")
    if not Path(path).is_dir():
        raise RuntimeError("BGE artifact missing; run explicit model provisioning")
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(path, local_files_only=True, device="cpu")


@lru_cache(maxsize=1)
def reranker():
    path = os.getenv("RERANKER_MODEL_PATH", "/models/reranker")
    if not Path(path).is_dir():
        raise RuntimeError("Reranker artifact missing")
    from sentence_transformers import CrossEncoder

    return CrossEncoder(path, local_files_only=True, device="cpu")


def client():
    from qdrant_client import QdrantClient

    return QdrantClient(url=os.environ["QDRANT_URL"], timeout=15)


def build_corpus():
    from agent.rag.index_documents import index
    from agent.rag.retriever import index_pdf_directory
    from qdrant_client import models

    root = Path(os.getenv("PDF_DIR", "data_alfbnk"))
    index(root)
    chunks = index_pdf_directory(root)
    if not chunks:
        raise ValueError("No readable PDF chunks; active corpus unchanged")
    dates = json.loads(os.getenv("PDF_REPORT_DATES_JSON", "{}"))
    manifest = {
        "embedding": EMBED_MODEL,
        "revision": EMBED_REVISION,
        "dimension": DIMENSION,
        "format": FORMAT,
        "documents": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.glob("*.pdf"))
        },
    }
    artifact_manifest = Path(
        os.getenv("MODEL_ARTIFACT_MANIFEST", "/models/manifest.json")
    )
    if not artifact_manifest.exists():
        raise RuntimeError("Explicit model artifact manifest required")
    artifacts = json.loads(artifact_manifest.read_text())
    if artifacts.get("embedding_revision") != EMBED_REVISION:
        raise ValueError("Embedding revision mismatch")
    if not re.fullmatch("[0-9a-f]{40}", artifacts.get("reranker_revision", "")):
        raise ValueError("Immutable reranker revision required")
    manifest["artifacts"] = artifacts
    manifest["report_dates"] = dates
    from agent.rag.index_documents import EXTRACTOR_VERSION

    manifest["extractor"] = EXTRACTOR_VERSION
    manifest["chunk_digest"] = digest([c.__dict__ for c in chunks])
    version = digest(manifest)
    collection = "corpus_" + version[:24]
    q = client()
    if not q.collection_exists(collection):
        q.create_collection(
            collection,
            vectors_config=models.VectorParams(
                size=DIMENSION, distance=models.Distance.COSINE
            ),
        )
    entries = []
    for c in chunks:
        data = {
            **c.__dict__,
            "document_id": manifest["documents"][c.filename],
            "checksum": manifest["documents"][c.filename],
            "report_date": dates.get(c.filename),
            "confidence": 0.75 if c.extraction_method == "ocr" else 1.0,
            "corpus": version,
            "report_day": date.fromisoformat(dates[c.filename]).toordinal()
            if dates.get(c.filename)
            else 0,
        }
        entries.append(data)
    for start in range(0, len(entries), 16):
        part = entries[start : start + 16]
        vectors = (
            embedding()
            .encode([c["text"] for c in part], normalize_embeddings=True, batch_size=4)
            .tolist()
        )
        q.upsert(
            collection,
            points=[
                models.PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, c["chunk_id"])),
                    vector=v,
                    payload=c,
                )
                for c, v in zip(part, vectors)
            ],
            wait=True,
        )
    # Activation is a single SQL transaction; readers see only a fully written collection.
    with transaction() as s:
        s.execute(update(Corpus).values(active=False))
        row = s.get(Corpus, version)
        full = {**manifest, "collection": collection, "chunks": entries}
        if row:
            row.manifest = full
            row.active = True
        else:
            s.add(Corpus(id=version, manifest=full, active=True))
    return version


def active():
    with transaction() as s:
        row = s.scalar(select(Corpus).where(Corpus.active.is_(True)))
        return row.manifest if row else None


def retrieve(query, filenames=None, as_of=None, top_k=5):
    from qdrant_client import models

    manifest = active()
    if not manifest:
        return []
    cutoff = as_of or date.today().isoformat()

    def permitted(c):
        return (filenames is None or c["filename"] in filenames) and (
            not c.get("report_date") or c["report_date"] <= cutoff
        )

    candidates = {}
    words = set(re.findall(r"[а-яa-z0-9]{4,}", query.lower()))
    # Lexical candidates never escape the same document/date scope.
    lexical = []
    for c in manifest["chunks"]:
        if not permitted(c) or c.get("confidence", 0) < 0.65:
            continue
        score = len(
            words & set(re.findall(r"[а-яa-z0-9]{4,}", c["text"].lower()))
        ) / max(1, len(words))
        if score >= 0.1:
            lexical.append((score, c))
    for score, c in sorted(lexical, key=lambda x: x[0], reverse=True)[:20]:
        candidates[c["chunk_id"]] = {**c, "score": score}
    conditions = [
        models.FieldCondition(
            key="report_day",
            range=models.Range(lte=date.fromisoformat(cutoff).toordinal()),
        )
    ]
    if filenames is not None:
        if not filenames:
            return []
        conditions.append(
            models.FieldCondition(key="filename", match=models.MatchAny(any=filenames))
        )
    vector = embedding().encode([query], normalize_embeddings=True).tolist()[0]
    hits = (
        client()
        .query_points(
            manifest["collection"],
            query=vector,
            query_filter=models.Filter(must=conditions) if conditions else None,
            limit=40,
        )
        .points
    )
    for hit in hits:
        if (
            permitted(hit.payload)
            and hit.payload.get("confidence", 0) >= 0.65
            and hit.score >= float(os.getenv("RAG_DENSE_THRESHOLD", ".45"))
        ):
            candidates[hit.payload["chunk_id"]] = {**hit.payload, "score": hit.score}
    values = list(candidates.values())
    if not values:
        return []
    scores = reranker().predict([(query, c["text"]) for c in values]).tolist()
    ranked = sorted(zip(scores, values), key=lambda x: x[0], reverse=True)
    return [
        {**c, "score": float(score)}
        for score, c in ranked
        if score >= float(os.getenv("RAG_RERANK_THRESHOLD", "0"))
    ][:top_k]


def collect_old_corpora():
    """Explicit maintenance, never run concurrently with active analysis."""
    q = client()
    with transaction() as s:
        for row in s.scalars(select(Corpus).where(Corpus.active.is_(False))):
            q.delete_collection(row.manifest["collection"])
            s.delete(row)
