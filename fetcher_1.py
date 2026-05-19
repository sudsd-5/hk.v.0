import json
import time
import hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright

# ===================== 用户配置区域 =====================
VIDEO_URL = "https://www.bilibili.com/video/BV1xx411c7mD"   # 目标视频URL
AUTHOR_SELECTOR = ".user-info .user-name"                  # 评论者ID的CSS选择器
CONTENT_SELECTOR = ".reply-content .text"                  # 评论内容的CSS选择器
WAIT_SELECTOR = ".reply-list"                              # 等待评论区域出现的选择器（可选）

INTERVAL = 60                       # 抓取间隔（秒）
OUTPUT_FILE = "comments.jsonl"      # 输出文件（JSON Lines）
SEEN_FILE = "seen_ids.txt"          # 已抓取评论ID记录
HEADLESS = True                     # 是否无头模式
SCROLL_TIMES = 2                    # 页面滚动次数（加载更多评论）
# ========================================================

def comment_id(author: str, content: str) -> str:
    """根据作者+内容生成唯一的评论ID（用于去重）"""
    raw = f"{author}_{content[:80]}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]

def load_seen() -> set:
    if Path(SEEN_FILE).exists():
        with open(SEEN_FILE, 'r') as f:
            return set(line.strip() for line in f)
    return set()

def save_seen(comment_id: str):
    with open(SEEN_FILE, 'a') as f:
        f.write(comment_id + "\n")

def save_comment(comment: dict):
    with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(comment, ensure_ascii=False) + "\n")

def fetch_comments():
    """使用 Playwright 抓取当前页面的所有评论"""
    comments = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()
        page.goto(VIDEO_URL, timeout=30000)
        
        # 等待评论区域加载
        if WAIT_SELECTOR:
            page.wait_for_selector(WAIT_SELECTOR, timeout=10000)
        page.wait_for_timeout(2000)
        
        # 滚动页面以加载动态评论
        for _ in range(SCROLL_TIMES):
            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
        
        # 提取作者和内容
        authors = page.query_selector_all(AUTHOR_SELECTOR)
        contents = page.query_selector_all(CONTENT_SELECTOR)
        
        # 按索引配对（假设页面中作者和内容元素顺序一致且数量相同）
        for idx in range(min(len(authors), len(contents))):
            author = authors[idx].inner_text().strip()
            content = contents[idx].inner_text().strip()
            if author and content:
                cid = comment_id(author, content)
                comments.append({
                    "comment_id": cid,
                    "author": author,
                    "content": content,
                    "fetch_time": time.strftime("%Y-%m-%d %H:%M:%S")
                })
        browser.close()
    return comments

def main():
    print("评论抓取模块启动，按 Ctrl+C 停止")
    seen = load_seen()
    while True:
        try:
            print(f"\n[{time.ctime()}] 抓取中...")
            new_comments = []
            for c in fetch_comments():
                if c["comment_id"] not in seen:
                    seen.add(c["comment_id"])
                    save_seen(c["comment_id"])
                    save_comment(c)
                    new_comments.append(c)
                    print(f"新评论：{c['author']} -> {c['content'][:50]}...")
            print(f"本次发现 {len(new_comments)} 条新评论")
        except Exception as e:
            print(f"出错：{e}")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
