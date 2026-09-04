"""模型适配接口及测试实现。"""

from .adapter import LanguageModel
from .fake import ScriptedLanguageModel
from .openai_compatible import AgentModelSettings, OpenAICompatibleAgentModel
from .structured import LLMCallResult, LLMMessage, OpenAICompatibleLLM
from .structured_settings import StructuredModelSettings

__all__ = [
    "AgentModelSettings",
    "LanguageModel",
    "OpenAICompatibleAgentModel",
    "OpenAICompatibleLLM",
    "ScriptedLanguageModel",
    "LLMCallResult",
    "LLMMessage",
    "StructuredModelSettings",
]
