"""核对独立 Agent 在线数据是否齐全，并生成不含机器绝对路径的校验清单。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq
from dotenv import load_dotenv
from qdrant_client import QdrantClient

from new_agent.paths import AgentPaths


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="验证独立 Agent 正式运行数据")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="new_agent 项目根目录",
    )
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parquet_rows(path: Path) -> int:
    return int(pq.ParquetFile(path).metadata.num_rows)


def _aspect_counts(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as connection:
        result: dict[str, int] = {}
        for table in ("supported_businesses", "aspect_scores", "reviews", "aspect_evidence"):
            result[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return result


def _qdrant_import_status(
    paths: AgentPaths,
    files: dict[str, dict[str, object]],
    *,
    expected_point_count: int,
) -> tuple[bool, dict[str, object] | None]:
    """同时核对导入清单、当前文件指纹和正在运行的 Qdrant 条数。"""

    manifest_path = paths.review_index.parent / "qdrant_hybrid_import_manifest.json"
    if not manifest_path.is_file():
        return False, None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, None
    manifest_matches = (
        manifest.get("segments_sha256") == files["review_segments"]["sha256"]
        and manifest.get("embeddings_sha256") == files["review_embeddings"]["sha256"]
        and manifest.get("point_count") == expected_point_count
    )
    details: dict[str, object] = {
        "manifest_path": manifest_path.relative_to(paths.project_root).as_posix(),
        "collection": manifest.get("collection_name"),
        "point_count": manifest.get("point_count"),
        "dimension": manifest.get("dimension"),
        "dense_vector_name": manifest.get("dense_vector_name"),
        "bm25_vector_name": manifest.get("bm25_vector_name"),
        "manifest_matches_runtime_files": manifest_matches,
    }
    if not manifest_matches or not isinstance(manifest.get("collection_name"), str):
        return False, details

    client = QdrantClient(
        url=os.environ.get("QDRANT_URL", "http://127.0.0.1:6335"),
        timeout=20,
    )
    try:
        information = client.get_collection(str(manifest["collection_name"]))
    except Exception as exc:  # noqa: BLE001 - 校验报告只保存安全的异常类型
        details["reachable"] = False
        details["live_error_type"] = type(exc).__name__
        return False, details
    finally:
        client.close()
    live_point_count = int(information.points_count or 0)
    details.update(
        {
            "reachable": True,
            "live_point_count": live_point_count,
            "collection_status": getattr(information.status, "value", str(information.status)),
        }
    )
    return live_point_count == expected_point_count, details


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    root = _arguments().project_root.resolve()
    load_dotenv(root / ".env")
    paths = AgentPaths.resolve(root)
    required = {
        "business_facts": paths.business_facts / "business_facts.parquet",
        "category_rows": paths.category_catalog / "categories.parquet",
        "category_catalog": paths.category_catalog / "catalog.json",
        "aspect_database": paths.business_aspect_profiles / "business_aspect_profiles.sqlite3",
        "aspect_directions": paths.business_aspect_profiles / "aspect_directions.json",
        "supported_businesses": paths.business_aspect_profiles / "supported_businesses.json",
        "profile_snapshots": paths.user_profiles / "profile_snapshots.parquet",
        "profile_preferences": paths.user_profiles / "preference_signals.parquet",
        "profile_task_map": paths.user_profiles / "task_profile_map.parquet",
        "full_reviews": paths.full_reviews,
        "review_segments": paths.review_index / "review_segments.parquet",
        "review_embeddings": paths.review_index / "segment_embeddings.npy",
    }
    missing = [str(path.relative_to(root)) for path in required.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("缺少在线数据：" + ", ".join(missing))

    files: dict[str, dict[str, object]] = {}
    for name, path in required.items():
        files[name] = {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        print(f"verified {name}", flush=True)

    counts = {
        "businesses": _parquet_rows(required["business_facts"]),
        "categories": _parquet_rows(required["category_rows"]),
        "profile_snapshots": _parquet_rows(required["profile_snapshots"]),
        "profile_preferences": _parquet_rows(required["profile_preferences"]),
        "profile_task_links": _parquet_rows(required["profile_task_map"]),
        "full_reviews": _parquet_rows(required["full_reviews"]),
        "review_segments": _parquet_rows(required["review_segments"]),
        **{f"aspect_{name}": count for name, count in _aspect_counts(required["aspect_database"]).items()},
    }
    qdrant_ready, qdrant = _qdrant_import_status(
        paths,
        files,
        expected_point_count=counts["review_segments"],
    )
    payload = {
        "schema_version": 2,
        "verified_at": datetime.now(UTC).isoformat(),
        "files": files,
        "record_counts": counts,
        "qdrant_ready": qdrant_ready,
    }
    if qdrant is not None:
        payload["qdrant"] = qdrant
    if not qdrant_ready:
        payload["qdrant_note"] = (
            "启动独立Qdrant后运行 run/import_review_index.py，"
            "再执行本校验确认在线条数"
        )
    output = paths.runtime_data / "verification_manifest.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False, indent=2))
    print(f"verification manifest: {output}")


if __name__ == "__main__":
    main()
