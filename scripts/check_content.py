#!/usr/bin/env python3
"""内容登记表校验的独立入口（CI 与本地均可单独运行）。

用法：
    python3 scripts/check_content.py    # 违约退出码 1
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from builder.validate import validate_site  # noqa: E402


def main():
    site = json.load(open(os.path.join(ROOT, "src", "data", "site.json"), encoding="utf-8"))
    pages = json.load(open(os.path.join(ROOT, "src", "data", "pages.json"), encoding="utf-8"))
    errors, warnings = validate_site(site, pages)
    for w in warnings:
        print("  ⚠ " + w)
    if errors:
        for e in errors:
            print("  ✗ " + e)
        print("\n内容登记表违约 %d 项" % len(errors))
        sys.exit(1)
    print("✓ 内容登记表校验通过（%d 个页面条目）" % len(pages))
    if warnings:
        sys.exit(0)


if __name__ == "__main__":
    main()
