"""餐厅要求融合等结构化模型调用使用的精简配置。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Literal

from pydantic import Field, SecretStr

from new_agent.common.models import StrictModel


class StructuredModelSettings(StrictModel):
    """一次结构化模型调用真正需要的参数。"""

    enabled: bool = True
    temperature: Literal[0.0] = 0.0
    timeout_seconds: float = Field(default=120, gt=0)
    max_retries: int = Field(default=2, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    response_format_json: bool = False
    thinking: Literal["enabled", "disabled"] | None = None


class StructuredModelEnvironment(StrictModel):
    """从环境变量读取的模型地址；真实密钥不会进入日志。"""

    api_key: SecretStr | None = None
    base_url: str | None = None
    model: str | None = None

    @property
    def llm_enabled(self) -> bool:
        """只有密钥和模型名都存在时才允许发起结构化模型调用。"""

        return self.api_key is not None and bool(self.model)


def load_structured_model_environment(
    environment: Mapping[str, str] | None = None,
) -> StructuredModelEnvironment:
    """读取与主 Agent 相同的 OpenAI 兼容模型环境变量。"""

    if environment is None:
        from dotenv import load_dotenv

        load_dotenv()
        environment = os.environ

    def optional(name: str) -> str | None:
        value = environment.get(name, "").strip()
        return value or None

    api_key = optional("OPENAI_API_KEY")
    return StructuredModelEnvironment(
        api_key=SecretStr(api_key) if api_key else None,
        base_url=optional("OPENAI_BASE_URL"),
        model=optional("OPENAI_MODEL"),
    )
