"""Gateway signatures carry identity and company scope; a service key alone grants none."""

import hashlib, hmac, json, time, uuid, os, logging
from contextvars import ContextVar
from fastapi import Request
from starlette.responses import JSONResponse
from .settings import settings
from .storage import repositories as repo

principal = ContextVar("principal", default=None)


def signed_message(request, stamp, user, companies):
    return "\n".join(
        [stamp, user, companies, request.method, request.url.path, request.url.query]
    )


def identity(request):
    cfg = settings()
    if cfg.env in {"dev", "test"} and os.getenv("REQUIRE_AUTH", "false") != "true":
        return {"user": "local", "companies": ["*"], "admin": True}
    admin = request.headers.get("x-admin-key", "")
    if cfg.admin_key and hmac.compare_digest(admin, cfg.admin_key):
        return {"user": "admin", "companies": ["*"], "admin": True}
    # The HTTPS proxy authenticates demo users with HTTP Basic Auth. Its separate
    # credential grants access to demo companies, never administrative routes.
    demo = request.headers.get("x-demo-proxy-key", "")
    if cfg.env == "prod" and cfg.demo_proxy_key and hmac.compare_digest(demo, cfg.demo_proxy_key):
        return {"user": "demo-proxy", "companies": ["*"], "admin": False}
    # Internal API credentials authenticate transport only. No company access without signed scope.
    stamp = request.headers.get("x-auth-timestamp", "")
    user = request.headers.get("x-auth-user", "")
    companies = request.headers.get("x-auth-companies", "")
    signature = request.headers.get("x-auth-signature", "")
    if not cfg.gateway_secret:
        return None
    try:
        if abs(time.time() - int(stamp)) > 60:
            return None
    except ValueError:
        return None
    expected = hmac.new(
        cfg.gateway_secret.encode(),
        signed_message(request, stamp, user, companies).encode(),
        hashlib.sha256,
    ).hexdigest()
    if not user or not hmac.compare_digest(signature, expected):
        return None
    return {
        "user": user,
        "companies": [c for c in companies.split(",") if c],
        "admin": False,
    }


def allowed(company, who):
    return who and ("*" in who["companies"] or company in who["companies"])


def install(app):
    @app.middleware("http")
    async def access(request: Request, call_next):
        from .observability import request_context

        rid = uuid.uuid4().hex
        rt = request_context.set(rid)
        token = None
        company_token = None

        def respond(content, status, headers=None):
            return JSONResponse(
                content, status, headers={"X-Request-ID": rid, **(headers or {})}
            )

        try:
            if request.url.path in {"/health", "/health/live", "/health/ready"}:
                response = await call_next(request)
            else:
                who = identity(request)
                if not who:
                    return respond({"detail": "Authentication required"}, 401)
                token = principal.set(who)
                admin_path = request.url.path.startswith(
                    "/api/developer"
                ) or request.url.path in {
                    "/api/news/refresh",
                    "/api/rag/index",
                    "/health/models",
                }
                if admin_path and not who["admin"]:
                    return respond({"detail": "Administrator required"}, 403)
                body = {}
                if request.method in {"POST", "PUT", "PATCH"}:
                    data = await request.body()
                    if len(data) > 100_000:
                        return respond({"detail": "Request too large"}, 413)
                    try:
                        body = json.loads(data) if data else {}
                    except ValueError:
                        return respond({"detail": "Invalid JSON"}, 422)
                    if not isinstance(body, dict):
                        return respond({"detail": "Expected object"}, 422)
                company = request.query_params.get("company_id") or body.get(
                    "company_id"
                )
                parts = request.url.path.split("/")
                if "companies" in parts:
                    index = parts.index("companies")
                    company = parts[index + 1] if len(parts) > index + 1 else None
                card_id = body.get("card_id") or body.get("insight_id")
                if request.url.path.startswith("/api/cards/"):
                    card_id = parts[-1]
                if card_id:
                    event = repo.insight(card_id)
                    if event:
                        from .storage.db import transaction
                        from .storage.models import Insight

                        with transaction() as s:
                            owner = s.get(Insight, card_id).company_id
                        if not allowed(owner, who):
                            return respond({"detail": "Not found"}, 404)
                        if company and company != owner:
                            return respond({"detail": "Not found"}, 404)
                        company = owner
                if company and not allowed(company, who):
                    return respond({"detail": "Company access denied"}, 403)
                if request.url.path.startswith("/api/feed/jobs/"):
                    job = repo.get_job(parts[-1])
                    if job and (
                        not job["company_id"]
                        and not who["admin"]
                        or job["company_id"]
                        and not allowed(job["company_id"], who)
                    ):
                        return respond({"detail": "Not found"}, 404)
                # Global news/source lists and reports have no tenant data. Metrics are scoped in handler.
                if company:
                    from .observability import company_context

                    company_token = company_context.set(company)
                if request.method == "POST":
                    try:
                        rate_limit(who["user"], request.url.path)
                    except RuntimeError:
                        return respond(
                            {"detail": "Rate limit dependency unavailable"}, 503
                        )
                    except OverflowError:
                        return respond(
                            {"detail": "Too many requests"},
                            429,
                            headers={"Retry-After": "60"},
                        )
                response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            logging.getLogger("alpha.requests").info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": rid,
                        "method": request.method,
                        "path": request.url.path,
                    }
                )
            )
            if company_token is not None:
                from .observability import company_context

                company_context.reset(company_token)
            if token is not None:
                principal.reset(token)
            request_context.reset(rt)


def rate_limit(user, path):
    cfg = settings()
    if not cfg.redis_url:
        if cfg.env == "prod":
            raise RuntimeError("Redis unavailable")
        return
    from .jobs import redis

    try:
        r = redis()
        key = (
            "rate:"
            + hashlib.sha256((user + "|" + path).encode()).hexdigest()
            + ":"
            + str(int(time.time() // 60))
        )
        count = r.eval(
            "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],61) end; return n",
            1,
            key,
        )
        if count > int(os.getenv("REQUESTS_PER_MINUTE", "20")):
            raise OverflowError()
    except OverflowError:
        raise
    except Exception:
        raise RuntimeError("Redis unavailable") from None
