"""防止新项目在后续修改中偷偷重新依赖旧 Agent。"""

from __future__ import annotations

import ast
from pathlib import Path

from new_agent.paths import AgentPaths


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "new_agent"


def test_new_source_does_not_import_old_yelp_agent() -> None:
    """扫描真实语法树；注释或迁移说明里出现旧名称不会误报。"""

    violations: list[str] = []
    for path in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            if any(name == "yelp_agent" or name.startswith("yelp_agent.") for name in names):
                violations.append(str(path.relative_to(PROJECT_ROOT)))

    assert violations == []


def test_default_runtime_paths_stay_inside_new_project() -> None:
    """默认数据目录必须从新项目推导，不能回退到某台电脑的绝对路径。"""

    paths = AgentPaths.resolve(PROJECT_ROOT)
    for path in (
        paths.runtime_data,
        paths.business_facts,
        paths.category_catalog,
        paths.business_aspect_profiles,
        paths.user_profiles,
        paths.full_reviews,
        paths.review_index,
        paths.run_artifacts,
    ):
        assert path.is_relative_to(PROJECT_ROOT)
