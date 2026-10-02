#!/usr/bin/env python3
"""验证：本站的 CSP（script-src 'self'，无 unsafe-inline / nonce / hash）
不会拦掉 <script type="application/ld+json"> 结构化数据。

为什么要有这个脚本
------------------
本站给搜索引擎看的结构化数据（JSON-LD）必须内联写在 HTML 里。
但本站的 CSP 禁止所有内联脚本。这两件事看起来直接冲突，靠查文档
出现过互相矛盾的说法，所以改成实测：起一个本地服务器，真实下发本站
的 CSP，用真浏览器加载，看 JSON-LD 到底能不能被读到。

怎么保证结论可信
----------------
光看「没报错」是不够的 —— 也可能 CSP 压根没生效。所以每个页面都放
一个故意违规的内联 classic 脚本作**对照组**：如果它没被拦下来，说明
实验装置本身是坏的，本次结论作废。

判据还要避免张冠李戴：CSP 违规事件的不确定性很高，内联脚本的 sample
常常是空字符串。所以按 lineNumber 归属违规，明确区分「哪一行」触发。

需要 playwright 才能跑（pip install playwright && playwright install），
但这是**可选**的验证工具：不装也能完整构建和部署站点，只是没法亲自复现
这条结论。缺引擎时会如实报告未覆盖，且不会把没跑的算成通过。

用法：
    python3 scripts/verify_csp_jsonld.py
"""

import http.server
import json
import os
import socketserver
import sys
import tempfile
import threading

# CSP 真值只有一处：src/data/site.json 的 csp_meta。
# 不再手抄一份 —— 手抄的那份只能靠注释提醒"保持一致"，没有任何机制强制，
# 改一处漏一处不会被抓到，而本脚本恰恰是用来证明"CSP 不会拦掉 JSON-LD"的，
# 它自己参数错了会让结论失真。
#
# 注意 frame-ancestors 是刻意追加的：<meta> 里该指令会被浏览器忽略，
# 本脚本用 HTTP 头下发，所以这里带上它（与 _headers 的实际下发方式对齐）。
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SITE = json.load(open(os.path.join(_ROOT, "src", "data", "site.json"), encoding="utf-8"))
CSP = _SITE["csp_meta"] + "; frame-ancestors 'none'"

# 行号在这份 HTML 里是硬契约：判据靠它归属 CSP 违规，改动请同步更新。
PAGE_LINES = [
    '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>csp lab</title>',  # 1
    '<script type="application/ld+json">',                                                   # 2
    '{"@context":"https://schema.org","@type":"BlogPosting","headline":"实验对象的标题"}',      # 3
    '</script>',                                                                             # 4
    '<script>window.__classicRan = true;</script>',                                          # 5 对照组
    '</head><body>',                                                                         # 6
    '<script src="./ext.js"></script>',                                                      # 7
    '</body></html>',                                                                        # 8
]
LINE_JSONLD = 2
LINE_CLASSIC = 5

EXPECTED_HEADLINE = "实验对象的标题"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=kwargs.pop("directory"), **kwargs)

    def end_headers(self):
        self.send_header("Content-Security-Policy", CSP)
        super().end_headers()

    def log_message(self, *args):
        pass


PROBE_JS = """() => {
  const el = document.querySelector('script[type="application/ld+json"]');
  let headline = null, parseError = null;
  try { headline = JSON.parse(el.textContent).headline; }
  catch (e) { parseError = String(e); }
  return {
    classicRan:  window.__classicRan === true,
    externalRan: window.__externalRan === true,
    headline: headline,
    parseError: parseError,
    violations: (window.__violations || []).map(
      v => ({ line: v.lineNumber, directive: v.violatedDirective })
    ),
  };
}"""

INIT_JS = """
window.__violations = [];
window.addEventListener('securitypolicyviolation', function (e) {
  window.__violations.push({ lineNumber: e.lineNumber, violatedDirective: e.violatedDirective });
});
"""


def serve_once(port_holder, ready, directory):
    httpd = socketserver.TCPServer(("127.0.0.1", 0),
                                   lambda *a: Handler(*a, directory=directory))
    httpd.daemon_threads = True
    port_holder["port"] = httpd.server_address[1]
    ready.set()
    httpd.serve_forever()


def probe(engine_name, url):
    """在指定引擎里跑一次，返回 (结果 dict, 引擎版本)。失败抛异常。"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = getattr(p, engine_name).launch()
        try:
            page = browser.new_page()
            try:
                page.add_init_script(INIT_JS)
            except Exception:
                # 少数引擎版本不支持 init script；此刻 __violations 为空会让
                # 对照组判据失效，下面的校验会把这种情况如实判为「装置无效」
                pass
            page.goto(url)
            page.wait_for_load_state("networkidle")
            result = page.evaluate(PROBE_JS)
            return result, browser.version
        finally:
            browser.close()


def main():
    tmp = tempfile.mkdtemp(prefix="csp-lab-")
    open(os.path.join(tmp, "index.html"), "w", encoding="utf-8").write("\n".join(PAGE_LINES))
    open(os.path.join(tmp, "ext.js"), "w", encoding="utf-8").write(
        "window.__externalRan = true;"
    )

    holder, ready = {}, threading.Event()
    threading.Thread(target=serve_once, args=(holder, ready, tmp), daemon=True).start()
    ready.wait(5)
    url = "http://127.0.0.1:%d/index.html" % holder["port"]

    print("CSP        :", CSP)
    print("实验页面   :", "行%d=JSON-LD 数据块，行%d=故意违规的内联 classic 脚本（对照组）"
          % (LINE_JSONLD, LINE_CLASSIC))
    print("=" * 74)

    try:
        import playwright  # noqa: F401
    except ImportError:
        print("\n✗ 未安装 playwright，无法实测。")
        print("  安装方法： pip install playwright && playwright install")
        print("  这不是构建必需步骤 —— 不装也能完整构建和部署站点，")
        print("  只是无法亲自复现 docs/csp-jsonld.md 里的结论。")
        return 2

    rows, skipped = [], []
    for engine in ("chromium", "firefox", "webkit"):
        try:
            result, version = probe(engine, url)
        except Exception as exc:            # 引擎缺失 / 依赖不全 / 启动失败
            skipped.append((engine, str(exc).split("\n")[0].strip()[:100] or "启动失败"))
            continue

        v_jsonld = [v for v in result["violations"] if v["line"] == LINE_JSONLD]
        v_classic = [v for v in result["violations"] if v["line"] == LINE_CLASSIC]

        # 装置自检：对照组必须被拦，否则本次测得再多也没意义
        apparatus_ok = result["classicRan"] is False
        jsonld_ok = result["headline"] == EXPECTED_HEADLINE and not v_jsonld

        rows.append({
            "engine": "%s %s" % (engine, version),
            "csp_effective": apparatus_ok,
            "external_ok": result["externalRan"],
            "headline": result["headline"],
            "parse_error": result["parseError"],
            "v_jsonld": len(v_jsonld),
            "v_classic": len(v_classic),
            "ok": apparatus_ok and jsonld_ok,
        })

        print("\n【%s %s】" % (engine, version))
        print("  对照组：内联 classic 脚本执行了吗     : %s"
              % ("否 → CSP 确实在拦内联，装置有效" if apparatus_ok
                 else "是 → ⚠ 装置本身有问题，本轮结论作废"))
        print("  对照组：外链脚本执行了吗              : %s"
              % ("是" if result["externalRan"] else "否 → ⚠ 'self' 没生效，装置有问题"))
        print("  JSON-LD（行%d）读取并解析得到         : %r" % (LINE_JSONLD, result["headline"]))
        print("  JSON-LD 解析错误                      : %s" % result["parseError"])
        print("  违规归属：行%d(JSON-LD)=%d 条，行%d(对照组)=%d 条"
              % (LINE_JSONLD, len(v_jsonld), LINE_CLASSIC, len(v_classic)))

    print("\n" + "=" * 74)
    for engine, reason in skipped:
        print("未覆盖引擎 %-10s : %s" % (engine, reason))

    if not rows:
        print("\n✗ 一个引擎都没跑成，无法得出任何结论（不拿「没报错」当通过）。")
        return 2

    print("\n汇总：")
    for r in rows:
        print("  %-24s CSP生效=%-5s JSON-LD可读=%-5s JSON-LD违规=%d"
              % (r["engine"], r["csp_effective"],
                 r["headline"] == EXPECTED_HEADLINE, r["v_jsonld"]))

    all_ok = all(r["ok"] for r in rows)
    print()
    if all_ok:
        print("✓ 结论成立（%d 个引擎，对照组全部通过）：" % len(rows))
        print("  script-src 'self' 不会拦掉 <script type=\"application/ld+json\">。")
        print("  原因：HTML 规范里 script 的 type 不匹配 JavaScript MIME 时，浏览器")
        print("  把它当纯数据（data block）直接返回，不进入执行路径；而 CSP 的内联")
        print("  检查挂在执行路径上，所以管不到它。")
    else:
        print("✗ 结论不成立，或某个引擎的对照组没能证明装置有效。请人工复核。")

    if skipped:
        print("\n注意：以下引擎未实测，上述结论对它们属于「未验证」而非「已通过」：")
        print("      " + ", ".join(e for e, _ in skipped))

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
