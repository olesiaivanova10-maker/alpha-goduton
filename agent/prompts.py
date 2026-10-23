"""
Фасадный модуль промптов для обратной совместимости.
Все специализированные промпты распределены по отдельным модулям в пакете `ai_engine/prompts/`:
- gemma_classifier.py  (Gemma 4 — классификация)
- gemma_ranker.py      (Gemma 4 — оценка релевантности)
- qwen_rag.py          (Qwen 3.6 — RAG аналитика банка)
- deepseek_insight.py  (DeepSeek-V4.1 — глубокая интерпретация)
- glm_orchestrator.py  (GLM-5.3 — оркестратор и самопроверка)
- qwen_chat.py         (Qwen 3.6 — интерактивный Q&A чат в UI)
"""

from .prompts.gemma_classifier import (
    SYSTEM_PROMPT as PROMPT_CLASSIFIER,
    build_classifier_prompt
)
from .prompts.gemma_ranker import (
    SYSTEM_PROMPT as PROMPT_RELEVANCE_RANKER,
    build_ranker_prompt
)
from .prompts.qwen_rag import (
    SYSTEM_PROMPT as PROMPT_RAG,
    build_rag_prompt
)
from .prompts.deepseek_insight import (
    SYSTEM_PROMPT as PROMPT_INSIGHT_SYNTHESIS,
    ROLE_MODIFIERS as ROLE_SPECIFIC_INSTRUCTIONS,
    build_deepseek_insight_prompt
)
from .prompts.glm_orchestrator import (
    SYSTEM_ORCHESTRATOR,
    SYSTEM_FACT_CHECKER as PROMPT_FACT_CHECKER,
    build_orchestrator_plan_prompt,
    build_verification_prompt
)
from .prompts.qwen_chat import (
    SYSTEM_PROMPT as PROMPT_CHAT,
    build_chat_prompt
)
