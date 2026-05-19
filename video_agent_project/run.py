"""
第一组统一入口（学生 1 + 学生 2）

完整流程: 扫描 -> 预检 -> 浏览器发布 -> 写 published.log -> 写 outbox(第二组) -> 清空 ready_to_publish

用法:
  python run.py                 # 一键发布
  python run.py --scan-only     # 仅扫描，生成 scan_report.json
  python run.py --task-only     # 扫描并生成 current_task.json
  python run.py --publish-only  # 仅发布（需已有任务 JSON）
  python run.py --no-clear      # 成功后不清空文件夹
"""
import argparse
import asyncio
import sys
import time

import config
from clear_folder import clear_ready_folder
from exceptions import PublishError, ValidationError
from file_manager import generate_task, mark_published
from group2_handoff import export_after_publish
from logging_config import setup_logging
from models import PublishTask, TaskStatus
from scan_service import save_scan_report, scan_inventory

logger = setup_logging("run")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="第一组：自动发布 MVP")
    p.add_argument("--scan-only", action="store_true", help="仅扫描素材并输出报告")
    p.add_argument("--task-only", action="store_true", help="扫描并生成 current_task.json")
    p.add_argument("--publish-only", action="store_true", help="不重新扫描，直接发布")
    p.add_argument("--no-clear", action="store_true", help="成功后不清空 ready_to_publish")
    return p.parse_args()


def _publish_with_retries() -> PublishTask:
    from preflight import run_preflight
    from publish_video import publish_from_json

    last_err: Exception | None = None
    attempts = config.PUBLISH_FLOW_RETRIES

    for i in range(attempts):
        try:
            run_preflight()
            return asyncio.run(publish_from_json())
        except (PublishError, ValidationError) as e:
            last_err = e
            if i < attempts - 1:
                wait = config.RETRY_BACKOFF_SEC * (2**i)
                logger.warning("发布流程失败，%.0fs 后整段重试 (%d/%d): %s", wait, i + 1, attempts, e)
                time.sleep(wait)
            else:
                raise

    raise PublishError(str(last_err))


def main() -> int:
    args = parse_args()

    if args.scan_only:
        report = scan_inventory()
        save_scan_report(report)
        s = report.to_dict()["summary"]
        print(f"扫描完成: 可发布 {s['ready']} / 共 {s['total_videos']}")
        return 0

    if not args.publish_only:
        if generate_task() is None:
            return 0
        if args.task_only:
            print("任务 JSON 已生成，退出。")
            return 0

    try:
        result = _publish_with_retries()
    except (PublishError, ValidationError) as e:
        logger.error("流程终止: %s", e)
        return 1

    if result.status != TaskStatus.SUCCESS:
        logger.error("发布未成功: %s", result.status)
        return 1

    mark_published(str(result.resolve_video_path()))
    record = export_after_publish(result, result.video_url)
    logger.info(
        "第二组交接已写入 outbox（video_url=%s）",
        record.video_url or "空，需手动补全",
    )

    if not args.no_clear:
        clear_ready_folder()

    logger.info("第一组流程全部完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
