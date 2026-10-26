"""Bounded model calls with shared concurrency leases and usage accounting."""

import json, os, time, uuid, random
from contextlib import contextmanager
from .storage.db import transaction
from .storage.models import ModelCall, utc
from .observability import request_context, company_context, job_context
from .versions import prompt_version
from .settings import settings


class ModelGatewayError(RuntimeError):
    """Safe exception category; provider payloads must not reach logs."""


@contextmanager
def permit(model, max_tokens):
    cfg = settings()
    r = None
    key = "model:" + model
    token = uuid.uuid4().hex
    if cfg.redis_url:
        from .jobs import redis

        r = redis()
        now = time.time()
        script = """redis.call('ZREMRANGEBYSCORE',KEYS[1],'-inf',ARGV[1]); if redis.call('ZCARD',KEYS[1])>=tonumber(ARGV[2]) then return 0 end; redis.call('ZADD',KEYS[1],ARGV[3],ARGV[4]); redis.call('EXPIRE',KEYS[1],200); return 1"""
        if r.exists("circuit:" + model):
            raise RuntimeError("Model circuit open")
        if not r.eval(
            script,
            1,
            key,
            now,
            int(os.getenv("MODEL_CONCURRENCY", "2")),
            now + 180,
            token,
        ):
            raise RuntimeError("Model concurrency limit")
        # Budget reservations count maximum requested tokens, including failures. No hidden optimistic spend.
        day = utc().strftime("%Y%m%d")
        budget = int(os.getenv("MODEL_DAILY_TOKEN_BUDGET", "200000"))
        calls = r.incr("call-budget:" + day)
        r.expire("call-budget:" + day, 90000)
        if calls > int(os.getenv("MODEL_DAILY_CALL_LIMIT", "100")):
            r.zrem(key, token)
            raise RuntimeError("Daily call budget exhausted")
        used = r.eval(
            "local n=redis.call('INCRBY',KEYS[1],ARGV[1]); redis.call('EXPIRE',KEYS[1],90000); return n",
            1,
            "token-budget:" + day,
            max_tokens,
        )
        if used > budget:
            r.zrem(key, token)
            raise RuntimeError("Daily token budget exhausted")
    elif cfg.env == "prod":
        raise RuntimeError("Redis unavailable")
    try:
        yield r
    finally:
        if r:
            r.zrem(key, token)


def call(client, task, model_cfg, system_prompt, user_prompt, timeout):
    model = model_cfg.model.value
    from .capabilities import validate_model

    validate_model(model)
    if len(system_prompt) + len(user_prompt) > int(
        os.getenv("MODEL_CONTEXT_MAX_CHARS", "40000")
    ):
        raise ValueError("Model context too large")
    response = None
    error = None
    started = time.monotonic()
    try:
        with permit(model, model_cfg.max_tokens * 2) as r:
            for attempt in range(2):
                try:
                    response = client.chat.completions.create(
                        model=model,
                        temperature=model_cfg.temperature,
                        max_tokens=model_cfg.max_tokens,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        timeout=timeout,
                        extra_body=getattr(model_cfg,"provider_options",None) or None,
                        response_format={"type": "json_object"}
                        if model_cfg.supports_structured_output
                        else None,
                    )
                    text = response.choices[0].message.content
                    if not text:
                        raise ValueError("Empty model answer")
                    if model_cfg.supports_structured_output:
                        json.loads(text)
                    if r:
                        r.delete("failures:" + model)
                    return text
                except Exception as e:
                    transient = type(e).__name__ in {
                        "RateLimitError",
                        "APITimeoutError",
                        "APIConnectionError",
                        "InternalServerError",
                    }
                    if not transient or attempt == 1:
                        raise
                    time.sleep(0.5 + random.random())
    except Exception as e:
        error = type(e).__name__
        if settings().redis_url:
            try:
                from .jobs import redis

                r = redis()
                n = r.incr("failures:" + model)
                r.expire("failures:" + model, 120)
                if n >= 3:
                    r.set("circuit:" + model, "open", ex=30)
            except Exception:
                pass
        raise ModelGatewayError(error) from None
    finally:
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", None)
        output_tokens = getattr(usage, "completion_tokens", None)
        prices = json.loads(os.getenv("MODEL_PRICES_JSON", "{}")).get(model)
        cost = (
            (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1e6
            if prices and input_tokens is not None and output_tokens is not None
            else None
        )
        with transaction() as s:
            s.add(
                ModelCall(
                    id=uuid.uuid4().hex,
                    request_id=request_context.get(),
                    company_id=company_context.get(),
                    job_id=job_context.get(),
                    model_id=model,
                    task=task.value,
                    prompt_version=prompt_version(),
                    latency_ms=round((time.monotonic() - started) * 1000),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost,
                    error=error,
                )
            )
