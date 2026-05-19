"""
本地调试：不打开浏览器，检查环境与素材状态。

用法:
  python debug.py
  python debug.py --fix-test   # 从 published.log 移除 test，便于重测
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import config


def check_python() -> bool:
    v = sys.version_info
    ok = v.major == 3 and v.minor >= 10
    print(f"[Python] {sys.version} {'OK' if ok else '需要 3.10+'}")
    return ok


def check_deps() -> bool:
    missing = []
    for pkg in ("pydantic", "playwright", "playwright_stealth"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[依赖] 缺少: {', '.join(missing)}")
        print("  修复: pip install -r requirements.txt")
        print("  若 playwright_stealth 报错，执行: pip install \"setuptools>=69,<81\"")
        return False
    print("[依赖] 核心包已安装")
    return True


def check_auth() -> None:
    if config.STORAGE_STATE_FILE.is_file():
        print(f"[登录] 已存在 {config.STORAGE_STATE_FILE.name}")
    else:
        print("[登录] 未登录 -> 请先运行: python login.py")


def check_ready_folder() -> None:
    p = config.READY_DIR
    print(f"[素材] 目录: {p}")
    if not p.exists():
        print("  目录不存在，将自动创建")
        return
    mp4s = list(p.glob("*.mp4"))
    txts = list(p.glob("*.txt"))
    print(f"  mp4: {len(mp4s)}  txt: {len(txts)}")
    for f in sorted(mp4s):
        size = f.stat().st_size
        txt = p / f"{f.stem}.txt"
        flag = "OK" if txt.is_file() and size >= config.MIN_VIDEO_BYTES else "问题"
        print(f"  [{flag}] {f.name} ({size} bytes)" + ("" if txt.is_file() else " 缺 txt"))


def check_published_log() -> None:
    stems = []
    if config.LOG_FILE.is_file():
        stems = [ln.strip() for ln in config.LOG_FILE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    print(f"[已发布记录] published.log: {stems or '(空)'}")
    if "test" in stems:
        print("  提示: test 已标记发布，run.py 会跳过 test.mp4")
        print("  重测: python debug.py --fix-test")


def run_scan() -> None:
    from scan_service import save_scan_report, scan_inventory

    report = scan_inventory()
    save_scan_report(report)
    s = report.to_dict()["summary"]
    print(f"[扫描] 可发布 {s['ready']} / 已发布 {s['published']} / 共 {s['total_videos']}")
    for item in report.items:
        if item.state.value != "published":
            print(f"  - {item.stem}: {item.state.value} {item.reason}")


def check_task_json() -> None:
    from task_io import load_task

    task = load_task()
    if task is None:
        print("[任务] current_task.json 不存在")
        return
    path = task.resolve_video_path()
    exists = path.is_file()
    print(f"[任务] status={task.status.value} video={task.video_path}")
    print(f"  文件存在: {exists}  url={task.video_url or '-'}")
    if not exists:
        print("  提示: 路径无效或素材已清空，请重新 python run.py --task-only")


def check_outbox() -> None:
    if not config.PUBLISHED_VIDEOS_JSONL.is_file():
        print("[第二组交接] outbox 尚无记录")
        return
    lines = config.PUBLISHED_VIDEOS_JSONL.read_text(encoding="utf-8").strip().splitlines()
    print(f"[第二组交接] {len(lines)} 条 -> {config.PUBLISHED_VIDEOS_JSONL.name}")


def fix_test_in_log() -> None:
    if not config.LOG_FILE.is_file():
        print("published.log 不存在，无需修复")
        return
    lines = [ln for ln in config.LOG_FILE.read_text(encoding="utf-8").splitlines() if ln.strip() != "test"]
    config.LOG_FILE.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print("已从 published.log 移除 test，可重新发布 test.mp4")


def main() -> int:
    parser = argparse.ArgumentParser(description="发布模块本地调试")
    parser.add_argument("--fix-test", action="store_true", help="允许重新测试 test 视频")
    args = parser.parse_args()

    if args.fix_test:
        fix_test_in_log()
        return 0

    print("=" * 50)
    print("第一组 调试检查")
    print("=" * 50)
    check_python()
    deps_ok = check_deps()
    check_auth()
    check_ready_folder()
    check_published_log()
    run_scan()
    check_task_json()
    check_outbox()
    print("=" * 50)
    if not deps_ok:
        print("先修复依赖，再运行: python login.py && python run.py")
        return 1
    print("扫描/任务检查完成。完整发布: python run.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
