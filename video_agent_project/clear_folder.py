"""发布后清空 ready_to_publish；支持同步清理发布记录。"""
import argparse
import sys
from pathlib import Path

import config
from file_lock import file_lock
from scan_service import load_published


def clear_ready_folder() -> int:
    p = config.READY_DIR
    if not p.exists():
        print(f"{config.READY_DIR.name} 不存在，无需清空。")
        return 0
    count = 0
    for file in p.iterdir():
        if file.is_file():
            file.unlink()
            count += 1
    print(f"已清空 {config.READY_DIR.name}（删除 {count} 个文件）")
    return count


def remove_stems_from_log(stems: set[str]) -> None:
    """从 published.log 移除指定主干（清空文件夹且希望重新发布同名文件时使用）。"""
    if not stems or not config.LOG_FILE.is_file():
        return
    lock = config.LOG_FILE.with_suffix(config.LOG_FILE.suffix + ".lock")
    with file_lock(lock):
        lines = config.LOG_FILE.read_text(encoding="utf-8").splitlines()
        kept = [ln for ln in lines if ln.strip() and ln.strip() not in stems]
        config.LOG_FILE.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    print(f"已从 published.log 移除: {', '.join(sorted(stems))}")


def clear_folder_and_optional_log(reset_log: bool) -> None:
    stems: set[str] = set()
    if reset_log and config.READY_DIR.exists():
        for f in config.READY_DIR.glob("*.mp4"):
            stems.add(f.stem)
    clear_ready_folder()
    if reset_log:
        remove_stems_from_log(stems)


def main() -> int:
    parser = argparse.ArgumentParser(description="清空待发布文件夹")
    parser.add_argument(
        "--reset-log",
        action="store_true",
        help="同时从 published.log 移除该文件夹内视频的记录",
    )
    parser.add_argument("-y", "--yes", action="store_true", help="跳过确认")
    args = parser.parse_args()

    if not args.yes:
        msg = "确认清空 ready_to_publish"
        if args.reset_log:
            msg += " 并重置这些视频的发布记录"
        confirm = input(f"{msg}？(y/n): ")
        if confirm.lower() != "y":
            print("已取消")
            return 0

    clear_folder_and_optional_log(args.reset_log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
