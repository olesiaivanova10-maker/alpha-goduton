from .storage.db import transaction
from .storage.models import Classification
from .versions import digest, prompt_version
from agent.schemas import NewsClassification
from agent.models_cfg import TASK_MODEL_MAPPING, PipelineTask


def classify_once(agent, news):
    key = digest(
        [
            news.model_dump(mode="json"),
            prompt_version(),
            TASK_MODEL_MAPPING[PipelineTask.CLASSIFICATION].model_dump(
                mode="json", exclude={"why"}
            ),
        ]
    )
    from contextlib import nullcontext
    from .settings import settings

    lock = nullcontext()
    if settings().redis_url:
        from .jobs import redis

        lock = redis().lock("classification:" + key, timeout=150, blocking_timeout=100)
    with lock:
        return _classify(agent, news, key)


def _classify(agent, news, key):
    with transaction() as s:
        row = s.get(Classification, key)
        if row:
            return NewsClassification.model_validate(row.payload)
    result = agent.step_1_classify(news)
    with transaction() as s:
        if not s.get(Classification, key):
            s.add(
                Classification(
                    key=key,
                    news_id=news.news_id,
                    payload=result.model_dump(mode="json"),
                )
            )
    return result
