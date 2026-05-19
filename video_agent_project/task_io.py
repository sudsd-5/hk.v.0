"""任务 JSON 读写（学生 1 发布流程使用）。"""
import json
from pathlib import Path

import config
from models import PublishTask, TaskStatus


def load_task(path: Path | None = None) -> PublishTask | None:
    p = path or config.TASK_FILE
    if not p.is_file():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return PublishTask.model_validate(json.load(f))


def save_task(task: PublishTask, path: Path | None = None) -> None:
    p = path or config.TASK_FILE
    with open(p, "w", encoding="utf-8") as f:
        json.dump(task.model_dump(), f, ensure_ascii=False, indent=2)


def set_task_status(
    status: TaskStatus,
    error: str | None = None,
    path: Path | None = None,
) -> PublishTask | None:
    task = load_task(path)
    if task is None:
        return None
    task = task.touch(status=status, error=error)
    save_task(task, path)
    return task
