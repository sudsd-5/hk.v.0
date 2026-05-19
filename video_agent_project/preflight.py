"""
学生 2：发布前检查（素材 + 登录态 + 任务状态）。
"""
import config
from exceptions import PublishError, ValidationError
from logging_config import setup_logging
from models import PublishTask, TaskStatus
from scan_service import recover_stale_task, validate_task_for_publish
from task_io import load_task

logger = setup_logging("preflight")


def run_preflight() -> PublishTask:
    """
    发布前必须通过的全部检查。
    返回可发布的 PublishTask。
    """
    recover_stale_task()

    task = load_task()
    if task is None:
        raise ValidationError(f"未找到任务文件: {config.TASK_FILE}，请先运行扫描生成任务")

    if task.status == TaskStatus.FAILED:
        logger.info("上次发布失败，将重试: %s", task.error)

    validate_task_for_publish(task)

    if not config.STORAGE_STATE_FILE.is_file():
        raise PublishError(
            "未找到登录态。请先执行: python login.py\n"
            f"期望路径: {config.STORAGE_STATE_FILE}"
        )

    logger.info("预检通过: %s | %s", task.video_path, task.title[:40])
    return task
