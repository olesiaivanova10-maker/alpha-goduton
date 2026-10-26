"""
Конфигурация нейросетей и моделей для AI-пайплайна «Альфа Хак — Новостная аналитика».
Сформирована на основе утвержденной архитектурной связки команды.

Таблица распределения задач:
1. Классификация и фильтрация     -> Gemma 4
2. Оценка релевантности           -> Gemma 4
3. RAG                            -> Qwen3.6 + BGE
4. Глубокая интерпретация         -> DeepSeek-V4.1
5. Агент-оркестратор и проверка   -> GLM-5.3
6. Интерактивный Q&A чат в UI     -> Qwen3.6
"""

import os
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class ModelName(str, Enum):
    """Идентификаторы утвержденных правилами хакатона моделей."""
    GEMMA_4 = "google/gemma-4-26b-a4b-it"
    QWEN_3_6 = "qwen/qwen3.6-35b-a3b"
    DEEPSEEK_V4_1 = "deepseek/deepseek-v4.1-flash"
    GLM_5_3 = "z-ai/glm-5.3-flash"
    
    QWEN_VISION = "qwen/qwen3-vl-30b-a3b-instruct"
    KIMI = "moonshotai/kimi-k2.6"

    # Вспомогательные локальные модели для эмбеддингов/реранкинга
    BGE_EMBEDDINGS = "BAAI/bge-m3"
    BGE_RERANKER = "BAAI/bge-reranker-v2-m3"


class PipelineTask(str, Enum):
    CLASSIFICATION = "classification_and_filtering"
    RELEVANCE = "relevance_assessment"
    RAG = "rag_retrieval_and_synthesis"
    DEEP_INTERPRETATION = "deep_interpretation"
    ORCHESTRATOR = "orchestrator_and_verification"
    INTERACTIVE_CHAT = "interactive_qa_chat"


class ModelTaskConfig(BaseModel):
    """Конфигурация параметров генерации и обоснование выбора модели под задачу."""
    task: PipelineTask
    model: ModelName
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1024)
    supports_structured_output: bool = True
    provider_options: dict = Field(default_factory=dict)
    why: str = Field(..., description="Обоснование выбора модели из архитектурного решения команды")


# ==============================================================================
# Утвержденная архитектурная связка моделей команды
# ==============================================================================
TASK_MODEL_MAPPING: Dict[PipelineTask, ModelTaskConfig] = {
    PipelineTask.CLASSIFICATION: ModelTaskConfig(
        task=PipelineTask.CLASSIFICATION,
        model=ModelName.GEMMA_4,
        temperature=0.1,
        max_tokens=2000,
        supports_structured_output=True,
        why="Дешевизна, скорость обработки, бинарный отсев."
    ),
    
    PipelineTask.RELEVANCE: ModelTaskConfig(
        task=PipelineTask.RELEVANCE,
        model=ModelName.GEMMA_4,
        temperature=0.1,
        max_tokens=2000,
        supports_structured_output=True,
        why="Оценка связи новости с признаками клиента; это реальный вызов LLM."
    ),
    
    PipelineTask.RAG: ModelTaskConfig(
        task=PipelineTask.RAG,
        model=ModelName.QWEN_3_6,
        provider_options={"reasoning":{"effort":"none"}},
        temperature=0.2,
        max_tokens=2000,
        supports_structured_output=True,
        why=(
            "- Лучшая работа с русским языком\n"
            "- Достаточный размер контекста\n"
            "- Хорошее качество генерации"
        )
    ),
    
    PipelineTask.DEEP_INTERPRETATION: ModelTaskConfig(
        task=PipelineTask.DEEP_INTERPRETATION,
        model=ModelName.DEEPSEEK_V4_1,
        provider_options={"reasoning":{"effort":"low"}},
        temperature=0.3,
        max_tokens=6000,
        supports_structured_output=True,
        why=(
            "- DeepSeek сильнее в математических и финансовых рассуждениях, чем GLM\n"
            "- Kimi убираем совсем — она слабее с русским и финансовым контекстом\n"
            "- DeepSeek лучше «понимает» причинно-следственные связи в балансах"
        )
    ),
    
    PipelineTask.ORCHESTRATOR: ModelTaskConfig(
        task=PipelineTask.ORCHESTRATOR,
        model=ModelName.GLM_5_3,
        provider_options={"reasoning":{"effort":"low"}},
        temperature=0.1,
        max_tokens=1000,
        supports_structured_output=True,
        why=(
            "- GLM от Zhipu AI исторически лучше в function calling и структурированных задачах\n"
            "- Оркестратору важнее стабильность JSON-вывода и управление потоком, чем глубокие рассуждения"
        )
    ),
    
    PipelineTask.INTERACTIVE_CHAT: ModelTaskConfig(
        task=PipelineTask.INTERACTIVE_CHAT,
        model=ModelName.QWEN_3_6,
        provider_options={"reasoning":{"effort":"none"}},
        temperature=0.4,
        max_tokens=2000,
        supports_structured_output=False,
        why="Отличная русскоязычная связность и универсальность для диалогов."
    ),
}


class AIConfig:
    """Менеджер конфигурации и доступа к API."""
    
    def __init__(self):
        self.api_key: str = os.getenv("ALFA_HACK_API_KEY", os.getenv("OPENAI_API_KEY", "mock-token"))
        self.base_url: str = os.getenv("ALFA_HACK_API_BASE", "https://changellenge.up.railway.app/v1")
        self.timeout_sec: float = float(os.getenv("ALFA_API_TIMEOUT", "45.0"))
        self.max_retries: int = int(os.getenv("ALFA_API_RETRIES", "3"))

    def get_config_for_task(self, task: PipelineTask) -> ModelTaskConfig:
        """Получить конфигурацию модели для указанной задачи пайплайна."""
        return TASK_MODEL_MAPPING[task]

    def get_client_params(self, task: PipelineTask) -> Dict[str, Any]:
        """Параметры для инициализации вызова в OpenAI-совместимом SDK."""
        task_cfg = self.get_config_for_task(task)
        return {
            "model": task_cfg.model.value,
            "temperature": task_cfg.temperature,
            "max_tokens": task_cfg.max_tokens,
            "timeout": self.timeout_sec,
        }

    def print_architecture_summary(self):
        """Печать обоснования выбранной архитектуры нейросетей."""
        print("=" * 80)
        print("УТВЕРЖДЕННАЯ АРХИТЕКТУРА ИИ-МОДЕЛЕЙ (АЛЬФА ХАК)")
        print("=" * 80)
        for task, cfg in TASK_MODEL_MAPPING.items():
            print(f"\n[ЗАДАЧА]: {task.value}")
            print(f"  -> Модель: {cfg.model.value}")
            print(f"  -> Параметры: temp={cfg.temperature}, max_tokens={cfg.max_tokens}")
            print(f"  -> Почему выбрана:\n     " + cfg.why.replace("\n", "\n     "))
        print("\n" + "=" * 80)


# Синглтон конфигурации
config = AIConfig()
