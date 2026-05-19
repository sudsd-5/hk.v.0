"""浏览器启动、stealth、登录态持久化。"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright_stealth import stealth_async

import config


@asynccontextmanager
async def open_browser() -> AsyncIterator[tuple[Browser, BrowserContext, Page]]:
    config.AUTH_DIR.mkdir(parents=True, exist_ok=True)
    has_state = config.STORAGE_STATE_FILE.is_file()

    async with async_playwright() as pw:
        launch_kwargs = {"headless": config.HEADLESS}
        if config.BROWSER_CHANNEL:
            launch_kwargs["channel"] = config.BROWSER_CHANNEL

        browser = await pw.chromium.launch(**launch_kwargs)
        context_kwargs = {
            "viewport": config.VIEWPORT,
            "locale": config.LOCALE,
        }
        if has_state:
            context_kwargs["storage_state"] = str(config.STORAGE_STATE_FILE)

        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        await stealth_async(page)

        try:
            yield browser, context, page
        finally:
            await context.close()
            await browser.close()


async def save_storage_state(context: BrowserContext) -> None:
    config.AUTH_DIR.mkdir(parents=True, exist_ok=True)
    await context.storage_state(path=str(config.STORAGE_STATE_FILE))
