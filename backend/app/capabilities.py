"""Provider-confirmed text IDs; image support is deliberately disabled."""
import os,json
from agent.models_cfg import TASK_MODEL_MAPPING
CONFIRMED={cfg.model.value:{'text':True,'json':cfg.supports_structured_output,'image':False} for cfg in TASK_MODEL_MAPPING.values()}
def validate_model(model):
    allowed=json.loads(os.getenv('ALLOWED_MODEL_IDS_JSON',json.dumps(list(CONFIRMED))))
    if model not in allowed or model not in CONFIRMED:raise ValueError('Model is not in the confirmed text allowlist')
    return CONFIRMED[model]
