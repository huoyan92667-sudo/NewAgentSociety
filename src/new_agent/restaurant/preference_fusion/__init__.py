"""长期画像接入和四来源偏好融合的公开入口。"""

from new_agent.restaurant.preference_fusion.fusion import (
    PROMPT_VERSION,
    BusinessFactsFusionToolCall,
    CompactHardRequirement,
    CompactOpenRequirement,
    CompactReviewSearchPlan,
    CompactSceneSelection,
    CompactSearchCenter,
    CompactSoftRequirement,
    ConversationHistoryTurn,
    PreferenceCandidate,
    PreferenceFusion,
    PreferenceFusionAttempt,
    PreferenceFusionProposal,
    PreferenceFusionRequest,
    PreferenceFusionToolCall,
    RecommendationSnapshot,
)
from new_agent.restaurant.preference_fusion.profile_adapter import (
    ASPECT_DIRECTION_POLICY,
    IgnoredProfileSignal,
    ProfilePreferenceSet,
    adapt_user_profile,
)
from new_agent.restaurant.preference_fusion.runtime import (
    build_preference_fusion,
)
from new_agent.restaurant.tools.history_business import (
    HistoryBusinessFact,
    HistoryBusinessFactTool,
    HistoryFactObservation,
    HistoryFactQuery,
)

__all__ = [
    "ASPECT_DIRECTION_POLICY",
    "PROMPT_VERSION",
    "BusinessFactsFusionToolCall",
    "CompactHardRequirement",
    "CompactOpenRequirement",
    "CompactReviewSearchPlan",
    "CompactSceneSelection",
    "CompactSearchCenter",
    "CompactSoftRequirement",
    "ConversationHistoryTurn",
    "HistoryBusinessFact",
    "HistoryBusinessFactTool",
    "HistoryFactObservation",
    "HistoryFactQuery",
    "IgnoredProfileSignal",
    "PreferenceCandidate",
    "PreferenceFusion",
    "PreferenceFusionAttempt",
    "PreferenceFusionProposal",
    "PreferenceFusionRequest",
    "PreferenceFusionToolCall",
    "ProfilePreferenceSet",
    "RecommendationSnapshot",
    "adapt_user_profile",
    "build_preference_fusion",
]
