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
                    from types import SimpleNamespace
                    from .model_gateway import call
                    raw=call(client,task,SimpleNamespace(model=SimpleNamespace(value=name),temperature=0,max_tokens=256,supports_structured_output=True),'Return JSON only.','Return JSON only: {"ok":true}',10)
                    payload=json.loads(raw)
                    result['status'] = 'ok' if payload.get('ok') is True else 'degraded'
                except Exception as error:
                    result['status'] = {'AuthenticationError':'auth_failure','PermissionDeniedError':'auth_failure','RateLimitError':'rate_limit','APITimeoutError':'timeout'}.get(type(error).__name__,'down')
                    result['error'] = type(error).__name__
                result['latency_ms'] = round((time.monotonic()-start)*1000)
            probes[name] = result
        items.append({'task':task.value, **probes[name]})
    from .storage.db import transaction
    from .storage.models import Probe,utc
    with transaction() as s:
        for model,result in probes.items():
            row=s.get(Probe,model)
            if row:row.payload=result;row.updated_at=utc()
            else:s.add(Probe(model_id=model,payload=result))
    _cache.update(checked_at=now, items=items)
    return {**_cache, 'cached':False}

def cached_models():
    from .storage.db import transaction
    from .storage.models import Probe
    with transaction() as s:
        results={r.model_id:{**r.payload,'stale':time.time()-r.updated_at.timestamp()>300} for r in s.query(Probe).all()}
    return {'cached':True,'items':[{'task':task.value,**results.get(cfg.model.value,{'model':cfg.model.value,'status':'not_checked'})} for task,cfg in TASK_MODEL_MAPPING.items()]}
