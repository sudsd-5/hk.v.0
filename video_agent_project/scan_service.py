"""
学生 2：本地扫描、校验、库存报告、僵死任务恢复。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import config
from exceptions import ScanError, ValidationError
from logging_config import setup_logging
from models import PublishTask, TaskStatus
from task_io import load_task, save_task

logger = setup_logging("scan")


class ItemState(str, Enum):
    READY = "ready"  # 可发布
    PUBLISHED = "published"  # 已在 published.log
    MISSING_TXT = "missing_txt"
    INVALID_VIDEO = "invalid_video"
    INVALID_TXT = "invalid_txt"


@dataclass
class VideoItem:
    stem: str
    video_path: Path | None
    txt_path: Path | None
    state: ItemState
    title: str = ""
    tags: str = ""
    reason: str = ""


@dataclass
class ScanReport:
    scanned_at: str
    ready_dir: str
    items: list[VideoItem] = field(default_factory=list)

    @property
    def ready_items(self) -> list[VideoItem]:
        return [i for i in self.items if i.state == ItemState.READY]

    def to_dict(self) -> dict:
        return {
            "scanned_at": self.scanned_at,
            "ready_dir": self.ready_dir,
            "summary": {
                "total_videos": len(self.items),
                "ready": len([i for i in self.items if i.state == ItemState.READY]),
                "published": len([i for i in self.items if i.state == ItemState.PUBLISHED]),
                "skipped": len(self.items)
                - len([i for i in self.items if i.state == ItemState.READY])
                - len([i for i in self.items if i.state == ItemState.PUBLISHED]),
            },
            "items": [
                {
                    "stem": i.stem,
                    "state": i.state.value,
                    "video_path": str(i.video_path) if i.video_path else None,
                    "txt_path": str(i.txt_path) if i.txt_path else None,
                    "title": i.title,
                    "tags": i.tags,
                    "reason": i.reason,
                }
                for i in self.items
            ],
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_published() -> set[str]:
    if not config.LOG_FILE.is_file():
        return set()
    try:
        with open(config.LOG_FILE, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    except OSError as e:
        raise ScanError(f"无法读取 {config.LOG_FILE}: {e}") from e


def validate_video_file(path: Path) -> None:
    if not path.is_file():
        raise ValidationError(f"视频不存在: {path}")
    if path.suffix.lower() not in config.ALLOWED_VIDEO_SUFFIXES:
        raise ValidationError(f"不支持的视频格式: {path.suffix}（仅 {config.ALLOWED_VIDEO_SUFFIXES}）")
    size = path.stat().st_size
    if size < config.MIN_VIDEO_BYTES:
        raise ValidationError(f"视频文件过小或为空 ({size} bytes): {path}")


def validate_txt_content(title: str, tags: str, stem: str) -> None:
    if not title.strip():
        raise ValidationError(f"{stem}.txt 第一行标题不能为空")
    if len(title) > config.MAX_TITLE_LEN:
        raise ValidationError(f"{stem}.txt 标题超过 {config.MAX_TITLE_LEN} 字")


def read_txt_meta(txt_path: Path) -> tuple[str, str]:
    try:
        text = txt_path.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise ScanError(f"无法读取文案: {txt_path}") from e
    lines = text.splitlines()
    title = lines[0].strip() if lines else ""
    tags = lines[1].strip() if len(lines) > 1 else ""
    return title, tags


def scan_inventory() -> ScanReport:
    """扫描 ready_to_publish，生成完整库存报告。"""
    ready_path = config.READY_DIR
    if not ready_path.exists():
        ready_path.mkdir(parents=True, exist_ok=True)
        logger.info("已创建 %s", ready_path)

    published = load_published()
    report = ScanReport(scanned_at=_utc_now(), ready_dir=str(ready_path))

    stems: set[str] = set()
    for video in sorted(ready_path.glob("*.mp4")):
        stems.add(video.stem)
    for txt in sorted(ready_path.glob("*.txt")):
        stems.add(txt.stem)

    for stem in sorted(stems):
        video_path = ready_path / f"{stem}.mp4"
        txt_path = ready_path / f"{stem}.txt"
        has_video = video_path.is_file()
        has_txt = txt_path.is_file()

        if stem in published:
            report.items.append(
                VideoItem(
                    stem=stem,
                    video_path=video_path if has_video else None,
                    txt_path=txt_path if has_txt else None,
                    state=ItemState.PUBLISHED,
                    reason="已在 published.log 中",
                )
            )
            continue

        if not has_video:
            continue

        if not has_txt:
            report.items.append(
                VideoItem(
                    stem=stem,
                    video_path=video_path,
                    txt_path=None,
                    state=ItemState.MISSING_TXT,
                    reason="缺少同名 .txt",
                )
            )
            continue

        try:
            validate_video_file(video_path)
        except ValidationError as e:
            report.items.append(
                VideoItem(
                    stem=stem,
                    video_path=video_path,
                    txt_path=txt_path,
                    state=ItemState.INVALID_VIDEO,
                    reason=str(e),
                )
            )
            continue

        try:
            title, tags = read_txt_meta(txt_path)
            validate_txt_content(title, tags, stem)
        except ValidationError as e:
            report.items.append(
                VideoItem(
                    stem=stem,
                    video_path=video_path,
                    txt_path=txt_path,
                    state=ItemState.INVALID_TXT,
                    reason=str(e),
                )
            )
            continue

        report.items.append(
            VideoItem(
                stem=stem,
                video_path=video_path,
                txt_path=txt_path,
                state=ItemState.READY,
                title=title,
                tags=tags,
            )
        )

    return report


def save_scan_report(report: ScanReport) -> Path:
    config.PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    with open(config.SCAN_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
    logger.info("扫描报告已写入 %s", config.SCAN_REPORT_FILE)
    return config.SCAN_REPORT_FILE


def pick_next_ready(report: ScanReport | None = None) -> VideoItem | None:
    report = report or scan_inventory()
    ready = report.ready_items
    if not ready:
        return None
    return ready[0]


def recover_stale_task() -> PublishTask | None:
    """将长时间处于 running 的任务回滚为 pending（进程崩溃恢复）。"""
    task = load_task()
    if task is None or task.status != TaskStatus.RUNNING:
        return task

    try:
        updated = datetime.strptime(task.updated_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        updated = datetime.now(timezone.utc)

    age_min = (datetime.now(timezone.utc) - updated).total_seconds() / 60
    if age_min < config.STALE_TASK_MINUTES:
        logger.warning("任务仍在 running（%.0f 分钟），请确认是否有其他进程在发布", age_min)
        return task

    recovered = task.touch(status=TaskStatus.PENDING, error=f"running 超时 {age_min:.0f}min，已回滚")
    save_task(recovered)
    logger.info("已回滚僵死任务为 pending: %s", task.video_path)
    return recovered


def validate_task_for_publish(task: PublishTask) -> None:
    """发布前校验（学生 2 对接学生 1）。"""
    path = task.resolve_video_path()
    validate_video_file(path)
    validate_txt_content(task.title, task.tags, path.stem)
    if task.status == TaskStatus.SUCCESS:
        raise ValidationError("任务已是 success，无需重复发布")
