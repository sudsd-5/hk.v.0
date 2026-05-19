"""
第一组 -> 第二组 交接模块。

发布成功后写入:
  - outbox/published_videos.jsonl  （追加，第二组主输入）
  - outbox/last_publish.json       （最新一条，便于调试）

第二组约定:
  - 只读取 video_url 非空的记录
  - 用 comment_id 去重（第二组 SQLite 负责）
  - 处理完后可将 monitor_status 改为 monitoring / done（可选）
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import config
from file_lock import file_lock
from logging_config import setup_logging
from models import PublishTask, PublishedVideoRecord, utc_now

logger = setup_logging("group2_handoff")

# 常见平台作品 ID 从 URL 提取
_ID_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("douyin", re.compile(r"douyin\.com/video/(\d+)")),
    ("douyin", re.compile(r"modal_id=(\d+)")),
    ("bilibili", re.compile(r"/video/(BV[\w]+)")),
    ("bilibili", re.compile(r"/video/(av\d+)")),
]


def extract_video_id(video_url: str, platform: str | None = None) -> str | None:
    if not video_url:
        return None
    patterns = _ID_PATTERNS
    if platform:
        patterns = [(p, r) for p, r in _ID_PATTERNS if p == platform]
    for _, pattern in patterns:
        m = pattern.search(video_url)
        if m:
            return m.group(1)
    return None


def build_record(task: PublishTask, video_url: str | None) -> PublishedVideoRecord:
    stem = task.resolve_video_path().stem
    url = (video_url or "").strip()
    platform = task.platform or config.PLATFORM
    vid = task.video_id or extract_video_id(url, platform)
    return PublishedVideoRecord(
        platform=platform,
        video_url=url,
        video_id=vid,
        title=task.title,
        tags=task.tags,
        local_stem=stem,
        published_at=utc_now(),
        source="group1_publish",
        monitor_status="pending",
    )


def append_published_record(record: PublishedVideoRecord) -> Path:
    """追加一行 JSONL，并更新 last_publish.json。"""
    config.OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = config.PUBLISHED_VIDEOS_JSONL.with_suffix(".jsonl.lock")

    line = record.model_dump_json()
    with file_lock(lock_path):
        with open(config.PUBLISHED_VIDEOS_JSONL, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        with open(config.LAST_PUBLISH_JSON, "w", encoding="utf-8") as f:
            json.dump(record.model_dump(), f, ensure_ascii=False, indent=2)

    logger.info("已写入第二组交接: %s", config.PUBLISHED_VIDEOS_JSONL)
    if not record.video_url:
        logger.warning(
            "video_url 为空，第二组无法自动抓评论。"
            "请在 %s 中手动补全 video_url 后重跑监控。",
            config.LAST_PUBLISH_JSON,
        )
    return config.PUBLISHED_VIDEOS_JSONL


def export_after_publish(task: PublishTask, video_url: str | None) -> PublishedVideoRecord:
    """发布成功后由 run.py 调用。"""
    record = build_record(task, video_url)
    append_published_record(record)
    return record


def load_all_records() -> list[PublishedVideoRecord]:
    path = config.PUBLISHED_VIDEOS_JSONL
    if not path.is_file():
        return []
    records: list[PublishedVideoRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(PublishedVideoRecord.model_validate_json(line))
    return records


def load_pending_for_group2() -> list[PublishedVideoRecord]:
    """第二组可直接调用：待监控且 URL 有效的记录。"""
    return [
        r
        for r in load_all_records()
        if r.video_url and r.monitor_status in ("pending", "monitoring")
    ]


def print_handoff_summary() -> None:
    records = load_all_records()
    pending = load_pending_for_group2()
    print(f"交接文件: {config.PUBLISHED_VIDEOS_JSONL}")
    print(f"总记录: {len(records)}  |  待第二组处理(有URL): {len(pending)}")
    for r in records[-10:]:
        flag = "OK" if r.video_url else "缺少URL"
        print(f"  [{flag}] {r.local_stem} | {r.platform} | {r.video_url or '-'} | {r.monitor_status}")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="查看第一组->第二组交接记录")
    parser.add_argument("--list", action="store_true", help="列出 published_videos.jsonl")
    parser.add_argument("--pending", action="store_true", help="仅显示待监控记录")
    args = parser.parse_args()

    if args.pending:
        for r in load_pending_for_group2():
            print(r.model_dump_json())
        return 0

    print_handoff_summary()
    return 0


if __name__ == "__main__":
    sys.exit(main())
