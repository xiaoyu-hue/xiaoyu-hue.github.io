"""builder.pwa —— PWA 层：Service Worker 预缓存清单 / 离线页 / 响应头（机械搬运）。"""
from .io_utils import fail, read
from .paths import OFFLINE_TEMPLATE, SW_FILE
from .paths import POST_URL_RE

PRECACHE_START = "  // posts:start"
PRECACHE_END = "  // posts:end"

def render_sw(pages):
    """sw.js 的预缓存清单：文章那一段由目录生成，其余保持手写。

    此前加一篇文章要手动往这里补一行；忘了补，用户离线时就读不到这一篇，
    而且表现得很像「网络问题」，没人会想到是清单漏了。
    现在这段不一致会让 python3 build.py 直接报差异，藏不住。
    """
    text = read(SW_FILE)
    i = text.find(PRECACHE_START)
    j = text.find(PRECACHE_END, i)
    if i < 0 or j < 0:
        fail("sw.js 里找不到 posts:start / posts:end 标记，无法更新预缓存清单")
    nums = []
    for rel in pages:
        m = POST_URL_RE.match(rel)
        if m:
            nums.append(int(m.group(1)))
    lines = ["  '/blog/post-%d.html'," % n for n in sorted(nums)]
    # 标记行本身保留，只替换两行标记之间的内容
    return text[:i] + PRECACHE_START + "\n" + "\n".join(lines) + "\n" + text[j:]


def render_offline(pages):
    """离线页：文章入口列表由文章清单生成。

    此前这里是手抄的十几行 <li>，每加一篇文章都要手动补一行。忘了补的话，
    用户离线时就点不到那一篇，而且本地测试、线上构建都不会报任何错 ——
    属于「只有真断网了才会发现」的那类 bug。
    """
    tpl = read(OFFLINE_TEMPLATE)
    if "{{post-links}}" not in tpl:
        fail("离线页模板里找不到 {{post-links}} 占位符")
    items = []
    for rel, meta in pages.items():
        m = POST_URL_RE.match(rel)
        if m:
            items.append((int(m.group(1)), rel, meta))
    items.sort()                      # 离线页按编号正序，找起来顺着
    lines = ['      <li><a href="%s">%s</a></li>' % (rel, meta["_h1"])
             for _num, rel, meta in items]
    return tpl.replace("{{post-links}}", "\n".join(lines))

def render_headers(site):
    """生成 Cloudflare Pages / Netlify 用的响应头文件。

    GitHub Pages 不支持自定义响应头，这个文件在那里不生效（README 里已说明）。
    """
    # 原文件的写法是 "... form-action 'none'; frame-ancestors 'none'"，注意 'none' 后有分号
    csp = site["csp_meta"] + "; frame-ancestors 'none'"
    return (
        "/*\n"
        "  X-Content-Type-Options: nosniff\n"
        "  X-Frame-Options: DENY\n"
        "  Referrer-Policy: strict-origin-when-cross-origin\n"
        "  Permissions-Policy: geolocation=(), microphone=(), camera=(), payment=()\n"
        "  Cross-Origin-Opener-Policy: same-origin\n"
        "  Strict-Transport-Security: max-age=31536000\n"
        "  Content-Security-Policy: %s\n" % csp
    )
