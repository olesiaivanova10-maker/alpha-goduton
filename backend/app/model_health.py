"""Explicit, cached live probes; never expose credential-bearing configuration."""
import json
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit
from agent.models_cfg import TASK_MODEL_MAPPING, config

_cache = {"checked_at": 0.0, "items": []}

def check_models(force=False, ttl=60):
    now = time.time()
    if not force and now - _cache['checked_at'] < ttl:
        return {**_cache, 'cached': True}
    parsed = urlsplit(config.base_url)
    valid_url = parsed.scheme in {'http', 'https'} and bool(parsed.hostname)
    configured = bool(config.api_key) and not config.api_key.startswith('mock')
    items, probes = [], {}
    for task, cfg in TASK_MODEL_MAPPING.items():
        name = cfg.model.value
        if name not in probes:
            result = {'model': name, 'status': 'not_configured', 'latency_ms': None,
                      'last_checked_at': datetime.now(timezone.utc).isoformat(), 'error': None}
            if not valid_url:
                result['error'] = 'ALFA_HACK_API_BASE must be an HTTP(S) URL'
            elif not configured:
                result['error'] = 'API key not configured'
            else:
                start = time.monotonic()
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=config.api_key, base_url=config.base_url, timeout=10, max_retries=0)
                    response = client.chat.completions.create(model=name, messages=[{'role':'user','content':'Return JSON only: {"ok":true}'}], max_tokens=256, response_format={"type":"json_object"})
                    payload = json.loads(response.choices[0].message.content)
                    result['status'] = 'ok' if payload.get('ok') is True else 'degraded'
                except Exception as error:
                    result['status'] = 'down'
                    result['error'] = type(error).__name__
                result['latency_ms'] = round((time.monotonic()-start)*1000)
            probes[name] = result
        items.append({'task':task.value, **probes[name]})
    _cache.update(checked_at=now, items=items)
    return {**_cache, 'cached':False}
