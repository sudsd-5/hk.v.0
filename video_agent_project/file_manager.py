"""
学生 2：任务生成、已发布记录（带文件锁）、对接扫描服务。
"""
from pathlib import Path

import config
from file_lock import file_lock
from logging_config import setup_logging
from models import PublishTask, TaskStatus
from scan_service import (
    load_published,
    pick_next_ready,
    save_scan_report,
    scan_inventory,
)
from task_io import save_task

logger = setup_logging("file_manager")

READY_DIR = config.READY_DIR.name
LOG_FILE = config.LOG_FILE.name
TASK_FILE = config.TASK_FILE.name


def _to_relative_path(abs_path: Path) -> str:
    return abs_path.resolve().relative_to(config.PROJECT_ROOT.resolve()).as_posix()


def save_published(file_stem: str) -> None:
    """追加已发布记录（去重 + 文件锁）。"""
    lock = config.LOG_FILE.with_suffix(config.LOG_FILE.suffix + ".lock")
    with file_lock(lock):
        published = load_published()
        if file_stem in published:
            logger.debug("已在发布记录中: %s", file_stem)
            return
        with open(config.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(file_stem + "\n")
    logger.info("已写入发布记录: %s", file_stem)


def scan_unpublished() -> tuple[str, str, str] | None:
    """兼容旧接口：返回 (绝对路径, title, tags)。"""
    report = scan_inventory()
    item = pick_next_ready(report)
    if item is None or item.video_path is None:
        skipped = [i for i in report.items if i.state.value not in ("ready", "published")]
        if skipped:
            for i in skipped:
                logger.warning("[%s] %s: %s", i.stem, i.state.value, i.reason)
        return None
    return str(item.video_path.resolve()), item.title, item.tags


def generate_task(write_report: bool = True) -> dict | None:
    """扫描并生成 current_task.json。"""
    report = scan_inventory()
    if write_report:
        save_scan_report(report)

    item = pick_next_ready(report)
    if item is None or item.video_path is None:
        logger.info("没有待发布的视频")
        return None

    task = PublishTask(
        video_path=_to_relative_path(item.video_path),
        title=item.title,
        tags=item.tags,
        status=TaskStatus.PENDING,
        error=None,
    )
    save_task(task)
    logger.info("任务已生成: %s -> %s", TASK_FILE, item.video_path.name)
    return task.model_dump()


def mark_published(video_path: str) -> None:
    stem = Path(video_path).stem
    save_published(stem)


if __name__ == "__main__":
    report = scan_inventory()
    save_scan_report(report)
    print(f"可发布: {len(report.ready_items)} 个")
    generate_task(write_report=False)
