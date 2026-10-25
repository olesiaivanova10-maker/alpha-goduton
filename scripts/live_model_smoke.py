"""Explicit opt-in live model check. No network in normal unit tests."""

import os, sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if not os.getenv("ALFA_HACK_API_KEY"):
    print("SKIP: ALFA_HACK_API_KEY not configured")
    raise SystemExit(0)
from backend.app.model_health import check_models

result = check_models(force=True)
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if all(i["status"] == "ok" for i in result["items"]) else 1)
