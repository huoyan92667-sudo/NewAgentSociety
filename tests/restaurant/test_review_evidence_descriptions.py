from __future__ import annotations

import json

from new_agent.llm import LLMCallResult, LLMMessage
from new_agent.restaurant.review_evidence.descriptions import (
    PreferenceDescriptionBuilder,
)
from new_agent.restaurant.schema import OpenRequirement, RequirementBasis


class SequenceGenerator:
    """依次返回预设结果，并保留每次收到的消息供断言修正提示。"""

    def __init__(self, contents: list[str]) -> None:
        self._contents = contents
        self.calls: list[list[LLMMessage]] = []

    def generate(self, messages: list[LLMMessage]) -> LLMCallResult:
        index = len(self.calls)
        self.calls.append(list(messages))
        return LLMCallResult(
            status="success",
            content=self._contents[index],
            model="fake",
            latency_ms=10.0,
            attempt_count=1,
            input_tokens=10 + index,
            output_tokens=5 + index,
            total_tokens=15 + 2 * index,
        )


def _requirement(key: str, text: str, priority: int) -> OpenRequirement:
    return OpenRequirement(
        key=key,
        text=text,
        behavior="prefer",
        priority=priority,
        controlling_source="current_query",
        sources=[
            RequirementBasis(
                source="current_query",
                text=text,
                turn_index=1,
                preference_strength=75,
            )
        ],
    )


def test_invalid_description_output_is_repaired_inside_one_tool_call() -> None:
    """漏项时内部修正一次，不能迫使外层 Agent 重新执行整个评论工具。"""

    first = json.dumps(
        {
            "items": [
                {
                    "requirement_id": "dress.casual",
                    "positive_descriptions": ["casual clothes accepted", "relaxed attire"],
                    "negative_descriptions": ["formal dress required", "strict dress code"],
                }
            ]
        }
    )
    repaired = json.dumps(
        {
            "items": [
                {
                    "requirement_id": "dress.casual",
                    "positive_descriptions": ["casual clothes accepted", "relaxed attire"],
                    "negative_descriptions": ["formal dress required", "strict dress code"],
                },
                {
                    "requirement_id": "dress.formal",
                    "positive_descriptions": ["formal attire not required", "ordinary clothes welcome"],
                    "negative_descriptions": ["jacket required", "guest rejected for casual wear"],
                },
            ]
        }
    )
    generator = SequenceGenerator([first, repaired])
    result = PreferenceDescriptionBuilder(generator).build(
        [],
        [
            _requirement("dress.casual", "着装可以随意", 1),
            _requirement("dress.formal", "是否必须穿正装", 2),
        ],
        query_text="这家店需要穿正装吗？",
    )

    assert result.failure_reason is None
    assert [item.requirement_id for item in result.descriptions] == [
        "dress.casual",
        "dress.formal",
    ]
    assert result.model_call_count == 2
    assert result.input_tokens == 21
    assert result.output_tokens == 11
    assert len(generator.calls) == 2
    assert [message.role for message in generator.calls[1]] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    correction = json.loads(generator.calls[1][-1].content)
    assert correction["required_requirement_ids"] == [
        "dress.casual",
        "dress.formal",
    ]
