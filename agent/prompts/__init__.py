"""
Пакет специализированных промптов для каждой модели AI-пайплайна.
Каждый модуль оптимизирован под сильные стороны конкретной нейросети.
"""

from .gemma_classifier import build_classifier_prompt, SYSTEM_PROMPT as GEMMA_CLASSIFIER_SYSTEM
from .gemma_ranker import build_ranker_prompt, SYSTEM_PROMPT as GEMMA_RANKER_SYSTEM
from .qwen_rag import build_rag_prompt, SYSTEM_PROMPT as QWEN_RAG_SYSTEM
from .deepseek_insight import build_deepseek_insight_prompt, SYSTEM_PROMPT as DEEPSEEK_INSIGHT_SYSTEM
from .glm_orchestrator import (
    build_orchestrator_plan_prompt,
    build_verification_prompt,
    SYSTEM_ORCHESTRATOR as GLM_ORCHESTRATOR_SYSTEM,
    SYSTEM_FACT_CHECKER as GLM_FACT_CHECKER_SYSTEM
)
from .qwen_chat import build_chat_prompt, SYSTEM_PROMPT as QWEN_CHAT_SYSTEM

__all__ = [
    "build_classifier_prompt",
    "build_ranker_prompt",
    "build_rag_prompt",
    "build_deepseek_insight_prompt",
    "build_orchestrator_plan_prompt",
    "build_verification_prompt",
    "build_chat_prompt",
    "GEMMA_CLASSIFIER_SYSTEM",
    "GEMMA_RANKER_SYSTEM",
    "QWEN_RAG_SYSTEM",
    "DEEPSEEK_INSIGHT_SYSTEM",
    "GLM_ORCHESTRATOR_SYSTEM",
    "GLM_FACT_CHECKER_SYSTEM",
    "QWEN_CHAT_SYSTEM",
]
