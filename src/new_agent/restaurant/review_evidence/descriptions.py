"""用当前问题改写评论检索说法，同时保持融合后的偏好含义不变。"""

from __future__ import annotations

import json
from typing import Protocol

from pydantic import Field, ValidationError

from new_agent.llm import LLMCallResult, LLMMessage
from new_agent.common.models import StrictModel
from new_agent.restaurant.review_evidence.aspect_definitions import (
    preference_semantic_anchors,
)
from new_agent.restaurant.schema import (
    ASPECT_FIELDS,
    OpenRequirement,
    SoftPreference,
)

from .schema import PreferenceSearchDescription


class DescriptionGenerator(Protocol):
    """长尾描述生成只依赖一次结构化大模型调用。"""

    def generate(self, messages: list[LLMMessage]) -> LLMCallResult: ...


class _SearchDescriptionItem(StrictModel):
    requirement_id: str = Field(min_length=1, max_length=200)
    positive_descriptions: list[str] = Field(min_length=2, max_length=2)
    negative_descriptions: list[str] = Field(min_length=2, max_length=2)


class _SearchDescriptionProposal(StrictModel):
    items: list[_SearchDescriptionItem]


class DescriptionBuildResult(StrictModel):
    """固定描述和一次长尾生成合并后的结果及模型用量。"""

    descriptions: list[PreferenceSearchDescription]
    call: LLMCallResult | None = None
    repair_call: LLMCallResult | None = None
    raw_json: str | None = None
    warning: str | None = Field(default=None, max_length=500)
    failure_reason: str | None = None

    @property
    def model_call_count(self) -> int:
        """包括首次生成和一次格式修正，供整轮词元统计使用。"""

        return int(self.call is not None) + int(self.repair_call is not None)

    @property
    def input_tokens(self) -> int | None:
        return self._known_usage("input_tokens")

    @property
    def output_tokens(self) -> int | None:
        return self._known_usage("output_tokens")

    def _known_usage(self, field_name: str) -> int | None:
        calls = [item for item in (self.call, self.repair_call) if item is not None]
        if not calls:
            return None
        values = [getattr(item, field_name) for item in calls]
        # 任何一次调用没有返回用量，都不能把未知值伪装成零。
        if any(value is None for value in values):
            return None
        return sum(values)  # type: ignore[arg-type]


class PreferenceDescriptionBuilder:
    """让检索说法知道用户正在找什么，但不让模型改动偏好与顺序。"""

    def __init__(self, generator: DescriptionGenerator) -> None:
        self._generator = generator

    def build(
        self,
        preferences: list[SoftPreference],
        open_requirements: list[OpenRequirement],
        *,
        query_text: str | None = None,
    ) -> DescriptionBuildResult:
        fixed = [
            self._fixed_description(item)
            for item in sorted(preferences, key=lambda value: value.priority)
            if item.field in ASPECT_FIELDS
        ]
        long_tail = [
            item
            for item in sorted(
                open_requirements,
                key=lambda value: value.priority or 10_000,
            )
            if item.behavior in {"must_have", "prefer", "avoid"}
        ]
        # 没有当前问题时保留原来的固定锚点，方便离线工具和旧调用方使用。
        # 在线推荐一定传 query_text，因此固定偏好也会经过一次上下文改写。
        if not long_tail and not query_text:
            return DescriptionBuildResult(descriptions=fixed)

        messages = self._messages(query_text or "", fixed, long_tail)
        call = self._generator.generate(messages)
        if call.status != "success" or call.content is None:
            reason = _short_reason(
                call.failure_reason or "description_generation_failed"
            )
            if fixed and not long_tail:
                return DescriptionBuildResult(
                    descriptions=fixed,
                    call=call,
                    warning=f"使用固定检索说法：{reason}",
                )
            return DescriptionBuildResult(
                descriptions=fixed,
                call=call,
                failure_reason=reason,
            )
        try:
            proposal = _SearchDescriptionProposal.model_validate_json(call.content)
            expanded = self._validate_and_materialize(fixed, long_tail, proposal)
        except (ValidationError, ValueError) as first_error:
            reason = _short_reason(f"invalid search descriptions: {first_error}")
            # 当前只有固定14种偏好时，大模型改写失败不能让整轮推荐重跑。
            # 直接使用已经定义好的正反锚点，相关性稍弱但语义和方向可靠。
            if fixed and not long_tail:
                return DescriptionBuildResult(
                    descriptions=fixed,
                    call=call,
                    raw_json=call.content,
                    warning=f"使用固定检索说法：{reason}",
                )
            # 长尾要求没有可靠的固定锚点。把具体漏项或格式错误连同必须返回的
            # 编号交回同一个模型修正一次，比让外层 Agent 重新执行整个工具便宜。
            repair_call = self._generator.generate(
                self._repair_messages(
                    messages,
                    invalid_content=call.content,
                    validation_error=reason,
                    fixed=fixed,
                    long_tail=long_tail,
                )
            )
            if repair_call.status != "success" or repair_call.content is None:
                return DescriptionBuildResult(
                    descriptions=fixed,
                    call=call,
                    repair_call=repair_call,
                    raw_json=call.content,
                    failure_reason=_short_reason(
                        repair_call.failure_reason or "description_repair_failed"
                    ),
                )
            try:
                repaired = _SearchDescriptionProposal.model_validate_json(
                    repair_call.content
                )
                expanded = self._validate_and_materialize(
                    fixed,
                    long_tail,
                    repaired,
                )
            except (ValidationError, ValueError) as repair_error:
                return DescriptionBuildResult(
                    descriptions=fixed,
                    call=call,
                    repair_call=repair_call,
                    raw_json=repair_call.content,
                    failure_reason=_short_reason(
                        f"invalid repaired search descriptions: {repair_error}"
                    ),
                )
            return DescriptionBuildResult(
                descriptions=expanded,
                call=call,
                repair_call=repair_call,
                raw_json=repair_call.content,
                warning="检索说法的结构由模型修正了一次",
            )
        return DescriptionBuildResult(
            descriptions=expanded,
            call=call,
            raw_json=call.content,
        )

    @staticmethod
    def _fixed_description(preference: SoftPreference) -> PreferenceSearchDescription:
        anchors = preference_semantic_anchors(
            preference.field,  # type: ignore[arg-type]
            preference.direction,
        )
        return PreferenceSearchDescription(
            requirement_id=preference.key,
            requirement_text=preference.key,
            kind="fixed_aspect",
            priority=preference.priority,
            preference_strength=preference.preference_strength,
            positive_descriptions=anchors.satisfying,
            negative_descriptions=anchors.contradicting,
            preference=preference,
        )

    @staticmethod
    def _messages(
        query_text: str,
        fixed: list[PreferenceSearchDescription],
        long_tail: list[OpenRequirement],
    ) -> list[LLMMessage]:
        items = [
            {
                "requirement_id": item.requirement_id,
                "kind": "fixed_aspect",
                "field": item.preference.field if item.preference is not None else None,
                "direction": (
                    item.preference.direction if item.preference is not None else None
                ),
                "base_positive_descriptions": item.positive_descriptions,
                "base_negative_descriptions": item.negative_descriptions,
            }
            for item in fixed
        ]
        items.extend(
            {
                "requirement_id": item.key,
                "kind": "long_tail",
                "user_text": item.text,
                "behavior": item.behavior,
            }
            for item in long_tail
        )
        system = """
你只负责为英文 Yelp 评论生成语义检索说法，不推荐商家，也不判断评论真假。
你会同时看到用户当前问题和已经融合好的软偏好。一次处理全部要求，每项恰好输出2条英文正向描述和2条英文反向描述。
正向描述表示商家满足用户要求时评论可能表达的意思；反向描述表示商家违反用户要求时评论可能表达的意思。
若 behavior=avoid，正向描述应表达成功避开该问题，反向描述应表达出现了用户想避开的情况。
固定特征已经给出基础含义，你不能改变特征方向。当前问题中的具体菜品或菜系会改变特征含义时，应把它写进检索说法。例如用户想吃牛排且特征是菜品质量，应该检索牛排肉质、味道和熟度，而不是宽泛的“所有食物都很好”。
环境、拥挤、停车、服务等商家整体特征不需要生硬地绑定菜品名称，继续表达餐厅层面的真实含义。
同一方向的两条有固定分工：第一条写评论可能给出的直接总体结论；第二条必须写可观察的原因或表现，例如原料、做法、味道、熟度、花椒麻感、偏甜偏淡、说话是否要提高声音，不能再次使用一组抽象近义词重复第一条。两条反向描述也不能只在正向描述前添加not/no：第一条写直接否定结论，第二条写具体失败表现。描述应短而具体，同时适合向量检索和关键词检索，不得编造商家、评论或数值。
只返回严格 JSON：
{"items":[{"requirement_id":"原编号","positive_descriptions":["...","..."],"negative_descriptions":["...","..."]}]}
""".strip()
        return [
            LLMMessage(role="system", content=system),
            LLMMessage(
                role="user",
                content=json.dumps(
                    {"query_text": query_text, "items": items},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            ),
        ]

    @staticmethod
    def _repair_messages(
        messages: list[LLMMessage],
        *,
        invalid_content: str,
        validation_error: str,
        fixed: list[PreferenceSearchDescription],
        long_tail: list[OpenRequirement],
    ) -> list[LLMMessage]:
        """要求模型只修正结构，不允许合并、删除或改写需求编号。"""

        required_ids = [
            *(item.requirement_id for item in fixed),
            *(item.key for item in long_tail),
        ]
        correction = {
            "task": "只修正上一条输出的JSON结构，不重新解释用户需求",
            "validation_error": validation_error,
            "required_requirement_ids": required_ids,
            "rules": [
                "items必须逐项返回required_requirement_ids中的全部编号",
                "每个编号恰好出现一次，禁止合并、删除、增加或改名",
                "每项必须有2条英文positive_descriptions和2条英文negative_descriptions",
                "只返回JSON对象，不要Markdown和说明文字",
            ],
            "output_shape": {
                "items": [
                    {
                        "requirement_id": "原编号",
                        "positive_descriptions": ["英文说法1", "英文说法2"],
                        "negative_descriptions": ["英文说法1", "英文说法2"],
                    }
                ]
            },
        }
        return [
            *messages,
            LLMMessage(role="assistant", content=invalid_content),
            LLMMessage(
                role="user",
                content=json.dumps(correction, ensure_ascii=False, separators=(",", ":")),
            ),
        ]

    @staticmethod
    def _validate_and_materialize(
        fixed: list[PreferenceSearchDescription],
        long_tail: list[OpenRequirement],
        proposal: _SearchDescriptionProposal,
    ) -> list[PreferenceSearchDescription]:
        expected_ids = {
            *(item.requirement_id for item in fixed),
            *(item.key for item in long_tail),
        }
        received = {item.requirement_id: item for item in proposal.items}
        if set(received) != expected_ids or len(received) != len(proposal.items):
            raise ValueError("model must return every requirement exactly once")
        result = [
            item.model_copy(
                update={
                    "positive_descriptions": received[
                        item.requirement_id
                    ].positive_descriptions,
                    "negative_descriptions": received[
                        item.requirement_id
                    ].negative_descriptions,
                },
                deep=True,
            )
            for item in fixed
        ]
        for requirement in long_tail:
            item = received[requirement.key]
            strengths = [
                basis.preference_strength
                for basis in requirement.sources
                if basis.preference_strength is not None
            ]
            result.append(
                PreferenceSearchDescription(
                    requirement_id=requirement.key,
                    requirement_text=requirement.text,
                    kind="long_tail",
                    priority=requirement.priority or 1,
                    preference_strength=max(
                        strengths,
                        default=(
                            100 if requirement.behavior == "must_have" else 75
                        ),
                    ),
                    positive_descriptions=item.positive_descriptions,
                    negative_descriptions=item.negative_descriptions,
                )
            )
        # 最终评论挑选也会沿用这里的顺序，所以必须让当前问题产生的第一
        # 优先要求真正排在画像和场景前面，不能只在打分公式里权重大。
        return sorted(result, key=lambda item: (item.priority, item.requirement_id))


def _short_reason(value: str, maximum: int = 450) -> str:
    """错误进入统一结果前先限长，避免错误说明本身再次触发校验失败。"""

    cleaned = " ".join(value.split())
    return cleaned if len(cleaned) <= maximum else cleaned[: maximum - 1] + "…"
