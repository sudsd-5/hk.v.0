"""拟人化操作：随机停顿、逐字输入（禁止 fill）。"""
import asyncio
import random

from playwright.async_api import Locator

import config


async def human_pause(min_sec: float | None = None, max_sec: float | None = None) -> None:
    lo = min_sec if min_sec is not None else config.ACTION_DELAY_MIN
    hi = max_sec if max_sec is not None else config.ACTION_DELAY_MAX
    await asyncio.sleep(random.uniform(lo, hi))


async def human_type(locator: Locator, text: str) -> None:
    """逐字输入，模拟真人打字。"""
    await locator.click()
    delay = random.randint(config.TYPE_DELAY_MIN_MS, config.TYPE_DELAY_MAX_MS)
    await locator.press_sequentially(text, delay=delay)
