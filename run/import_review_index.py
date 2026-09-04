"""把新项目已经准备好的评论片段和向量导入自己的 Qdrant。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from new_agent.paths import AgentPaths
from new_agent.restaurant.review_evidence.qdrant_store import (
    DEFAULT_COLLECTION_NAME,
    QdrantReviewSegmentStore,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导入独立 Agent 的评论向量库")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="new_agent 项目根目录",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=256,
        help="每批写入的评论片段数",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _arguments()
    root = args.project_root.resolve()
    load_dotenv(root / ".env")
    paths = AgentPaths.resolve(root)
    store = QdrantReviewSegmentStore.from_url(
        os.environ.get("QDRANT_URL", "http://127.0.0.1:6335"),
        collection_name=os.environ.get(
            "QDRANT_COLLECTION", DEFAULT_COLLECTION_NAME
        ).strip()
        or DEFAULT_COLLECTION_NAME,
    )
    try:
        # 入口故意不提供“删除并重建”参数，避免误删一个已有评论库。
        manifest = store.import_index(
            paths.review_index,
            batch_size=args.batch_size,
        )
    finally:
        store.close()
    verification_path = paths.runtime_data / "verification_manifest.json"
    if verification_path.is_file():
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        verification["qdrant_ready"] = True
        verification["qdrant"] = {
            "url": os.environ.get("QDRANT_URL", "http://127.0.0.1:6335"),
            "collection": manifest.collection_name,
            "point_count": manifest.point_count,
            "segments_sha256": manifest.segments_sha256,
            "embeddings_sha256": manifest.embeddings_sha256,
        }
        verification.pop("qdrant_note", None)
        verification_path.write_text(
            json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
