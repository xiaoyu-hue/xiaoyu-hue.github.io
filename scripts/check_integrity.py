#!/usr/bin/env python3
"""站点完整性检查：死链、CSP 一致性、第三方资源回归、内联脚本回归。

零依赖，直接用系统 python3 运行：
    python3 scripts/check_integrity.py

退出码 0 = 全部通过；1 = 有问题。
"""

import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECTED_CSP = (
    "default-src 'self'; script-src 'self'; worker-src 'self'; style-src 'self'; "
    "font-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; "
    "base-uri 'self'; form-action 'none'"
)
# 已知会被浏览器忽略的指令：禁止加回来（会制造虚假安全感）
FORBIDDEN_CSP_DIRECTIVES = ["frame-ancestors", "sandbox", "report-uri", "report-to"]

problems = []


def rel(p):
    return os.path.relpath(p, ROOT)


# 测试工具链会在仓库内生成大量 .html（node_modules、Playwright 报告等）,
# 它们不是站点内容,必须排除,否则会被当成"缺 CSP 的页面"误报。
EXCLUDED_DIRS = {"node_modules", "playwright-report", "test-results", ".git"}


def is_excluded(path):
    parts = os.path.relpath(path, ROOT).split(os.sep)
    return any(part in EXCLUDED_DIRS for part in parts[:-1])


html_files = sorted(
    p for p in glob.glob(os.path.join(ROOT, "**", "*.html"), recursive=True)
    if not is_excluded(p)
)
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

# ---------- 5. PWA 资产完整性 ----------
# 这几项的故障表现都很隐蔽：manifest 写错时浏览器仍然"装得上"，
# 只是图标 404 或列表里显示成默认图标，控制台不报错。
MANIFEST = os.path.join(ROOT, "manifest.webmanifest")
SW = os.path.join(ROOT, "sw.js")
OFFLINE = os.path.join(ROOT, "offline.html")

if not os.path.exists(MANIFEST):
    problems.append("[缺 PWA] 没有 manifest.webmanifest")
else:
    try:
        with open(MANIFEST, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except json.JSONDecodeError as e:
        problems.append(f"[manifest 非法] 不是合法 JSON: {e}")
        manifest = None

    if manifest:
        for field in ("name", "short_name", "start_url", "scope", "display", "icons"):
            if field not in manifest:
                problems.append(f"[manifest 缺字段] 缺少 {field}")
        if manifest.get("scope") != "/":
            problems.append(f"[manifest scope] 应当是 /，实际 {manifest.get('scope')!r}")

        for icon in manifest.get("icons", []):
            src = icon.get("src", "")
            # 图标必须是绝对路径：用相对路径时 blog/ 下的页面会解析成
            # /blog/assets/...，404 且没有任何提示
            if not src.startswith("/"):
                problems.append(f"[图标路径] {src} 必须是绝对路径（以 / 开头）")
                continue
            target = os.path.join(ROOT, src.lstrip("/"))
            if not os.path.exists(target):
                problems.append(f"[图标缺失] manifest 里的 {src} 不存在")

if not os.path.exists(SW):
    # 最常见的错法就是把 sw.js 放进 assets/。先点破这一点,
    # 否则用户只看得到「没有 sw.js」,不知道该去哪找。
    if os.path.exists(os.path.join(ROOT, "assets", "sw.js")):
        problems.append(
            "[SW 位置错误] sw.js 出现在 assets/ 下，必须移到站点根目录 —— "
            "放在子目录会把作用域限制在 /assets/，页面导航将完全不走缓存"
        )
    else:
        problems.append("[缺 PWA] 没有 sw.js（Service Worker 必须在站点根目录）")
else:
    # 两处都有时会有一份是旧的，行为取决于浏览器先加载哪个，必须避免
    if os.path.exists(os.path.join(ROOT, "assets", "sw.js")):
        problems.append("[SW 位置错误] sw.js 同时存在于根目录和 assets/ 下，删掉 assets/ 里的那份")
    sw_src = open(SW, encoding="utf-8").read()
    m = re.search(r"const PRECACHE = \[(.*?)\];", sw_src, re.S)
    if not m:
        problems.append("[SW 缺清单] sw.js 里找不到 PRECACHE")
    else:
        for url in re.findall(r"'([^']+)'", m.group(1)):
            path = "index.html" if url == "/" else url.lstrip("/")
            if not os.path.exists(os.path.join(ROOT, path)):
                problems.append(f"[预缓存死链] sw.js 的 PRECACHE 里的 {url} 不存在")
    if not re.search(r"const CACHE_VERSION = 'v\d+'", sw_src):
        problems.append("[SW 缺版本] sw.js 里找不到形如 v1 的 CACHE_VERSION")

if not os.path.exists(OFFLINE):
    problems.append("[缺 PWA] 没有 offline.html（离线回退页）")

# 每个页面都要声明 manifest，否则浏览器不知道有这个应用清单
for f in html_files:
    text = open(f, encoding="utf-8").read()
    if 'rel="manifest"' not in text:
        problems.append(f"[缺 manifest 声明] {rel(f)} 没有 <link rel=\"manifest\">")
    tc = len(re.findall(r'<meta name="theme-color"', text))
    if tc != 2:
        problems.append(
            f"[theme-color] {rel(f)} 应有 2 个 theme-color（深/浅各一），实际 {tc}"
        )

# ---------- 6. 微动效系统完整性 ----------
# 这几项的故障表现都是「沉默失效」：CSS 不报错、JS 测试全绿，
# 只是浏览器里量 computed style 才发现动效没生效。
STYLE = os.path.join(ROOT, "assets", "style.css")
if not os.path.exists(STYLE):
    problems.append("[缺样式] 没有 assets/style.css")
else:
    css = open(STYLE, encoding="utf-8").read()

    # 令牌齐备：缺任何一个都会让对应动效静默失灵
    needed_tokens = [
        "--dur-fast", "--dur-base", "--dur-slow",
        "--shift-sm", "--shift-md", "--shift-lg",
        "--stagger-step",
    ]
    for token in needed_tokens:
        if token + ":" not in css:
            problems.append(f"[微动效] style.css 缺少令牌 {token}")

    # 总开关：全站唯一能把所有动效归零的地方
    if '[data-motion="off"]' not in css:
        problems.append("[微动效] style.css 缺少 html[data-motion=off] 总开关")

    # .reveal 的基础规则只能有一处。
    # 两处定义时靠源顺序决定谁生效，改了 A 坏了 B，极难排查。
    # 必须行首锚定：`.grid .reveal:nth-child(2){` 这类后代选择器
    # 也含 `.reveal`，用子串计数会误判。
    if len(re.findall(r"^\.reveal\{", css, re.M)) != 1:
        problems.append("[微动效] .reveal 的基础规则应当只有一处（行首匹配）")

    # 组件规则不许用 transition 简写去抢 .reveal 的属性轴。
    # transition 简写会把 transition-delay 一并重置为 0，
    # 卡片同时带 .card 与 .reveal 时就会把错落延迟冲掉 ——
    # 表现为「延迟全是 0，动效齐刷刷一起出现」。这条曾真实发生过。
    for selector in (".card,.post-card{",):
        idx = css.find(selector)
        if idx < 0:
            continue
        block = css[idx:css.find("}", idx)]
        if re.search(r"transition\s*:", block):
            problems.append(
                f"[微动效] {selector[:-1]} 用了 transition 简写，会重置 "
                f"transition-delay 并冲掉 .reveal 的错落延迟；"
                f"请改用 transition-property/-duration/-timing-function 长写"
            )

    # 三条纯 CSS 降级路径必须在场
    for path, label in (
        ("prefers-reduced-motion:reduce", "系统级「减少动画」"),
        ("prefers-contrast:more", "增强对比度"),
        ("scripting:none", "脚本不可用"),
    ):
        if path not in css:
            problems.append(f"[微动效] style.css 缺少降级路径：{label}")

    # 微动效系统块必须在文件末尾（同权重靠源顺序取胜，
    # 上移会被前面的基础规则反覆盖）
    pos = css.find("微动效系统")
    if pos < 0:
        problems.append("[微动效] style.css 里找不到「微动效系统」块")
    elif css.find(".prefs-panel.is-open", pos) < 0:
        problems.append("[微动效] 编排规则没有落在微动效系统块内（可能被上移了）")

# 每个页面都要有动效开关按钮，且 on / off 成对
for f in html_files:
    text = open(f, encoding="utf-8").read()
    if f.endswith("offline.html"):
        continue   # 离线页没有设置面板，属预期
    on = len(re.findall(r'data-motion-option="on"', text))
    off = len(re.findall(r'data-motion-option="off"', text))
    if (on, off) != (1, 1):
        problems.append(
            f"[微动效] {rel(f)} 的动效开关应有 on/off 各 1 个，实际 on={on} off={off}"
        )

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
print("  ✓ PWA：manifest 合法、图标齐全、Service Worker 在站点根目录")
print("  ✓ PWA：预缓存清单无死链，各页面均声明 manifest 与 theme-color")
print("  ✓ 微动效：令牌齐备、总开关在场、三条降级路径完整、无简写覆盖")
print("\n全部通过 ✓")
