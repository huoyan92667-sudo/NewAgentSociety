"""建立读取完整历史的一次调用偏好融合器。"""

from __future__ import annotations

from new_agent.llm import OpenAICompatibleLLM
from new_agent.llm import StructuredModelSettings
from new_agent.restaurant.business_facts import BusinessFactCatalog
from new_agent.restaurant.preference_fusion.fusion import PreferenceFusion
from new_agent.restaurant.tools import BusinessFactsTool


def build_preference_fusion(
    business_catalog: BusinessFactCatalog | None = None,
) -> PreferenceFusion:
    """复用项目现有模型配置，固定使用严格 JSON 和关闭随机性。"""

    generator = OpenAICompatibleLLM.from_environment(
        StructuredModelSettings(
            enabled=True,
            temperature=0.0,
            timeout_seconds=90,
            max_retries=2,
            max_tokens=8000,
            response_format_json=True,
            thinking="disabled",
        )
    )
    return PreferenceFusion(
        generator,
        business_tool=(
            None if business_catalog is None else BusinessFactsTool(business_catalog)
        ),
    )
