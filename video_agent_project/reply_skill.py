import asyncio
import random
from playwright.async_api import Page


async def skill_reply_comment(page: Page, comment_id: str, text: str):
    """
    在指定评论下方进行拟人化回复。
    参数:
        page:       已登录的 Playwright 页面对象
        comment_id: 要回复的评论 ID
        text:       回复内容文本
    """
    # 安全铁律3：操作前随机停顿，模拟真人浏览
    await asyncio.sleep(random.uniform(1, 3))

    # 1. 定位并点击该评论的“回复”按钮
    #    （选择器需要根据你们实际平台修改）
    reply_btn = page.locator(f"div[data-comment-id='{comment_id}'] .reply-btn")
    await reply_btn.wait_for(state="visible", timeout=10000)
    await reply_btn.click()
    print(f"已点击评论 {comment_id} 的回复按钮")

    # 2. 等待回复输入框出现，并点击聚焦
    reply_input = page.locator(f"div[data-comment-id='{comment_id}'] .reply-input")
    await reply_input.wait_for(state="visible", timeout=5000)
    await reply_input.click()

    # 安全铁律2：拟人化逐字输入，严禁使用 fill()
    await reply_input.press_sequentially(text, delay=random.randint(100, 300))

    # 安全铁律3：提交前再次随机停顿
    await asyncio.sleep(random.uniform(1, 3))

    # 3. 点击提交按钮
    submit_btn = page.locator(f"div[data-comment-id='{comment_id}'] .reply-submit")
    await submit_btn.click()
    print(f"? 已回复评论 {comment_id}: {text}")