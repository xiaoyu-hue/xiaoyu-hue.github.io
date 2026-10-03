"""builder.content —— 内容层：文章发现、登记表合并、卡片渲染（机械搬运）。"""
import json
import os
import re

from .io_utils import fail, read
from .paths import PAGES_DIR, PAGES_JSON, POST_BODY_RE, POST_URL_RE, SITE_JSON
from .feeds import extract_body_date

def discover_posts():
    """扫描 src/pages/ 下的 blog-post-N.body.html，返回 {编号: 派生信息}。

    这是「有哪些文章」的唯一事实来源。此前这件事被抄在 8 个地方
    （登记表、列表页卡片、离线页、SW 缓存清单、构建目标、3 处测试清单），
    每加一篇都要同步一遍，漏一处还不会报错，只会默默少一个入口。
    现在只认目录：放一个文件进来就算一篇文章。
    """
    found = {}
    for name in sorted(os.listdir(PAGES_DIR)):
        m = POST_BODY_RE.match(name)
        if not m:
            continue
        num = int(m.group(1))
        body = read(os.path.join(PAGES_DIR, name))
        h1 = re.search(r"<h1>(.*?)</h1>", body, re.S)
        date_line = re.search(r'<div class="date">(.*?)</div>', body, re.S)
        if not h1:
            fail("src/pages/%s 里找不到 <h1>，无法推断标题" % name)
        if not date_line:
            fail('src/pages/%s 里找不到 <div class="date">，无法推断日期' % name)
        found[num] = {
            "file": name,
            "h1": strip_tags(h1.group(1)).strip(),
            # 卡片整体是一个 <a>，里面不能再嵌 <a>（HTML 不允许嵌套链接），
            # 所以日期行一律取纯文本：正文里项目名可以带 GitHub 链接，卡片里只能是字。
            "date_line": strip_tags(date_line.group(1)).strip(),
            "date": extract_body_date(body),
            "first_para": first_paragraph(body),
        }
    if not found:
        fail("src/pages/ 下没有任何 blog-post-N.body.html，站点至少得有一篇文章")
    return found


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s)


def first_paragraph(body):
    """正文第一个 <p> 的纯文本 —— 摘要的最后兜底。"""
    m = re.search(r"<p>(.*?)</p>", body, re.S)
    return strip_tags(m.group(1)).strip() if m else ""


def derive_post_meta(site, num, info):
    """一篇文章在没人手写登记时，能自己推出哪些字段。"""
    return {
        "body": info["file"],
        "url_path": "blog/post-%d.html" % num,
        "title": "%s · %s" % (info["h1"], site["author"]),
        "description": info["first_para"],
        "og_type": "article",
        "footer": "page",
        "date": info["date"],
    }


def load_pages(site):
    """登记表（pages.json）与目录的合并结果。

    · 登记表里写了的 → 以登记表为准（description / card 这类手工文案）
    · 目录里有、登记表没写的 → 全部字段自动派生

    两者分工不同：目录回答「有没有这篇」，登记表回答「这篇怎么写得更好」。
    所以新增一篇文章可以不碰登记表——这正是要让「加一篇文章 = 加一个文件」。
    """
    explicit = json.loads(read(PAGES_JSON))
    discovered = discover_posts()
    pages = {}
    seen = set()

    for key, meta in explicit.items():
        m = POST_URL_RE.match(key)
        if not m:
            pages[key] = meta
            continue
        num = int(m.group(1))
        info = discovered.get(num)
        if info is None:
            fail("pages.json 登记了 %s，但 src/pages/ 下没有 blog-post-%d.body.html" % (key, num))
        merged = derive_post_meta(site, num, info)
        merged.update(meta)
        # 下划线前缀 = 派生字段，不写回 pages.json，只在构建期使用
        merged["_h1"] = info["h1"]
        merged["_date_line"] = info["date_line"]
        pages[key] = merged
        seen.add(num)

    for num in sorted(set(discovered) - seen):
        info = discovered[num]
        merged = derive_post_meta(site, num, info)
        merged["_h1"] = info["h1"]
        merged["_date_line"] = info["date_line"]
        merged["card"] = info["first_para"]   # 没手写摘要就用首段，至少不是空的
        pages[merged["url_path"]] = merged
    return pages


CARD_TEMPLATE = (
    '  <a class="glass post-card reveal" href="%s">\n'
    "    <h3>%s</h3>\n"
    '    <div class="date">%s</div>\n'
    "    <p>%s</p>\n"
    "  </a>"
)


def render_post_cards(pages):
    """按「日期倒序、同一天里编号倒序」生成博客列表页的卡片。"""
    posts = []
    for rel, meta in pages.items():
        m = POST_URL_RE.match(rel)
        if not m:
            continue
        posts.append((meta.get("date") or "", int(m.group(1)), rel, meta))
    posts.sort(key=lambda t: (t[0], t[1]), reverse=True)
    cards = []
    for _date, _num, rel, meta in posts:
        href = rel.rsplit("/", 1)[-1]
        summary = meta.get("card") or meta.get("description") or ""
        cards.append(CARD_TEMPLATE % (href, meta["_h1"], meta["_date_line"], summary))
    return "\n\n".join(cards)

def load_site():
    site = json.loads(read(SITE_JSON))
    return site, load_pages(site)
