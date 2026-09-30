#!/usr/bin/env python3
"""站点完整性检查：死链、CSP 一致性、第三方资源回归、内联脚本回归。

零依赖，直接用系统 python3 运行：
    python3 scripts/check_integrity.py

退出码 0 = 全部通过；1 = 有问题。
"""

import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECTED_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; "
    "img-src 'self' data:; connect-src 'none'; object-src 'none'; "
    "base-uri 'self'; form-action 'none'"
)
# 已知会被浏览器忽略的指令：禁止加回来（会制造虚假安全感）
FORBIDDEN_CSP_DIRECTIVES = ["frame-ancestors", "sandbox", "report-uri", "report-to"]

problems = []


def rel(p):
    return os.path.relpath(p, ROOT)


html_files = sorted(glob.glob(os.path.join(ROOT, "**", "*.html"), recursive=True))
md_files = sorted(glob.glob(os.path.join(ROOT, "*.md")))

if not html_files:
    problems.append("未找到任何 HTML 文件")

# ---------- 1. 内部链接可达性 ----------
skip_prefix = ("http://", "https://", "#", "mailto:", "data:", "javascript:")
for f in html_files + md_files:
    text = open(f, encoding="utf-8").read()
    links = re.findall(r'(?:href|src)="([^"]+)"', text)
    links += re.findall(r"\]\(([^)]+)\)", text)  # Markdown 链接
    for raw in links:
        if raw.startswith(skip_prefix):
            continue
        target = os.path.normpath(os.path.join(os.path.dirname(f), raw.split("#")[0]))
        if not os.path.exists(target):
            problems.append(f"[死链] {rel(f)} -> {raw}")

# ---------- 2. CSP 存在性与一致性 ----------
for f in html_files:
    text = open(f, encoding="utf-8").read()
    m = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]*)"', text)
    if not m:
        problems.append(f"[缺 CSP] {rel(f)} 没有 meta CSP")
        continue
    csp = m.group(1)
    if csp != EXPECTED_CSP:
        problems.append(f"[CSP 不一致] {rel(f)} 的策略与基准不同:\n    实际: {csp}\n    基准: {EXPECTED_CSP}")
    for d in FORBIDDEN_CSP_DIRECTIVES:
        if re.search(r"(^|[;\s])" + d + r"(\s|$)", csp):
            problems.append(
                f"[无效指令] {rel(f)} 的 CSP 含 '{d}' —— 该指令通过 <meta> 下发时会被浏览器忽略，"
                f"不会产生任何防护，请勿添加"
            )
    if "unsafe-inline" in csp or "unsafe-eval" in csp:
        problems.append(f"[策略放宽] {rel(f)} 的 CSP 含 unsafe-inline / unsafe-eval")
    if 'name="referrer"' not in text:
        problems.append(f"[缺 referrer] {rel(f)} 没有 meta referrer 策略")

# ---------- 3. 第三方资源回归 ----------
THIRD_PARTY = re.compile(r"(fonts\.(googleapis|gstatic)\.com|cdn\.|unpkg\.com|jsdelivr\.net)", re.I)
for f in html_files:
    text = open(f, encoding="utf-8").read()
    for m in THIRD_PARTY.finditer(text):
        problems.append(f"[第三方资源] {rel(f)} 引用了外部资源: {m.group(1)}")

# ---------- 4. 内联脚本 / 事件属性回归 ----------
for f in html_files:
    text = open(f, encoding="utf-8").read()
    if re.search(r"<script(?![^>]*\ssrc=)[^>]*>", text):
        problems.append(f"[内联脚本] {rel(f)} 含内联 <script>，会被 CSP 拦截")
    if re.search(r"\son[a-z]+\s*=", text, re.I):
        problems.append(f"[事件属性] {rel(f)} 含 on*= 内联事件属性，会被 CSP 拦截")
    if re.search(r'\sstyle\s*=\s*"', text):
        problems.append(f"[内联样式] {rel(f)} 含 style= 内联属性，会被 CSP 拦截（请改用 class）")

# ---------- 报告 ----------
print(f"检查范围: {len(html_files)} 个 HTML + {len(md_files)} 个 Markdown\n")
if problems:
    print(f"发现 {len(problems)} 个问题：\n")
    for p in problems:
        print(f"  ✗ {p}")
    sys.exit(1)

print("  ✓ 内部链接全部可达")
print("  ✓ 所有页面均带 CSP 且策略一致（无 unsafe-inline / unsafe-eval）")
print("  ✓ 无第三方外部资源")
print("  ✓ 无内联脚本 / 事件属性 / 内联样式")
print("\n全部通过 ✓")
