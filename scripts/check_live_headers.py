#!/usr/bin/env python3
"""线上安全头校验：确认部署后的站点真的返回了 _headers 里声明的安全头。

为什么需要这个脚本
------------------
仓库里有 `_headers` 文件（Cloudflare Pages 语法），但它的效果一直没被验证过。
一个配置文件"写对了"，不等于"真的生效了"：
  - Cloudflare Pages 的解析规则可能变（比如语法被弃用）
  - 部署平台可能换（GitHub Pages 根本不支持 _headers）
  - 中间的 CDN / 代理可能剥掉或改写响应头
这些都会让安全头静默失效，而页面上完全看不出来 —— 与 CSP/JSON-LD 那条结论
是同一类风险（出错时无声无息），所以同样值得放进 CI。

为什么不用 Mozilla Observatory
-----------------------------
Mozilla 的 HTTP Observatory 已于 2024-07 迁移到 MDN，旧的
`observatory.mozilla.org/api/v2/analyze` 端点已下线（实测返回 404）。
现行方案要么收费、要么需注册、要么托管在营销站点上，不适合塞进 CI，
更不适合让项目的门禁依赖一个随时可能关停的第三方服务。
改为自建：直接对线上 URL 发请求，断言我们自己声明的那组安全头是否真的存在。
零依赖、零外部服务、断言标准由本仓库自己掌握。

零依赖，直接用系统 python3 运行：
    python3 scripts/check_live_headers.py [站点URL]

不传 URL 时用默认线上地址。退出码 0 = 全部通过；1 = 有问题。
"""

import json
import os
import sys
import urllib.request
import urllib.error

# 线上站点。用 sitemap.xml 里登记的规范域名（Cloudflare Pages）。
DEFAULT_URL = "https://xiaoyu-hue-github-io.pages.dev/"

# CSP 的唯一真值来源（与 build.py、check_integrity.py 同源）。
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SITE = json.load(open(os.path.join(_ROOT, "src", "data", "site.json"), encoding="utf-8"))

# 期望的安全头，键为头名（小写），值为期望值。
# 这些值必须与仓库根目录的 `_headers` 文件保持一致；
# 哪边改了而另一边没改，就是本脚本要抓的不一致。
EXPECTED_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "cross-origin-opener-policy": "same-origin",
}

# 这些头只检查"存在且非空"，不比对精确值 ——
# 因为平台（Cloudflare）会追加/改写内容，精确比对会误报。
# 例如 HSTS 平台可能补 includeSubDomains，CSP 平台可能重排指令顺序。
EXPECTED_HEADERS_PREFIX = {
    "strict-transport-security": "max-age=",
}

# CSP 逐条指令校验：只要线上 CSP 里出现了这些指令且值一致即可，
# 不做整串精确比对（平台可能调整顺序或空白）。
#
# 指令表不手抄：直接从 src/data/site.json 的 csp_meta（CSP 唯一真值）解析，
# 再补上 frame-ancestors —— 它在 <meta> 里会被浏览器忽略、刻意不进 csp_meta，
# 但线上是通过 HTTP 头下发的，所以实际会带上，这里必须一起校验。
def _csp_directives():
    directives = {}
    for part in _SITE["csp_meta"].split(";"):
        part = part.strip()
        if not part:
            continue
        name, _, value = part.partition(" ")
        directives[name] = value.strip()
    directives["frame-ancestors"] = "'none'"
    return directives


EXPECTED_CSP_DIRECTIVES = _csp_directives()

# Permissions-Policy 是逗号分隔的特性列表，逐项检查存在性。
EXPECTED_PERMISSIONS = ["geolocation=()", "microphone=()", "camera=()", "payment=()"]

problems = []


def fetch_headers(url):
    """发 HEAD 请求拿响应头。HEAD 失败时退回 GET（有些平台不支持 HEAD）。"""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "header-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, dict(resp.headers), url
    except urllib.error.HTTPError as e:
        # HEAD 被拒（405 等）就退回 GET
        if e.code in (403, 405, 501):
            req = urllib.request.Request(url, method="GET", headers={"User-Agent": "header-check/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                # 只读头，立刻关闭，不下载正文
                result = (resp.status, dict(resp.headers), resp.url)
                resp.close()
                return result
        raise
    except Exception:
        # 网络类异常统一走 GET 再试一次
        req = urllib.request.Request(url, headers={"User-Agent": "header-check/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = (resp.status, dict(resp.headers), resp.url)
            resp.close()
            return result


def norm(headers):
    """把响应头整理成 {小写头名: 值}。"""
    return {k.lower(): v for k, v in headers.items()}


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL

    print(f"检查目标：{url}")

    try:
        status, headers, final_url = fetch_headers(url)
    except urllib.error.URLError as e:
        # 线上不可达时不应该让 CI 红叉：可能是临时网络抖动或站点维护。
        # 网络问题不是"安全头配错了"，两件事要分开，所以这里明确报错退出 1，
        # 但输出里写清是网络原因而非配置原因，便于排障时一眼区分。
        print(f"[网络错误] 无法访问站点：{e}")
        print("提示：这不代表安全头配置有问题；请先确认站点可达后重试。")
        sys.exit(1)

    h = norm(headers)
    print(f"HTTP {status}（最终 URL：{final_url}）\n")

    # 1) 精确值比对
    for name, want in EXPECTED_HEADERS.items():
        got = h.get(name)
        if got is None:
            problems.append(f"缺少安全头：{name}（期望 {want}）")
        elif got.strip().lower() != want.lower():
            problems.append(f"安全头值不符：{name} = {got!r}（期望 {want!r}）")

    # 2) 前缀/存在性比对
    for name, prefix in EXPECTED_HEADERS_PREFIX.items():
        got = h.get(name)
        if got is None:
            problems.append(f"缺少安全头：{name}（期望以 {prefix!r} 开头）")
        elif prefix.lower() not in got.lower():
            problems.append(f"安全头值不符：{name} = {got!r}（期望含 {prefix!r}）")

    # 3) CSP 逐指令
    csp = h.get("content-security-policy")
    if csp is None:
        problems.append("缺少安全头：content-security-policy")
    else:
        # 拆成 {指令名: 值}，忽略指令内部多余空白
        directives = {}
        for part in csp.split(";"):
            part = part.strip()
            if not part:
                continue
            bits = part.split(None, 1)
            directives[bits[0].lower()] = (bits[1].strip() if len(bits) > 1 else "")
        for name, want in EXPECTED_CSP_DIRECTIVES.items():
            got = directives.get(name)
            if got is None:
                problems.append(f"CSP 缺少指令：{name} {want}")
            elif " ".join(got.split()) != " ".join(want.split()):
                problems.append(f"CSP 指令值不符：{name} = {got!r}（期望 {want!r}）")

    # 4) Permissions-Policy 逐项
    pp = h.get("permissions-policy")
    if pp is None:
        problems.append("缺少安全头：permissions-policy")
    else:
        compact = pp.replace(" ", "").lower()
        for item in EXPECTED_PERMISSIONS:
            if item.replace(" ", "").lower() not in compact:
                problems.append(f"Permissions-Policy 缺少：{item}（实际 {pp!r}）")

    # 5) 附带确认：不应出现危险的过时头（它们会给虚假安全感）
    if "x-xss-protection" in h:
        problems.append(
            "出现已废弃的 x-xss-protection 头（现代浏览器忽略它，只会制造虚假安全感）"
        )

    if problems:
        print("发现问题：")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)

    print("全部安全头校验通过：")
    for name in list(EXPECTED_HEADERS) + list(EXPECTED_HEADERS_PREFIX) + ["content-security-policy", "permissions-policy"]:
        print(f"  [OK] {name}")


if __name__ == "__main__":
    main()
