"""builder.feeds —— 机器可读层：JSON-LD / sitemap / robots / RSS（机械搬运）。"""
import json
import re

from .layout import canonical_url

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
