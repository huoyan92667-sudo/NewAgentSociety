"""从旧工程复制新 Agent 在线运行必需的数据，并记录逐文件校验值。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DataAsset:
    """一项旧数据与新项目数据位置的明确对应关系。"""

    name: str
    old_relative_path: Path
    new_relative_path: Path


ASSETS = (
    DataAsset(
        "business_facts",
        Path("src/yelp_agent/recommendation_v2/data/business_facts/v1"),
        Path("data/runtime/restaurants/business_facts/v1"),
    ),
    DataAsset(
        "category_catalog",
        Path("src/yelp_agent/recommendation_v2/data/category_catalog/v1"),
        Path("data/runtime/restaurants/category_catalog/v1"),
    ),
    DataAsset(
        "business_aspect_profiles",
        Path("src/yelp_agent/recommendation_v2/data/business_aspect_profiles/v1"),
        Path("data/runtime/restaurants/aspect_profiles/v1"),
    ),
    DataAsset(
        "user_profiles",
        Path("data/features/user_profiles/v1"),
        Path("data/runtime/users/profiles/v1"),
    ),
    DataAsset(
        "full_reviews",
        Path("data/processed/reviews.parquet"),
        Path("data/runtime/reviews/reviews.parquet"),
    ),
    DataAsset(
        "review_index",
        Path("src/yelp_agent/recommendation_v2/data/review_evidence/v1/index"),
        Path("data/runtime/reviews/index"),
    ),
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="迁移新 Agent 正式运行数据")
    parser.add_argument("--old-project", type=Path, required=True, help="旧工程根目录")
    parser.add_argument(
        "--new-project",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="new_agent 项目根目录",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="允许替换目标中同名文件；默认发现不同文件就停止",
    )
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    return sorted(path for path in source.rglob("*") if path.is_file())


def _copy_file(source: Path, target: Path, *, replace: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if source.stat().st_size == target.stat().st_size and _sha256(source) == _sha256(target):
            return
        if not replace:
            raise FileExistsError(f"目标文件不同，未覆盖：{target}")
    partial = target.with_name(target.name + ".partial")
    shutil.copy2(source, partial)
    os.replace(partial, target)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _arguments()
    old_root = args.old_project.resolve()
    new_root = args.new_project.resolve()
    records: list[dict[str, object]] = []
    for asset in ASSETS:
        source = old_root / asset.old_relative_path
        target = new_root / asset.new_relative_path
        if not source.exists():
            raise FileNotFoundError(f"缺少迁移来源：{source}")
        for source_file in _source_files(source):
            relative = Path(source_file.name) if source.is_file() else source_file.relative_to(source)
            target_file = target if source.is_file() else target / relative
            _copy_file(source_file, target_file, replace=args.replace)
            records.append(
                {
                    "asset": asset.name,
                    "path": target_file.relative_to(new_root).as_posix(),
                    "bytes": target_file.stat().st_size,
                    "sha256": _sha256(target_file),
                }
            )
            print(f"verified {asset.name}: {relative}", flush=True)

    # Qdrant 运行目录不能在服务运行时直接复制。它由 import_review_index.py
    # 从上面已校验的评论索引重新建立，避免得到损坏的数据库文件。
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "old_project": str(old_root),
        "new_project": str(new_root),
        "files": records,
        "qdrant": "rebuild_with_run/import_review_index.py",
    }
    output = new_root / "data" / "runtime" / "migration_manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"migration manifest: {output}")


if __name__ == "__main__":
    main()
