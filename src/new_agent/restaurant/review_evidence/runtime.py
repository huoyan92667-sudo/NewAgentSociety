"""建立新版评论证据排序需要的 Qdrant、本地向量模型和长尾描述模型。"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from new_agent.llm import OpenAICompatibleLLM
from new_agent.llm import StructuredModelSettings
from new_agent.paths import AgentPaths
from new_agent.restaurant.business_aspect_profiles import (
    BusinessAspectProfileCatalog,
    load_business_aspect_profile_catalog,
)
from new_agent.restaurant.review_evidence.retrieval_config import load_review_rag_config
from new_agent.retrieval.embedding import (
    LocalEmbeddingEnvironment,
    LocalQwenEmbeddingEncoder,
)
from new_agent.retrieval.embedding.config import load_local_embedding_environment

from .descriptions import PreferenceDescriptionBuilder
from .direct_search import DirectReviewEvidenceSearch
from .full_reviews import FullReviewStore
from .offline_aspects import OfflineAspectEvidenceResolver
from .qdrant_store import DEFAULT_COLLECTION_NAME, QdrantReviewSegmentStore
from .ranker import ReviewEvidenceRanker
from .retrieval import ReviewEvidenceRetriever
from .scoring import EvidenceScoringConfig
from .segment_vectors import ReviewSegmentVectorStore

@dataclass(frozen=True, slots=True)
class ReviewEvidenceCapabilities:
    """推荐排序和按商家查评论共享同一套模型、向量和Qdrant资源。"""

    ranker: ReviewEvidenceRanker
    direct_search: DirectReviewEvidenceSearch


class _LazyReviewEvidenceRetriever:
    """只有出现固定14项以外的自由要求时，才启动向量模型和Qdrant。"""

    recall_threshold = 0.55
    acceptance_threshold = 0.60
    direction_margin = 0.05

    def __init__(self, factory: Callable[[], ReviewEvidenceRetriever]) -> None:
        self._factory = factory
        self._retriever: ReviewEvidenceRetriever | None = None

    def retrieve_many(self, *args: Any, **kwargs: Any):
        if self._retriever is None:
            self._retriever = self._factory()
        return self._retriever.retrieve_many(*args, **kwargs)

    def close(self) -> None:
        if self._retriever is not None:
            self._retriever.close()


def _local_embedding_environment() -> LocalEmbeddingEnvironment:
    """读取本地向量模型，禁止退回某台开发机的写死路径。"""

    configured = load_local_embedding_environment()
    if not configured.enabled:
        raise RuntimeError(
            "local review embedding model is not configured; set "
            "LOCAL_EMBEDDING_MODEL_PATH and LOCAL_EMBEDDING_PYTHON"
        )
    return configured


def build_review_evidence_ranker(
    *,
    qdrant_url: str | None = None,
    profile_catalog: BusinessAspectProfileCatalog | None = None,
    project_root: str | Path | None = None,
) -> ReviewEvidenceRanker:
    """建立真实运行时；固定14种不会调用大模型，只有长尾要求才会调用。"""

    return build_review_evidence_capabilities(
        qdrant_url=qdrant_url,
        profile_catalog=profile_catalog,
        project_root=project_root,
    ).ranker


def build_review_evidence_capabilities(
    *,
    qdrant_url: str | None = None,
    profile_catalog: BusinessAspectProfileCatalog | None = None,
    project_root: str | Path | None = None,
) -> ReviewEvidenceCapabilities:
    """建立共享评论能力，避免推荐和单店查询各加载一份本地向量模型。"""

    generator = OpenAICompatibleLLM.from_environment(
        StructuredModelSettings(
            enabled=True,
            temperature=0.0,
            timeout_seconds=120,
            max_retries=2,
            max_tokens=2500,
            response_format_json=True,
            thinking="disabled",
        )
    )
    retriever = _LazyReviewEvidenceRetriever(
        lambda: _build_dynamic_review_retriever(
            qdrant_url=qdrant_url,
            project_root=project_root,
        )
    )
    description_builder = PreferenceDescriptionBuilder(generator)
    scoring_config = EvidenceScoringConfig(
        acceptance_threshold=0.60,
        top_each_side=5,
        half_life_days=730,
    )
    ranker = ReviewEvidenceRanker(
        description_builder=description_builder,
        retriever=retriever,
        offline_aspects=OfflineAspectEvidenceResolver(
            profile_catalog or load_business_aspect_profile_catalog(project_root)
        ),
        scoring_config=scoring_config,
    )
    return ReviewEvidenceCapabilities(
        ranker=ranker,
        direct_search=DirectReviewEvidenceSearch(
            description_builder=description_builder,
            retriever=retriever,  # type: ignore[arg-type]
            scoring_config=scoring_config,
        ),
    )


def _build_dynamic_review_retriever(
    *,
    qdrant_url: str | None,
    project_root: str | Path | None,
) -> ReviewEvidenceRetriever:
    """建立昂贵的自由评论检索环境；固定14项不会调用这里。"""

    paths = AgentPaths.resolve(project_root)
    rag_config = load_review_rag_config(paths.review_retrieval_config)
    encoder = LocalQwenEmbeddingEncoder.from_environment(
        rag_config.semantic_config().model_copy(update={"batch_size": 16}),
        _local_embedding_environment(),
    )
    store = QdrantReviewSegmentStore.from_url(
        qdrant_url or os.environ.get("QDRANT_URL", "http://127.0.0.1:6335"),
        collection_name=os.environ.get(
            "QDRANT_COLLECTION", DEFAULT_COLLECTION_NAME
        ).strip()
        or DEFAULT_COLLECTION_NAME,
    )
    return ReviewEvidenceRetriever(
        store=store,
        encoder=encoder,
        segment_vectors=ReviewSegmentVectorStore(
            paths.review_index / "segment_embeddings.npy"
        ),
        full_reviews=FullReviewStore(paths.full_reviews),
        recall_threshold=0.55,
        acceptance_threshold=0.60,
        direction_margin=0.05,
        recall_each_side=15,
        initial_segment_group_size=15,
        middle_segment_group_size=30,
        final_segment_group_size=60,
        minimum_clear_evidence=5,
        search_concurrency=4,
        enable_bm25=True,
        rrf_k=60,
    )
