"""
学生 2 交付：扫描 ready_to_publish，输出 scan_report.json。

用法:
  python scan.py
  python scan.py --json   # 仅打印 JSON 到 stdout
"""
import argparse
import json
import sys

from scan_service import save_scan_report, scan_inventory


def main() -> int:
    parser = argparse.ArgumentParser(description="扫描待发布素材并生成报告")
    parser.add_argument("--json", action="store_true", help="将报告打印到标准输出")
    args = parser.parse_args()

    report = scan_inventory()
    path = save_scan_report(report)

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        s = report.to_dict()["summary"]
        print(f"扫描完成 -> {path}")
        print(f"  视频总数: {s['total_videos']}")
        print(f"  可发布:   {s['ready']}")
        print(f"  已发布:   {s['published']}")
        print(f"  需处理:   {s['skipped']}")
        for item in report.items:
            if item.state.value == "ready":
                print(f"  [可发布] {item.stem}: {item.title[:40]}")
            elif item.state.value != "published":
                print(f"  [{item.state.value}] {item.stem}: {item.reason}")

    return 0 if report.ready_items or not report.items else 0


if __name__ == "__main__":
    sys.exit(main())
