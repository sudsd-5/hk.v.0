"""
学生 1：Playwright 上传与发布主逻辑。
"""
import asyncio
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, TypeVar
from urllib.parse import urljoin

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator, Page, TimeoutError as PlaywrightTimeout

import config
from browser_utils import open_browser
from exceptions import PublishError
from human_utils import human_pause, human_type
from logging_config import setup_logging
from models import PublishTask, TaskStatus
from group2_handoff import extract_video_id
from task_io import load_task, save_task

logger = setup_logging("publish")

_VIDEO_URL_HINTS = re.compile(r"(video/|modal_id=|/BV|/av)", re.I)
T = TypeVar("T")


async def _retry(
    name: str,
    fn: Callable[[], Awaitable[T]],
    *,
    retries: int | None = None,
) -> T:
    attempts = retries if retries is not None else config.MAX_RETRIES
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            return await fn()
        except (PlaywrightTimeout, PlaywrightError, PublishError) as e:
            last_err = e
            if i < attempts - 1:
                wait = config.RETRY_BACKOFF_SEC * (2**i)
                logger.warning("%s 第 %d/%d 次失败，%.0fs 后重试: %s", name, i + 1, attempts, wait, e)
                await asyncio.sleep(wait)
            else:
                raise PublishError(f"{name} 在 {attempts} 次尝试后仍失败: {e}") from e
    raise PublishError(f"{name} 失败") from last_err


async def _save_failure_screenshot(page: Page | None, stem: str) -> None:
    if page is None:
        return
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = config.LOGS_DIR / f"fail_{stem}_{ts}.png"
    try:
        await page.screenshot(path=str(path), full_page=True)
        logger.error("失败截图已保存: %s", path)
    except Exception as e:
        logger.error("截图保存失败: %s", e)


async def _wait_visible(page: Page, selector: str, timeout: int | None = None) -> Locator:
    loc = page.locator(selector).first
    await loc.wait_for(state="visible", timeout=timeout or config.DEFAULT_TIMEOUT_MS)
    return loc


async def _upload_video(page: Page, video_path: Path) -> None:
    if not video_path.is_file():
        raise PublishError(f"视频文件不存在: {video_path}")
    if video_path.stat().st_size < config.MIN_VIDEO_BYTES:
        raise PublishError(f"视频文件无效: {video_path}")

    async def do_upload() -> None:
        await page.goto(config.UPLOAD_URL, wait_until="domcontentloaded", timeout=config.DEFAULT_TIMEOUT_MS)
        await human_pause()
        file_input = await _wait_visible(page, config.SELECTORS["file_input"])
        await file_input.set_input_files(str(video_path))
        logger.info("已选择视频: %s", video_path.name)

    await _retry("上传视频文件", do_upload)


async def _wait_upload_ready(page: Page) -> None:
    async def wait_ready() -> None:
        await _wait_visible(
            page,
            config.SELECTORS["title_input"],
            timeout=config.UPLOAD_WAIT_TIMEOUT_MS,
        )

    await _retry("等待视频处理完成", wait_ready)


async def _fill_metadata(page: Page, title: str, tags: str) -> None:
    async def fill_title() -> None:
        if not title:
            return
        title_loc = await _wait_visible(page, config.SELECTORS["title_input"])
        await human_pause(0.5, 1.5)
        await human_type(title_loc, title)
        logger.info("已填写标题")

    await _retry("填写标题", fill_title)

    if tags:

        async def fill_tags() -> None:
            tags_loc = await _wait_visible(page, config.SELECTORS["tags_input"])
            await human_pause(0.5, 1.5)
            await human_type(tags_loc, tags)
            logger.info("已填写标签")

        try:
            await _retry("填写标签", fill_tags, retries=2)
        except PublishError:
            logger.warning("标签填写失败，继续发布（可能为非必填项）")


async def _click_publish(page: Page) -> None:
    async def do_publish() -> None:
        await human_pause()
        btn = await _wait_visible(page, config.SELECTORS["publish_btn"])
        await btn.click()
        logger.info("已点击发布")

    await _retry("点击发布", do_publish)


def _normalize_href(href: str, base: str) -> str:
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return urljoin(base, href)
    return href


async def _capture_video_url(page: Page) -> str | None:
    """发布后尽量抓取作品页 URL，供第二组监控评论。"""
    await human_pause(2, 4)

    selector = config.SELECTORS.get("video_link")
    if selector:
        try:
            link = page.locator(selector).first
            await link.wait_for(state="attached", timeout=15_000)
            href = await link.get_attribute("href")
            if href:
                url = _normalize_href(href.strip(), page.url)
                logger.info("从页面链接取得 video_url: %s", url)
                return url
        except (PlaywrightTimeout, PlaywrightError):
            logger.debug("未通过 video_link 选择器取得链接")

    if _VIDEO_URL_HINTS.search(page.url):
        logger.info("使用当前页 URL: %s", page.url)
        return page.url

    try:
        hrefs: list[str] = await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => e.href).filter(Boolean)",
        )
        for href in hrefs:
            if _VIDEO_URL_HINTS.search(href):
                url = _normalize_href(href, page.url)
                logger.info("从页面锚点取得 video_url: %s", url)
                return url
    except PlaywrightError:
        pass

    logger.warning("未能自动获取 video_url，第二组需在 outbox 中手动补链")
    return None


async def _wait_publish_success(page: Page) -> None:
    async def check() -> None:
        indicator = page.locator(config.SELECTORS["success_indicator"]).first
        await indicator.wait_for(state="visible", timeout=config.DEFAULT_TIMEOUT_MS)

    try:
        await _retry("等待发布成功", check, retries=2)
        logger.info("检测到发布成功标识")
    except PublishError:
        logger.warning("未检测到成功标识，等待 10s（请人工确认）")
        await asyncio.sleep(10)


async def publish_task(task: PublishTask) -> PublishTask:
    video_path = task.resolve_video_path()
    stem = video_path.stem
    running = task.touch(status=TaskStatus.RUNNING, error=None)
    save_task(running)
    page_ref: Page | None = None

    try:
        async with open_browser() as (_, _ctx, page):
            page_ref = page
            await _upload_video(page, video_path)
            logger.info("等待视频转码...")
            await _wait_upload_ready(page)
            await human_pause(1, 2)
            await _fill_metadata(page, task.title, task.tags)
            await _click_publish(page)
            await _wait_publish_success(page)
            video_url = await _capture_video_url(page)

        vid = extract_video_id(video_url or "", config.PLATFORM)
        success = running.touch(
            status=TaskStatus.SUCCESS,
            error=None,
            video_url=video_url,
            video_id=vid,
            platform=config.PLATFORM,
        )
        save_task(success)
        logger.info("发布成功: %s | url=%s", stem, video_url or "(未捕获)")
        return success

    except Exception as e:
        await _save_failure_screenshot(page_ref, stem)
        failed = running.touch(status=TaskStatus.FAILED, error=str(e))
        save_task(failed)
        raise PublishError(str(e)) from e


async def publish_from_json() -> PublishTask:
    task = load_task()
    if task is None:
        raise PublishError(f"任务文件不存在: {config.TASK_FILE}")
    if task.status == TaskStatus.SUCCESS:
        logger.info("任务已是 success，跳过")
        return task
    return await publish_task(task)


def main() -> int:
    from preflight import run_preflight

    try:
        run_preflight()
        asyncio.run(publish_from_json())
        return 0
    except (PublishError, Exception) as e:
        logger.error("发布失败: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
