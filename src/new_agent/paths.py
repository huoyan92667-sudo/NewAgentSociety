"""集中管理新 Agent 的项目目录和正式数据位置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AgentPaths:
    """调用方只提供项目根目录，其余路径都由这里统一推导。"""

    project_root: Path

    @classmethod
    def resolve(cls, project_root: str | Path | None = None) -> AgentPaths:
        if project_root is not None:
            root = Path(project_root)
        else:
            configured = os.environ.get("NEW_AGENT_ROOT", "").strip()
            # 源码开发环境下，本文件位于 <root>/src/new_agent/paths.py。
            root = Path(configured) if configured else Path(__file__).resolve().parents[2]
        return cls(project_root=root.resolve())

    @property
    def runtime_data(self) -> Path:
        return self.project_root / "data" / "runtime"

    @property
    def business_facts(self) -> Path:
        return self.runtime_data / "restaurants" / "business_facts" / "v1"

    @property
    def category_catalog(self) -> Path:
        return self.runtime_data / "restaurants" / "category_catalog" / "v1"

    @property
    def business_aspect_profiles(self) -> Path:
        return self.runtime_data / "restaurants" / "aspect_profiles" / "v1"

    @property
    def user_profiles(self) -> Path:
        return self.runtime_data / "users" / "profiles" / "v1"

    @property
    def full_reviews(self) -> Path:
        return self.runtime_data / "reviews" / "reviews.parquet"

    @property
    def review_index(self) -> Path:
        return self.runtime_data / "reviews" / "index"

    @property
    def review_retrieval_config(self) -> Path:
        return self.project_root / "configs" / "review_retrieval.yaml"

    @property
    def run_artifacts(self) -> Path:
        return self.project_root / "runs" / "artifacts"

