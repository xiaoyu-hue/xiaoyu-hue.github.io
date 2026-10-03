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
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
LAYOUTS = os.path.join(SRC, "layouts")
PAGES_DIR = os.path.join(SRC, "pages")
DATA = os.path.join(SRC, "data")

SITE_JSON = os.path.join(DATA, "site.json")
PAGES_JSON = os.path.join(DATA, "pages.json")
LAYOUT_FILE = os.path.join(LAYOUTS, "base.html")

# 站点上需要被这套流程管理的成品文件（相对仓库根）
HTML_TARGETS = ["index.html", "blog/index.html"] + [
    "blog/post-%d.html" % i for i in range(1, 9)
]

EXIT_OK, EXIT_DIFF, EXIT_ERR = 0, 1, 2


# ---------------------------------------------------------------- 小工具

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def fail(msg):
    print("[错误] " + msg, file=sys.stderr)
    sys.exit(EXIT_ERR)


# ---------------------------------------------------------------- 模板渲染

class Layout:
    """把 base.html 拆成 5 段，中间留两个可变量：导航区与正文。

    段的划分依据是原手写文件里天然存在的固定标记（见 bootstrap 的同名常量），
    这样模板和产物之间是一一对应的，不存在"渲染时才知道长什么样"的部分。
    """

    # 各段之间的锚点字符串（在原 HTML 中唯一）
    A_MAIN_OPEN = '<main id="main" tabindex="-1">\n'
    A_MAIN_CLOSE = '\n</main>\n'
    A_FOOTER_OPEN = '<footer><div class="wrap">\n'
    A_FOOTER_CLOSE = '\n</div></footer>\n'
    A_NAV_OPEN = '<nav class="nav" aria-label="主导航">'

    def __init__(self, text):
        self.raw = text
        i_nav = text.index(self.A_NAV_OPEN)
        i_main = text.index(self.A_MAIN_OPEN)
        i_mclose = text.index(self.A_MAIN_CLOSE)
        i_foot = text.index(self.A_FOOTER_OPEN)
        i_fclose = text.index(self.A_FOOTER_CLOSE)

        self.head = text[:i_nav]              # <!DOCTYPE> ... </head><body>装饰 div、跳转链接、空行
        self.nav = text[i_nav:i_main]         # <nav>...</nav> + 空行
        # main 的开闭标签：main_open 是 main 起始标签，main_close 是 </main> 与后续空行
        self.main_open = self.A_MAIN_OPEN
        self.main_close = self.A_MAIN_CLOSE
        self.footer_open = text[i_mclose + len(self.A_MAIN_CLOSE):i_foot + len(self.A_FOOTER_OPEN)]
        self.footer_close = self.A_FOOTER_CLOSE
        self.tail = text[i_fclose + len(self.A_FOOTER_CLOSE):]

        self._check()

    def _check(self):
        """模板自身必须完整，否则宁可不构建。"""
        for name in ("head", "nav", "footer_open", "tail"):
            if not getattr(self, name):
                fail("布局片段 %s 为空，模板可能被改坏了" % name)

    def render(self, vars_, content, footer_inner):
        """拼出一个完整 HTML。

        替换顺序是刻意的：先替换所有普通变量，最后才插入 {{content}}。
        这样即使正文里恰好出现了 {{...}} 字样，也不会被当成变量再展开一次。
        """
        if "{{content}}" not in self.raw:
            fail("模板里找不到 {{content}} 占位符")

        pieces = {
            "head": self.head,
            "nav": self.nav,
            "footer_open": self.footer_open,
            "tail": self.tail,
        }
        out = {}
        for k, v in pieces.items():
            # 先核对变量清单再替换。顺序很重要：JSON-LD 这类内容本身就带着 "}}"
            # 结尾（嵌套对象收尾），先替换后检查会把它们误判成未提供的变量。
            needed = set(re.findall(r"\{\{([a-z_]+)\}\}", v))
            missing = needed - set(vars_)
            if missing:
                fail("模板片段 %s 里有未提供的变量：%s" % (k, "、".join(sorted(missing))))
            for key, val in vars_.items():
                v = v.replace("{{%s}}" % key, val)
            out[k] = v

        # 独立处理 CSS 兜底：footer_inner / content 按字面插入，不做任何变量替换
        return "".join([
            out["head"],
            out["nav"],
            self.main_open,
            content,
            self.main_close,
            out["footer_open"],
            footer_inner,
            self.footer_close,
            out["tail"],
        ])


def path_vars(url_path):
    """根据页面在站点里的位置，算出所有相对路径变量。

    这条逻辑替代了原来每份 HTML 里手抄的相对路径，搬家时也不会写错。
    """
    # 导航高亮：处于博客区（blog/index.html 及各文章）时，给「博客」这一项
    # 加 aria-current="page"。首页各锚点（关于/项目/联系）指向首页本身，
    # 不是"当前页"，所以只有博客链接需要这个标记。
    # 前导空格是刻意的：模板里写成 href="{{blog}}"{{blog_current}}，
    # 非博客页为空串（不多出空格），博客页为 ' aria-current="page"'。
    blog_current = ' aria-current="page"' if url_path.startswith("blog/") else ""

    depth = url_path.count("/")
    if depth == 0:
        return {
            "rel": "",                      # 资源前缀： assets/style.css
            "home": "index.html",           # 品牌位回首页
            "anchor": "",                   # 首页锚点： #about
            "blog": "blog/index.html",      # 博客入口
            "blog_current": blog_current,   # 当前在博客区则加 aria-current
        }
    return {
        "rel": "../",
        "home": "../index.html",
        "anchor": "../index.html",
        "blog": "index.html",
        "blog_current": blog_current,
    }


def canonical_url(base_url, url_path):
    """首页的 canonical 以斜杠结尾，子页面拼完整路径 —— 与手写版本保持一致。

    别小看这个尾斜杠：canonical 字符串不一致会让搜索引擎把它当成两个不同的 URL，
    这正是这套流程要避免的那类问题。
    """
    return base_url + "/" if url_path == "" else "%s/%s" % (base_url, url_path)


# ---------------------------------------------------------------- 构建

def load_site():
    site = json.loads(read(SITE_JSON))
    pages = json.loads(read(PAGES_JSON))
    return site, pages


def build(site, pages):
    """返回 {输出相对路径: 文件内容}"""
    layout = Layout(read(LAYOUT_FILE))
    outputs = {}
    bodies = {}   # 正文片段：RSS 需要它来输出全文
    for rel_path, meta in pages.items():
        bodies[rel_path] = read(os.path.join(PAGES_DIR, meta["body"]))

    for rel_path, meta in pages.items():
        body_file = os.path.join(PAGES_DIR, meta["body"])
        content = read(body_file)

        # 声明了 date 的页面（文章）必须与正文里写的那处一致。列表页没有 date，跳过。
        if meta.get("date") is not None:
            body_date = extract_body_date(content)
            if body_date != meta["date"]:
                fail("%s：pages.json 记录的 date=%r，正文里写的却是 %r"
                     % (rel_path, meta["date"], body_date))

        v = dict(path_vars(meta["url_path"]))
        if meta.get("footer", "page") not in site["footers"]:
            fail("%s 引用了不存在的页脚变体：%s" % (rel_path, meta.get("footer")))
        v.update({
            "head_extra": render_head_extra(site, rel_path, meta),
            "title": meta["title"],
            "description": meta["description"],
            "canonical": canonical_url(site["base_url"], meta["url_path"]),
            "og_type": meta.get("og_type", "article"),
            "og_title": meta.get("og_title", meta["title"]),
            "og_description": meta.get("og_description", meta["description"]),
            "twitter_title": meta.get("twitter_title", meta["title"]),
            "twitter_description": meta.get("twitter_description", meta["description"]),
            "og_image_alt": meta.get("og_image_alt", meta["title"]),
            "base_url": site["base_url"],
            "csp": site["csp_meta"],
        })
        outputs[rel_path] = layout.render(
            v, content, site["footers"][meta.get("footer", "page")])

    # _headers 也一并生成，让 CSP 只有一个来源
    outputs["_headers"] = render_headers(site)

    # 机器可读层：此前全部缺失
    outputs["sitemap.xml"] = render_sitemap(site, pages)
    outputs["robots.txt"] = render_robots(site)
    outputs["feed.xml"] = render_feed(site, pages, bodies)
    outputs["404.html"] = render_404(layout, site, pages)
    return outputs


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


# ---------------------------------------------------------------- 机器可读层

# 这几个文件解决的是同一件事：让搜索引擎、RSS 阅读器、转发卡片能"读懂"这个站。
# 在此之前它们全部缺失——内容写得再好，通道是断的。


def extract_body_date(body):
    """从正文第一处 <div class="date"> 里取出 YYYY-MM-DD。

    日期目前仍写在正文里（步骤 2 的 Markdown 化会把它提到 frontmatter）。
    这里只是读取，不改动正文——避免还没到那一步就大改文章结构。
    """
    m = re.search(r'<div class="date">\s*(\d{4}-\d{2}-\d{2})', body)
    return m.group(1) if m else None


def xml_escape(s):
    """XML 转义。RSS 与 sitemap 都用得上，缺了会让带 & < > 的标题把整个源弄坏。"""
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def cdata_escape(text):
    """CDATA 分段转义：把正文里的 ]]> 拆开，避免它提前结束 CDATA 区、弄断 RSS。

    原理：把每个 ]]> 替换成 ]]]]><![CDATA[> —— 前者闭合旧 CDATA 区，
    紧接着再开一个新 CDATA 区，解析器看到的是同一段连续文本，但 ]]> 不再成对出现。
    正文恰含 ]]> 的概率极低（作者内容），但一旦命中就会让 feed.xml 在首个 ]]> 处断裂。
    """
    return text.replace("]]>", "]]]]><![CDATA[>")


def rfc822_date(iso_date):
    """2026-09-30 → Mon, 30 Sep 2026 00:00:00 GMT（RSS 规定的 RFC 822 格式）"""
    from datetime import datetime
    return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%a, %d %b %Y 00:00:00 GMT")


def absolutize_links(body, url_path, base_url):
    """把正文里的相对链接换成绝对地址。

    只在生成 RSS 时调用，不改动站点本身的 HTML。必要性在于：RSS 阅读器拿到的是
    一段脱离了页面上下文的 HTML，'post-8.html' 这种相对路径在它那里指向的是
    阅读器自己的域名，会全部变成死链。

    base_url 显式传入而不是读全局：此前它依赖模块级 BASE_URL_HOLDER，
    只有当 build() 先跑过才非空；否则静默产出 'None/blog/x.html' 这种
    坏链接 —— 不报错、不崩溃，坏了也看不见。
    """
    base_dir = url_path.rsplit("/", 1)[0] if "/" in url_path else ""
    base = ("%s/%s" % (base_url, base_dir)) if base_dir else base_url

    def fix(m):
        href = m.group(1)
        if href.startswith(("http", "#", "mailto:", "data:")):
            return m.group(0)
        return 'href="%s/%s"' % (base, href)

    return re.sub(r'href="([^"]+)"', fix, body)


def json_ld_for(rel_path, meta, site):
    """给每个页面生成结构化数据。

    首页是 WebSite + Person，文章是 BlogPosting，博客列表是 CollectionPage。
    搜索引擎靠它才能在搜索结果里显示面包屑、作者、发布时间；内容聚合器和 AI
    摘要工具也主要读这一层，而不是猜正文。
    """
    url = canonical_url(site["base_url"], meta["url_path"])
    if meta["og_type"] == "website":
        return [
            {"@context": "https://schema.org", "@type": "WebSite",
             "name": meta["title"], "url": site["base_url"] + "/",
             "description": meta["description"], "inLanguage": site.get("lang", "zh-CN"),
             "author": {"@type": "Person", "name": site.get("author", ""),
                        "url": "https://github.com/%s" % site.get("author", "")}},
        ]
    if rel_path == "blog/index.html":
        return [
            {"@context": "https://schema.org", "@type": "CollectionPage",
             "name": meta["title"], "description": meta["description"], "url": url,
             "isPartOf": {"@type": "WebSite", "url": site["base_url"] + "/"},
             "inLanguage": site.get("lang", "zh-CN")},
        ]

    item = {"@context": "https://schema.org", "@type": "BlogPosting",
            "headline": meta["title"], "description": meta["description"],
            "url": url, "inLanguage": site.get("lang", "zh-CN"),
            "author": {"@type": "Person", "name": site.get("author", "")}}
    if meta.get("date"):
        item["datePublished"] = meta["date"]
    return [item]


def json_ld_script(blob):
    """把结构化数据序列化成可以安全内联在 HTML 里的 <script> 内容。

    为什么不能直接用 json.dumps：JSON 允许字符串里出现 "<" 与 "/"，
    json.dumps 也不会转义它们，所以一个标题里只要含 "</script>"，
    序列化结果就会**提前闭合脚本块**，后面的内容被浏览器当成真正的
    HTML 解析 —— 攻击者可以在标题里夹带 <script> 执行任意脚本。

    标准做法是把 "<" 转义成 JSON 的 \\u003c：值仍然逐字节相等
    （json.loads 后与原文完全一致），但源码里再也出现不了 "</script>"。
    只转义 "<" 就够：脚本块只能被 "</script" 结束，而它必然含 "<"。
    """
    return json.dumps(blob, ensure_ascii=False,
                      separators=(",", ":")).replace("<", "\\u003c")


def render_head_extra(site, rel_path, meta):
    """塞进 </head> 之前的那几行：JSON-LD 脚本 + RSS 自动发现链接。"""
    out = []
    if rel_path in ("index.html", "blog/index.html"):
        out.append('<link rel="alternate" type="application/rss+xml" '
                   'title="%s" href="%s/feed.xml">'
                   % (xml_escape(site.get("feed_title", site.get("author", "RSS"))),
                      site["base_url"]))
    for blob in json_ld_for(rel_path, meta, site):
        out.append('<script type="application/ld+json">%s</script>'
                   % json_ld_script(blob))
    return "\n".join(out)


def render_sitemap(site, pages):
    """标准 XML sitemap。没有 date 的页面（首页、博客列表）不写 lastmod ——
    编一个日期比留空更糟，那是在给搜索引擎喂假信号。"""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for rel_path, meta in pages.items():
        lines.append("  <url>")
        lines.append("    <loc>%s</loc>" % xml_escape(
            canonical_url(site["base_url"], meta["url_path"])))
        if meta.get("date"):
            lines.append("    <lastmod>%s</lastmod>" % meta["date"])
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def render_robots(site):
    """告诉爬虫去哪儿找 sitemap。注意 Sitemap 一行指向主站，与 canonical 策略一致。"""
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        "Sitemap: %s/sitemap.xml\n" % site["base_url"]
    )


def render_feed(site, pages, bodies):
    """RSS 2.0 全文源。

    选全文而不是摘要：这个博客的价值在内容本身（md5 一致的实验记录），
    摘要源会让 RSS 读者失去订阅的理由。
    """
    updated = [m["date"] for m in pages.values() if m.get("date")]
    feed_title = site.get("feed_title", "%s · 博客" % site.get("author", ""))
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        '  <channel>',
        '    <title>%s</title>' % xml_escape(feed_title),
        '    <link>%s/blog/index.html</link>' % site["base_url"],
        '    <description>%s</description>' % xml_escape(
            pages["blog/index.html"]["description"]),
        '    <language>%s</language>' % site.get("lang", "zh-CN"),
        '    <atom:link href="%s/feed.xml" rel="self" '
        'type="application/rss+xml"/>' % site["base_url"],
    ]
    if updated:
        out.append('    <lastBuildDate>%s</lastBuildDate>' % rfc822_date(max(updated)))

    # 只收录文章页；首页和列表不是"条目"
    posts = [(r, m) for r, m in pages.items() if m.get("date")]
    for rel_path, meta in sorted(posts, key=lambda kv: kv[1]["date"], reverse=True):
        body = absolutize_links(bodies[rel_path], meta["url_path"], site["base_url"])
        out.append("    <item>")
        out.append("      <title>%s</title>" % xml_escape(meta["title"]))
        out.append("      <link>%s</link>" % xml_escape(
            canonical_url(site["base_url"], meta["url_path"])))
        out.append("      <guid isPermaLink=\"true\">%s</guid>" % xml_escape(
            canonical_url(site["base_url"], meta["url_path"])))
        out.append("      <pubDate>%s</pubDate>" % rfc822_date(meta["date"]))
        out.append("      <description><![CDATA[%s]]></description>" % cdata_escape(body))
        out.append("    </item>")

    out += ["  </channel>", "</rss>"]
    return "\n".join(out) + "\n"


def render_404(layout, site, pages):
    """404 页。GitHub Pages 与 Cloudflare Pages 都会自动使用它。

    用首页的视觉样式，给两个出口：回首页、去博客。
    """
    v = dict(path_vars(""))
    v.update({
        "title": "页面不存在 · %s" % site.get("author", ""),
        "description": "你要找的页面不存在或已被移动。",
        "canonical": canonical_url(site["base_url"], "404.html"),
        "og_type": "website",
        "og_title": "页面不存在 · %s" % site.get("author", ""),
        "og_description": "你要找的页面不存在或已被移动。",
        "twitter_title": "页面不存在 · %s" % site.get("author", ""),
        "twitter_description": "你要找的页面不存在或已被移动。",
        "og_image_alt": "页面不存在",
        "base_url": site["base_url"],
        "csp": site["csp_meta"],
        # 404 页刻意不放 JSON-LD：它不是有效内容，给它结构化数据等于邀请搜索引擎
        # 把它收录进去。留一行注释说明是有意为之，免得以后被当成遗漏。
        # noindex 是必须的：托管平台会在任意未知路径返回这一页，
        # 不加的话搜索引擎会把每个失效 URL 都当成一个可索引页面收进去。
        "head_extra": ('<meta name="robots" content="noindex">\n'
                       '<!-- 404：不输出结构化数据，此页不应被索引 -->'),
    })
    body = (
        '<section><div class="wrap">\n'
        '  <article class="article glass reveal">\n'
        '    <h1>404 · 这个地址没有东西</h1>\n'
        '    <p>链接可能过期了，或者从来没存在过。</p>\n'
        '    <div class="links">\n'
        '      <a href="index.html">← 回首页</a>\n'
        '      <a href="blog/index.html">去博客</a>\n'
        '    </div>\n'
        '  </article>\n'
        '</div></section>'
    )
    return layout.render(v, body, site["footers"]["page"])


# ---------------------------------------------------------------- 比对与写入

def compare(outputs):
    """拿构建结果和磁盘上的现有文件逐字节比对，返回差异清单。"""
    diffs = []
    for rel_path, text in sorted(outputs.items()):
        disk = os.path.join(ROOT, rel_path)
        if not os.path.exists(disk):
            diffs.append((rel_path, "文件不存在（新建）", None))
            continue
        old = read(disk)
        if old != text:
            diffs.append((rel_path, describe_diff(old, text), None))
    return diffs


def describe_diff(old, new):
    """给人看的差异描述：第一个不同的位置 + 前后文。"""
    ol, nl = old.split("\n"), new.split("\n")
    for i in range(max(len(ol), len(nl))):
        o = ol[i] if i < len(ol) else "<缺少>"
        n = nl[i] if i < len(nl) else "<缺少>"
        if o != n:
            return "第 %d 行不同\n      现有: %s\n      构建: %s" % (
                i + 1, o.strip()[:100] or "(空行)", n.strip()[:100] or "(空行)")
    return "行数不同但内容看起来一样（可能是尾随换行差异）"


def do_write(outputs):
    for rel_path, text in sorted(outputs.items()):
        write(os.path.join(ROOT, rel_path), text)
    print("已写入 %d 个文件" % len(outputs))


# ---------------------------------------------------------------- 反向生成

def bootstrap():
    """从现有手写 HTML 反向生成 src/。只应在首次迁移时运行。

    它会把每份 HTML 的重复区块抽出来，并**逐份交叉验证**：
    除了已知的 per-page 字段外必须完全一致，否则说明这套模板化漏了东西。
    """
    print("从现有 HTML 反向生成 src/ ...\n")

    blocks = {}
    for rel in HTML_TARGETS:
        text = read(os.path.join(ROOT, rel))
        blocks[rel] = {
            "text": text,
            "title": re.search(r"<title>(.*?)</title>", text, re.S).group(1),
            "description": re.search(
                r'<meta name="description" content="(.*?)">', text, re.S).group(1),
            "og_title": re.search(
                r'<meta property="og:title" content="(.*?)">', text, re.S).group(1),
            "og_description": re.search(
                r'<meta property="og:description" content="(.*?)">', text, re.S).group(1),
            "twitter_title": re.search(
                r'<meta name="twitter:title" content="(.*?)">', text, re.S).group(1),
            "twitter_description": re.search(
                r'<meta name="twitter:description" content="(.*?)">', text, re.S).group(1),
            "og_image_alt": re.search(
                r'<meta property="og:image:alt" content="(.*?)">', text, re.S).group(1),
            "og_type": re.search(
                r'<meta property="og:type" content="(.*?)">', text, re.S).group(1),
            "canonical": re.search(
                r'<link rel="canonical" href="(.*?)">', text, re.S).group(1),
            "csp": re.search(
                r'<meta http-equiv="Content-Security-Policy" content="(.*?)">',
                text, re.S).group(1),
        }

    # 1) 交叉验证：各文件的重复区块必须一致
    ref = "blog/post-1.html"
    for rel, b in blocks.items():
        if rel == ref:
            continue
        for key in ("csp",):
            if b[key] != blocks[ref][key]:
                fail("%s 与 %s 的 %s 不一致，模板化会丢失差异" % (rel, ref, key))

    # 2) 抽出 head 中的 base_url（所有页面共用同一个 og:image 域名）
    m = re.search(r'<meta property="og:image" content="(https?://[^/]+)', blocks[ref]["text"])
    base_url = m.group(1)

    # 3) 从 reference 文件生成 base.html 模板
    t = blocks[ref]["text"]
    nav_open = Layout.A_NAV_OPEN
    head = t[:t.index(nav_open)]
    head = head.replace('href="../', 'href="{{rel}}') \
               .replace('src="../', 'src="{{rel}}')
    # head 里的 per-page 字段换成变量
    head = head.replace(blocks[ref]["title"], "{{title}}") \
               .replace(blocks[ref]["description"], "{{description}}") \
               .replace(blocks[ref]["csp"], "{{csp}}")
    head = re.sub(r'<link rel="canonical" href=".*?">',
                  '<link rel="canonical" href="{{canonical}}">', head)
    head = re.sub(r'<meta property="og:type" content=".*?">',
                  '<meta property="og:type" content="{{og_type}}">', head)
    head = re.sub(r'<meta property="og:title" content=".*?">',
                  '<meta property="og:title" content="{{og_title}}">', head)
    head = re.sub(r'<meta property="og:description" content=".*?">',
                  '<meta property="og:description" content="{{og_description}}">', head)
    head = re.sub(r'<meta property="og:url" content=".*?">',
                  '<meta property="og:url" content="{{canonical}}">', head)
    head = re.sub(r'<meta property="og:image:alt" content=".*?">',
                  '<meta property="og:image:alt" content="{{og_image_alt}}">', head)
    head = re.sub(r'<meta property="og:image" content=".*?">',
                  '<meta property="og:image" content="{{base_url}}/assets/og-cover.png">', head)
    head = re.sub(r'<meta name="twitter:title" content=".*?">',
                  '<meta name="twitter:title" content="{{twitter_title}}">', head)
    head = re.sub(r'<meta name="twitter:description" content=".*?">',
                  '<meta name="twitter:description" content="{{twitter_description}}">', head)
    head = re.sub(r'<meta name="twitter:image" content=".*?">',
                  '<meta name="twitter:image" content="{{base_url}}/assets/og-cover.png">', head)

    # nav 区 + main/footer 之间的部分
    i_main = t.index(Layout.A_MAIN_OPEN)
    nav = t[t.index(nav_open):i_main]
    # 顺序有讲究：品牌位的 href 是 "../index.html" 的完整形式，必须先把这个最具体的
    # 匹配掉，再把剩下的 "../index.html" 前缀统一换成锚点变量，否则品牌位会被误伤。
    nav = nav.replace('class="brand" href="../index.html">',
                      'class="brand" href="{{home}}">')
    nav = nav.replace('<a href="index.html">博客', '<a href="{{blog}}">博客')
    nav = nav.replace('href="../index.html', 'href="{{anchor}}')

    i_fclose = t.index(Layout.A_FOOTER_CLOSE)
    i_mclose = t.index(Layout.A_MAIN_CLOSE)
    footer_open = t[i_mclose + len(Layout.A_MAIN_CLOSE):t.index(Layout.A_FOOTER_OPEN) + len(Layout.A_FOOTER_OPEN)]
    tail = t[i_fclose + len(Layout.A_FOOTER_CLOSE):]
    tail = tail.replace('src="../', 'src="{{rel}}')

    # head_extra 的落位：JSON-LD 与 RSS 自动发现链接会插在这里。
    # 写进 bootstrap 而不是事后手加，是为了让模板被重建时不会悄悄丢掉这个能力。
    head = head.replace(
        '<link rel="stylesheet" href="{{rel}}assets/style.css">\n</head>',
        '<link rel="stylesheet" href="{{rel}}assets/style.css">\n{{head_extra}}\n</head>')
    if "{{head_extra}}" not in head:
        fail("无法在 </head> 前定位 style.css 链接行，head_extra 落位失败")

    # main 占位符：base.html 里留 {{content}}
    layout = (head + nav + Layout.A_MAIN_OPEN + "{{content}}" +
              Layout.A_MAIN_CLOSE + footer_open + "{{footer_inner}}" +
              Layout.A_FOOTER_CLOSE + tail)

    # 4) 页脚形态归集：全站只有两种（首页多一行寄语），提到 site.json 里单数维护，
    #    否则 pages.json 会被同一份页脚占满九行。
    def footer_of(doc):
        a = doc.index(Layout.A_FOOTER_OPEN) + len(Layout.A_FOOTER_OPEN)
        return doc[a:doc.index(Layout.A_FOOTER_CLOSE)]

    home_footer = footer_of(blocks["index.html"]["text"])
    others = {rel: footer_of(b["text"]) for rel, b in blocks.items() if rel != "index.html"}
    odd = sorted(rel for rel, f in others.items() if f != home_footer)
    page_footers = sorted({others[r] for r in odd})
    if len(page_footers) > 1:
        fail("文章页出现了 %d 种不同的页脚，超出模板设计（预期 1 种）" % len(page_footers))
    footers = {"home": home_footer, "page": page_footers[0] if page_footers else home_footer}

    # 5) 每份页面的正文
    pages_meta = {}
    for rel, b in blocks.items():
        doc = b["text"]
        i_open = doc.index(Layout.A_MAIN_OPEN) + len(Layout.A_MAIN_OPEN)
        content = doc[i_open:doc.index(Layout.A_MAIN_CLOSE)]

        body_name = rel.replace("/", "-").replace(".html", ".body.html")
        write(os.path.join(PAGES_DIR, body_name), content)

        url_path = rel if rel != "index.html" else ""
        meta = {
            "body": body_name,
            "url_path": url_path,
            "title": b["title"],
            "description": b["description"],
            "og_type": b["og_type"],
            "footer": "home" if rel == "index.html" else "page",
        }
        # 只有文章页才有发布时间。博客列表的正文里虽然也含 class="date"（那是每张
        # 卡片的日期），但它不是一篇文章，不能被收进 RSS。
        if rel.startswith("blog/post-"):
            meta["date"] = extract_body_date(content)
        # 只在与 title/description 不同时才显式保存，避免冗余
        if b["og_title"] != b["title"]:
            meta["og_title"] = b["og_title"]
        if b["og_description"] != b["description"]:
            meta["og_description"] = b["og_description"]
        if b["twitter_title"] != b["title"]:
            meta["twitter_title"] = b["twitter_title"]
        if b["twitter_description"] != b["description"]:
            meta["twitter_description"] = b["twitter_description"]
        if b["og_image_alt"] != b["title"]:
            meta["og_image_alt"] = b["og_image_alt"]
        pages_meta[rel] = meta

    site = {
        "base_url": base_url,
        "csp_meta": blocks[ref]["csp"],
        "footers": footers,
        "author": "xiaoyu-hue",
        "lang": "zh-CN",
        "feed_title": "xiaoyu-hue · 博客",
    }

    # 安全措施：模板一旦被人改过（加了新区块、调整过注释），bootstrap 反推出的
    # 版本会把那些改动无声地冲掉。所以已存在时默认不动，想重建要显式表态。
    if os.path.exists(LAYOUT_FILE) and "--force" not in sys.argv:
        print("  · src/layouts/base.html 已存在，未覆盖（避免冲掉已有改动）")
        print("    确认要按现有 HTML 重建模板的话，先删掉它，或追加 --force。")
    else:
        write(LAYOUT_FILE, layout)
        print("  · 已写入 src/layouts/base.html")

    write(SITE_JSON, json.dumps(site, ensure_ascii=False, indent=2) + "\n")
    write(PAGES_JSON, json.dumps(pages_meta, ensure_ascii=False, indent=2) + "\n")

    print("已生成：")
    print("  src/layouts/base.html")
    print("  src/data/site.json")
    print("  src/data/pages.json")
    print("  src/pages/ 下 %d 个正文片段" % len(pages_meta))
    print("\n现在运行 python3 build.py 验证产物是否与现有文件完全一致。")


# ---------------------------------------------------------------- 入口

def main():
    args = sys.argv[1:]

    if "--bootstrap" in args:
        bootstrap()
        return

    site, pages = load_site()
    outputs = build(site, pages)
    diffs = compare(outputs)

    if "--write" in args:
        do_write(outputs)
        return

    if not diffs:
        print("✓ 构建产物与现有文件逐字节一致（共 %d 个文件）" % len(outputs))
        print("  说明：目前 %d 份手抄样板已被 1 份模板替代，站点外观与行为没有任何变化。"
              % len(HTML_TARGETS))
        return

    print("✗ 构建产物与现有文件存在差异（%d 处）：\n" % len(diffs))
    for rel, why, _ in diffs:
        print("  %s\n    %s\n" % (rel, why))
    print("如果这些差异是有预期的（比如改了 base_url），用 --write 写入。")
    sys.exit(EXIT_DIFF)


if __name__ == "__main__":
    main()
