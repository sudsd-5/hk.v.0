"""
第一组共享配置：路径、平台选择器、超时与 OPSEC。
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
READY_DIR = PROJECT_ROOT / "ready_to_publish"
AUTH_DIR = PROJECT_ROOT / "auth"
LOGS_DIR = PROJECT_ROOT / "logs"
STORAGE_STATE_FILE = AUTH_DIR / "storage_state.json"
TASK_FILE = PROJECT_ROOT / "current_task.json"
LOG_FILE = PROJECT_ROOT / "published.log"
SCAN_REPORT_FILE = PROJECT_ROOT / "scan_report.json"

# ---------- 与第二组交接（outbox）----------
OUTBOX_DIR = PROJECT_ROOT / "outbox"
PUBLISHED_VIDEOS_JSONL = OUTBOX_DIR / "published_videos.jsonl"
LAST_PUBLISH_JSON = OUTBOX_DIR / "last_publish.json"
PLATFORM = "douyin"  # 第二组按平台选抓取逻辑：douyin / bilibili / ...

# ---------- 浏览器 ----------
HEADLESS = False
BROWSER_CHANNEL = None
VIEWPORT = {"width": 1280, "height": 900}
LOCALE = "zh-CN"

# ---------- 目标平台（默认：抖音创作者中心）----------
UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"
LOGIN_URL = "https://creator.douyin.com/"

SELECTORS = {
    "file_input": "input[type='file']",
    "title_input": (
        "textarea[placeholder*='标题'], "
        "input[placeholder*='标题'], "
        "div[data-placeholder*='标题'] textarea"
    ),
    "tags_input": (
        "input[placeholder*='标签'], "
        "input[placeholder*='话题'], "
        "motion.div[class*='tag'] input"
    ),
    "publish_btn": "button:has-text('发布'), button:has-text('发表')",
    "success_indicator": "text=发布成功, text=已发布, text=作品管理",
    # 发布后作品链接（按平台 F12 调整；第二组依赖 video_url）
    "video_link": (
        "a[href*='/video/'], "
        "a[href*='douyin.com/video'], "
        "a:has-text('查看作品'), "
        "a:has-text('前往发布')"
    ),
}

# ---------- OPSEC / 拟人化 ----------
ACTION_DELAY_MIN = 1.0
ACTION_DELAY_MAX = 3.0
TYPE_DELAY_MIN_MS = 80
TYPE_DELAY_MAX_MS = 220

# ---------- 超时与重试 ----------
DEFAULT_TIMEOUT_MS = 30_000
UPLOAD_WAIT_TIMEOUT_MS = 300_000
MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 2.0
PUBLISH_FLOW_RETRIES = 2  # 整段发布流程失败后重跑次数（学生 2）

# ---------- 扫描与校验（学生 2）----------
MIN_VIDEO_BYTES = 1024  # 小于 1KB 视为无效
MAX_TITLE_LEN = 100
STALE_TASK_MINUTES = 30  # running 超时回滚为 pending
ALLOWED_VIDEO_SUFFIXES = {".mp4"}
