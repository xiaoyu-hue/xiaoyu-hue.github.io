"""builder.pipeline —— 构建主管线：把内容拼成全部成品（机械搬运）。"""
import os

from .content import extract_body_date, render_post_cards
from .feeds import (canonical_url, render_feed, render_head_extra,
                    render_robots, render_sitemap)
from .io_utils import fail, read
from .layout import Layout, path_vars, render_404
from .paths import LAYOUT_FILE, PAGES_DIR
from .pwa import render_headers, render_offline, render_sw

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

        # 列表页的卡片由文章清单自动生成，不再手抄。
        if "{{post-cards}}" in content:
            content = content.replace("{{post-cards}}", render_post_cards(pages))

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
    outputs["offline.html"] = render_offline(pages)
    outputs["sw.js"] = render_sw(pages)
    return outputs
