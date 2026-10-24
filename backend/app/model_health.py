import time
from datetime import datetime, timezone
from agent.models_cfg import TASK_MODEL_MAPPING

_cache={"checked_at":0.0,"items":[]}

def check_models(force: bool=False, ttl: int=60) -> dict:
    now=time.time()
    if not force and now-_cache["checked_at"]<ttl: return {"checked_at":_cache["checked_at"],"items":_cache["items"],"cached":True}
    items=[]
    for task,cfg in TASK_MODEL_MAPPING.items():
        items.append({"task":task.value,"model":cfg.model.value,"status":"not_configured","latency_ms":None,"last_checked_at":datetime.now(timezone.utc).isoformat(),"error":"live health-check requires ALFA_HACK_API_KEY"})
    _cache.update({"checked_at":now,"items":items}); return {"checked_at":now,"items":items,"cached":False}
