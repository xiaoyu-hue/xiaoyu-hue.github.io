#!/usr/bin/env python3
"""站点构建脚本 —— 零依赖，只用 Python 标准库。

为什么存在：
    这个站原本是纯手写的 9 个 HTML 文件。每页有约 75 行完全相同的样板
    （head 的 meta/CSP/PWA、导航栏+设置面板、页脚、PWA 提示、脚本引用）。
    改一次导航要动 9 个文件，改一处 CSP 要动 9 个文件。

    这个脚本把重复的样板抽到 src/layouts/base.html，正文留在 src/pages/，
    再拼回一模一样的 HTML。**产物和你现在手写的那个版本逐字节一致** ——
    这是它的验收标准，不是目标。

用法：
    python3 build.py              # 构建到内存，与现有产物比对，报告差异（不写磁盘）
    python3 build.py --write      # 构建并覆盖写入 HTML 与 _headers
    python3 build.py --bootstrap  # 反向操作：从现有 HTML 生成 src/（首次迁移用）

设计原则：
    1. 零依赖 —— 只用标准库，不需要 pip install，不需要 node_modules
    2. 产物可验证 —— 非用意改动必须为零，脚本会逐字节比对并报错
    3. 未知即报错 —— 遇到不认识的东西说清楚，绝不静默产出可能错误的内容

模块结构（2026-10 拆分，函数体逐字节搬运、逻辑零改动）：
    builder/paths.py      路径常量与命名约定（ROOT 的计算随目录层级调整，已注明）
    builder/io_utils.py   文件读写、报错、构建目标发现
    builder/layout.py     Layout 模板类 / 路径变量 / canonical / 404 页
    builder/content.py    文章发现（目录即清单）/ 登记表合并 / 列表卡片
    builder/feeds.py      机器可读层：JSON-LD / sitemap / robots / RSS
    builder/pwa.py        SW 预缓存清单 / 离线页 / _headers
    builder/pipeline.py   build() 主管线
    builder/verify.py     产物比对 / 写入
    builder/bootstrap.py  反向生成 src/
    本文件                CLI 入口 + 兼容层（tests/test_build.py 通过 import build
                          使用若干函数名，故在此显式再导出）
"""

import sys

# ---- 兼容层：历史调用方（tests/test_build.py、check_integrity.py 等）
# 习惯 `import build` 后用 build.xxx，这里把拆分后的公开名原样再导出。
from builder.bootstrap import bootstrap
from builder.content import (CARD_TEMPLATE, derive_post_meta, discover_posts,
                             extract_body_date, first_paragraph, load_pages,
                             load_site, render_post_cards, strip_tags)
from builder.feeds import (absolutize_links, cdata_escape, json_ld_for,
                           json_ld_script, render_feed, render_head_extra,
                           render_robots, render_sitemap, rfc822_date,
                           xml_escape)
from builder.io_utils import fail, html_targets, read, write
from builder.layout import Layout, canonical_url, path_vars, render_404
from builder.paths import (DATA, EXIT_DIFF, EXIT_ERR, EXIT_OK, LAYOUT_FILE,
                           LAYOUTS, OFFLINE_TEMPLATE, PAGES_DIR, PAGES_JSON,
                           POST_BODY_RE, POST_URL_RE, ROOT, SITE_JSON, SRC,
                           SW_FILE)
from builder.pipeline import build
from builder.pwa import (PRECACHE_END, PRECACHE_START, render_headers,
                         render_offline, render_sw)
from builder.validate import validate_site
from builder.verify import compare, describe_diff, do_write


def main():
    args = sys.argv[1:]

    if "--bootstrap" in args:
        bootstrap()
        return

    site, pages = load_site()

    # 内容登记表校验（阶段4）：坏数据进不了构建
    v_errors, v_warnings = validate_site(site, pages)
    for w in v_warnings:
        print("  ⚠ " + w)
    if v_errors:
        for e in v_errors:
            print("  ✗ " + e)
        fail("内容登记表校验未通过（%d 项），请修正 src/data/ 后重试" % len(v_errors))

    outputs = build(site, pages)
    diffs = compare(outputs)

    if "--write" in args:
        do_write(outputs)
        return

    if not diffs:
        print("✓ 构建产物与现有文件逐字节一致（共 %d 个文件）" % len(outputs))
        print("  说明：目前 %d 份手抄样板已被 1 份模板替代，站点外观与行为没有任何变化。"
              % len(html_targets()))
        return

    print("✗ 构建产物与现有文件存在差异（%d 处）：\n" % len(diffs))
    for rel, why, _ in diffs:
        print("  %s\n    %s\n" % (rel, why))
    print("如果这些差异是有预期的（比如改了 base_url），用 --write 写入。")
    sys.exit(EXIT_DIFF)


if __name__ == "__main__":
    main()
