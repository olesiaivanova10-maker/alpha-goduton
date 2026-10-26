# Verification record — 26 October 2026

Target: isolated `backend/product-foundation` checkout from main `7648caa`, plus explicit cherry-picks of the working demo improvements. No SSH operations, remote migrations or remote restarts were performed for this task. Existing public demo is unchanged.

## Executed

- **43 unit/component/API tests passed**, Python 3.13 locally; provider calls mocked in ordinary tests. Includes access isolation, signed identity tampering, rating/FK constraints and rollback, failed audit, audit timeout fallback, idempotent ingestion, source namespace, XML entity rejection, per-redirect public-address checks, missing artifacts, hybrid candidate scope/date/confidence filtering with fixture encoders, request/model usage records, production readiness without CSV, content-version invalidation and worker discovery re-registration.
- Discovery also ran with `DATA_DIR` pointed at an absent directory; company-dependent tests use in-memory fixtures. Private-dataset loader check was executed locally with supplied real CSV; it is skipped when those files are not provisioned.
- **Frontend TypeScript/Vite production build passed** in Docker. Dependency peer/CSS warnings remain; they did not fail the build. CI workflow was added but its GitHub-run result is not claimed here.
- Both Compose configurations passed `docker compose config --quiet`.
- Product images built with non-root application user. Base/service image digests were captured from the actually pulled/built images and pinned.
- **Real local PostgreSQL + Redis/RQ + Qdrant integration passed**, using a fresh PostgreSQL database, separate Redis logical DB, generated actual two-page PDF fixture and fixture model responses. RSS fixture → persistent source/news records → actual queue/worker → company profile → relevance → PDF page 2 → synthesis/audit fixture → feed → both chat contracts → feedback. No external model calls in this integration test.
- Live public RSS redirect regression check passed for Interfax and Kommersant: 377 records, no failed source; see `rss-redirect-check.json`. Only allowlisted HTTPS/public destinations are followed.
- Job replay did not rerun completed analysis. Actual Redis owner-token locks, model concurrency denial and exhausted-lease recovery passed.
- Actual Qdrant collection creation/upsert/query/deletion and document metadata isolation passed with deterministic fixture vectors. This does **not** validate BGE/reranker model quality.
- Full local stack was started, with process/readiness endpoints and authenticated/unauthenticated API checks. A real Redis restart exposed missing worker discovery registration; a resilient worker heartbeat and worker-specific healthcheck were added and tested. A second actual Redis restart then passed healthchecks for all seven services.
- **Persistence after actual local PostgreSQL/Redis restart:** 295 news / 3 insights / 3 feedback rows unchanged; Redis AOF test marker retained. These counts are test-environment data, not a production freshness claim.
- **PostgreSQL dump/restore into a separate database passed:** restored fixture news, insight and feedback counts each 1. Existing tables were not reset.
- **Explicit live smoke passed** through the new gateway: Gemma, Qwen, DeepSeek and GLM returned valid short JSON. See `live-smoke.json`. Six task entries share four model probes. Key read from existing private local `.env`, never copied into this checkout, logs, build or Git. These probes do not establish long-form generation/audit quality.
- **Real-report lexical baseline**, 9 supplied PDFs / existing OCR sidecars, 4 engineering-labelled queries: Recall@5 **0.667**, page precision **0.167**, no-answer accuracy **0.0**. See `retrieval-baseline.json`. This exposes a real weakness; it is not a satisfactory retrieval-quality gate. Labels are from first-page OCR review, not independent expert annotation.
- **Preprocessing benchmark:** 1000 fixture RSS records, 10 profiles from real CSV, zero model calls. RSS parsing 15.74 ms, mean profile extraction 55.85 ms, mean pre-sort 11.14 ms on this machine. See `local-profile.json`; no production throughput or model-latency claim.

## Commands / reproduction

Ordinary tests:

```sh
APP_ENV=test PYTHONPATH=backend:. python -m unittest discover -s backend/tests -v
```

Start only separate local dependencies and migrate a new test database. Run `tests/integration/product_services.py` in the app image with `tests/` mounted at `/tests`, `PYTHONPATH=/app:/app/backend:/tests`, a private test admin key, real/provisioned test CSV, and `REDIS_URL=redis://redis:6379/1`. Use `tests/integration/compose.test.yaml` only for this private test environment; its fixture admin credential is not a production secret. The PostgreSQL URL must point to the separately created test database. Do not run fixtures against an existing deployment database or an actively consumed queue.

## Not verified / remaining gates

- No BGE/reranker weights were downloaded/provisioned; actual hybrid inference, thresholds, quality, runtime memory and heavy optional image build remain unverified. The code fails closed on missing artifacts; ordinary HTTP requests never download weights.
- No vision path is enabled. Provider image-input capability is not established. Scanned-table layout and OCR numerical accuracy need additional evaluation.
- No public OIDC gateway/login deployment was performed; production data access is closed without trusted identity or internal administrator credentials. Authentication/infrastructure integration remains a deployment gate.
- No live long-form end-to-end analysis of many companies, provider monetary reconciliation, sustained concurrent load/SLO or HA test was performed. Current inference batches are bounded at 3 candidates, not the whole archive.
- No unattended backup scheduling or automatic production rollback was configured. Manual dump/restore was tested locally only.
- Alembic migrations and prototype importer are for explicit operator use. The existing remote database was not imported or modified.
- Docker-host platform was Apple Silicon; Linux AMD64 execution of the pinned multi-platform stack and optional model artifacts remains a CI/deployment check.

This PR is a product foundation for review, not a completed bank-production certification or permission to replace the currently working server.
