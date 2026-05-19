"""
首次使用：手动登录目标平台，保存 Cookie 到 auth/storage_state.json。
"""
import asyncio
import sys

import config
from browser_utils import open_browser, save_storage_state
from human_utils import human_pause
from logging_config import setup_logging

logger = setup_logging("login")


async def run_login() -> None:
    print("=" * 60)
    print("登录助手")
    print(f"1. 浏览器将打开: {config.LOGIN_URL}")
    print("2. 请手动完成登录（扫码 / 账号密码）")
    print("3. 确认已进入创作者后台后，回到终端按 Enter 保存登录态")
    print("=" * 60)

    async with open_browser() as (_, context, page):
        await page.goto(config.LOGIN_URL, wait_until="domcontentloaded")
        await human_pause(2, 4)
        input("\n>>> 登录完成后按 Enter 保存 Cookie...\n")
        await save_storage_state(context)
        logger.info("已保存登录态: %s", config.STORAGE_STATE_FILE)


def main() -> int:
    try:
        asyncio.run(run_login())
        return 0
    except KeyboardInterrupt:
        print("\n已取消")
        return 130


if __name__ == "__main__":
    sys.exit(main())
