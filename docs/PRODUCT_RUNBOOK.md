# Product foundation runbook

This is a reviewed-development candidate, not a bank production certification. The existing remote server has not been modified by this work.

## Provisioning and startup

1. Use a separate checkout and distinct volumes from the running demo. Keep a copy of its code, `.env`, SQLite files, JSON cache, CSV, PDF and OCR sidecars. Do not replace that deployment in place.
2. Copy `.env.example` to `.env`; choose a long URL-safe `POSTGRES_PASSWORD`. Product Compose overrides `APP_ENV`, `DATABASE_URL`, Redis and Qdrant URLs. Do not commit `.env`. Database/Redis/Qdrant ports are private to the Compose network.
3. Provision CSV into `backend/data/` and PDFs into `data_alfbnk/` explicitly. `DATA_DIR` and `PDF_DIR` are container paths. The indexing worker needs write permission for PDF OCR sidecars; app UID is 10001. Reports volume also needs that UID. Vision is disabled: no provider image-input capability has been confirmed.
4. Configure a trusted HTTPS gateway/OIDC proxy before exposing data. Production denies unauthenticated data access even if `REQUIRE_AUTH=false`. `ADMIN_API_KEY` is for internal administration only, never frontend JS. No public OIDC login is bundled.
5. Run:

```sh
docker compose -f compose.product.yaml up -d postgres redis qdrant
docker compose -f compose.product.yaml build
docker compose -f compose.product.yaml run --rm migrate
docker compose -f compose.product.yaml up -d --wait
```

Backend and frontend bind only to localhost ports 18081 and 18080. Add a trusted HTTPS proxy; do not expose the internal API key through the frontend.

`compose.yaml` remains the simpler SQLite/Redis local mode; product mode requires PostgreSQL and does not fall back if it is unavailable. Keep these stacks separate. Existing SQLite volumes need explicit import; there is no silent schema replacement or automatic migration of prototype files.

## Identity and scope

A gateway must validate the user's session/OIDC identity, determine allowed company IDs on the server, strip incoming `X-Auth-*` headers, then set `X-Auth-Timestamp`, `X-Auth-User`, `X-Auth-Companies` (comma-separated IDs), and `X-Auth-Signature`. Signature is lowercase HMAC-SHA256 with `GATEWAY_SIGNING_SECRET`, over six newline-separated fields: timestamp, user, companies, method, path, raw query string. Timestamp skew is limited to 60 seconds. Preserve the signed path/query exactly. Browser clients never receive this secret. The API checks company, card, insight and job ownership independently of user input. Administrative endpoints require the separate internal admin key.

A service credential without signed company scope grants no user-data access. This is an integration seam, not a completed OIDC implementation. Until a gateway is configured, production data routes stay closed.

## Jobs and compatibility

- RSS refresh, manual analysis, feed refresh, PDF indexing and active probes are queued in RQ and have SQL job records.
- `POST /api/news/refresh`, `/api/insights/analyze`, `/api/feed/refresh`, `/api/rag/index` return **202 + job_id**. The analyze request body is retained, but its old synchronous response becomes asynchronous; clients must poll `GET /api/feed/jobs/{job_id}`.
- `GET /health/models` reads persisted probe results. `force=true` submits an administrative probe job; submissions are limited to one per minute. Ordinary GET does not call a model.
- `/health/live` is process-only. `/health/ready` returns 503 for unavailable required dependencies or absent real CSV in prod; hybrid mode also requires provisioned artifacts and an active corpus. Existing `/health` stays compatible.
- Both chat contracts use server-owned stored context. Legacy `/api/chat` matches an exact stored title within the supplied authorized company/role and rejects ambiguity; it ignores client-supplied insight/history. `/chat` uses exact card ID. Fallback is explicit; it is not generated advice.
- Scheduler runs RSS refresh and recovery, not blanket analysis of every news/company combination. Analysis batches remain capped at 3 candidates. RQ retries transient failures with bounded intervals; model gateway separately retries transient provider failures once. Audit rejection is terminal for that job.
- A worker lease lasts up to 930 seconds. Recovery requeues expired or undelivered jobs; delivery is at least once, with exact-version card IDs and completion checks. Restarts may delay recovery until the lease expires. Completed job replay does not regenerate cards.

## Persistence and versions

SQLAlchemy repositories store news, possible-duplicate groups, source health, insights, citations, feedback, jobs, processing history, probes, model calls and corpus manifests. Identical normalized titles are only candidate duplicate groups; different articles are not merged on title similarity. RSS GUIDs are source-namespaced, so new IDs differ from the prototype. Failed refresh does not delete history. Redis holds an expendable 60-second news snapshot; database reads survive cache loss.

Result keys include source-namespaced news ID and article content revision, company/profile digest, role, prompt content, model configuration and corpus version. An edited article invalidates only older content results; historical cards remain stored. A changed dependency hides stale results from the current feed. Versioned historical results remain in storage. Feed supports bounded `limit`/`offset`. Global classification is cached independently of personal relevance. Audit-invalid results are saved as rejected and never published as verified. Processing errors retain safe exception type, not credential-bearing payloads.

## Legacy import

Run only against copied prototype files, and review `--dry-run` first:

```sh
python scripts/import_legacy.py --news-json /backup/news.json --insights-sqlite /backup/insights.db --dry-run
python scripts/import_legacy.py --news-json /backup/news.json --insights-sqlite /backup/insights.db
```

Historical dependency versions cannot be reconstructed. Imported verified cards use `legacy-unknown` and are not presented as current-version analysis. Unverified legacy cards are skipped. Prototype feedback that existed only in process memory cannot be recovered; this importer does not invent it.

## Models, rate limits and costs

Confirmed text model IDs are in `capabilities.py`/`models_cfg.py`; vision stays disabled. Timeouts, at most one transient retry, Redis owner-token concurrency slots, a short circuit breaker, daily reserved-output-token and call limits are applied in the shared gateway. Slot leases expire after 180 seconds. Redis failure blocks new rate-limited operations; durable SQL data remains. Set `MODEL_DAILY_TOKEN_BUDGET`, `MODEL_DAILY_CALL_LIMIT`, `MODEL_CONCURRENCY`, `REQUESTS_PER_MINUTE`, `MAX_QUEUE_SIZE` before load testing.

The daily token limit reserves the maximum output allowance for two attempts; it is not an exact bill or a limit on input tokens. One logical call can make two provider requests. `MODEL_PRICES_JSON` optionally maps model IDs to `input`/`output` prices per million tokens. Without configured prices, cost is null, never zero. Unknown failed-attempt usage remains unknown. `/api/developer/usage` exposes recorded calls/tokens and estimated cost in the configured tariff units; compare with provider billing. Logs/records exclude raw prompts, CSV and secrets.

A live smoke test is an explicit paid action:

```sh
python scripts/live_model_smoke.py
```

Without a key it prints SKIP; configured failures return nonzero. Use the same allowed provider configured for the project. No live model calls are part of the ordinary test suite.

## PDF / vector RAG

Default mode is lexical, preserving the existing fallback. Hybrid mode is implemented but must be separately provisioned and validated; no weights are downloaded by an HTTP handler.

1. Build optional dependencies with `INSTALL_RAG=true`. CPU dependencies are in `backend/requirements-rag.txt`.
2. Select an immutable official reranker revision and explicitly provision model files with `scripts/provision_models.py --directory /models --reranker-revision <40-character-SHA>`. BGE-M3 revision is pinned; dimension is 1024. Mount the model volume read-only to app/worker after provisioning. Files are large and CPU/RAM needs must be measured; the current 4GB demo server is not certified for this heavier stack.
3. Supply checked report dates in `PDF_REPORT_DATES_JSON`; `config/report_dates.example.json` is a starting point from first-page OCR for seven reports. Unknown dates remain unknown. Historical excerpts and generated summaries are not labelled the bank's current official position automatically.
4. Submit the protected `/api/rag/index` job. Explicit indexing extracts text, optionally PDF tables, and Tesseract rus+eng TSV OCR with word-confidence averages for scans. OCR does not reliably reconstruct scanned table layout; vision remains off.
5. Each index has PDF checksums, extractor/chunker version, embedding revision/dimension, reranker artifact manifest and report dates. A new Qdrant collection is fully written before a SQL transaction activates it. Old collections are retained for rollback; `collect_old_corpora()` is an explicit maintenance step and must not race in-flight analysis.
6. Hybrid retrieval combines keyword candidates and filtered dense results, then reranks. Document/date filters apply to candidates. Unknown date does not establish current authority; low-confidence extraction is excluded. Citation IDs from synthesis are checked against supplied chunks. Exact source pages/checksums are persisted.

No actual BGE/reranker inference was validated in this run because model weights were not provisioned. Qdrant operations were tested with deterministic fixture vectors. Do not equate this with evaluated hybrid-search quality. The small real-report lexical baseline is in `retrieval-baseline.json`; labels are engineering checks from OCR, not expert annotations.

## Backup, restore and rollback

Take a PostgreSQL dump and backup CSV/PDF plus OCR sidecars and model artifact manifest independently. Restrict file permissions; do not commit dumps or credentials.

```sh
docker compose -f compose.product.yaml exec -T postgres pg_dump -U alpha -Fc alpha > backup.dump
docker compose -f compose.product.yaml exec -T postgres createdb -U alpha alpha_restore_check
docker compose -f compose.product.yaml exec -T postgres pg_restore -U alpha -d alpha_restore_check < backup.dump
```

Verify row counts, FKs, feed and feedback against the restored DB before switching DATABASE_URL. Test restores only into a new database. Restore PDF/model files separately and rebuild a vector collection explicitly; the database contains the corpus manifest. Old immutable collections allow corpus rollback by an administrator switching the active manifest in a transaction. Full reindex after restore requires model artifacts and can be slow.

For application rollback, retain the prior image tag and database backup, stop consumers, and run the prior compatible image against the backed-up schema. Do not use destructive Alembic downgrade on live data. Initial schema downgrade deliberately refuses deletion. Never run `down -v` on a deployment whose data is needed. This PR was not applied to the running demo.

## Checks and known limits

See `PRODUCT_VERIFICATION.md` for actually executed checks. OIDC gateway wiring, weights/artifact provisioning, expert-labelled retrieval quality, heavy-stack sizing, production load/SLO, monetary billing reconciliation, backup scheduling, automated rollback, scanned-table accuracy and HA infrastructure remain operator validation gates. Compose alone does not provide bank-grade availability.
