"""builder.validate —— 内容登记表校验（阶段4 新增）。

设计原则与 build.py 一致：未知即报错，绝不静默产出可能错误的内容。
校验的是「结构与引用」（字段齐不齐、文件在不在、指向对不对），
不校验「文案好坏」——那是人的事。

返回 (errors, warnings)：errors 会导致构建中止；warnings 只提示不拦截。
"""

import datetime
import os
import re

from .io_utils import read
from .paths import PAGES_DIR, POST_URL_RE

# og:type 的合法取值（Open Graph 协议常用值中本站实际用到的两个）
ALLOWED_OG_TYPES = {"website", "article"}
# 每个页面条目的必填字段
REQUIRED_ALL = ("body", "title", "description", "og_type", "footer")
# 博客文章（blog/post-N.html）额外必填
POST_REQUIRED = ("card", "date")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL_RE = re.compile(r"^https?://\S+$")


def validate_site(site, pages):
    """校验 site.json 结构（site）与 pages.json 登记表（pages）。"""
    errors, warnings = [], []

    # ---------- site.json ----------
    base = (site.get("base_url") or "").strip()
    if not URL_RE.match(base):
        errors.append("site.json: base_url 必须是 http(s):// 开头的完整地址，现在是 %r" % base)
    elif base.endswith("/"):
        errors.append("site.json: base_url 不应以 / 结尾（canonical_url 会直接拼接路径，"
                      "结尾的斜杠会产生 //path 这样的坏链接）")
    for key in ("csp_meta", "author", "lang", "feed_title"):
        if not site.get(key):
            errors.append("site.json: 缺少必填字段 %s" % key)
    footers = site.get("footers") or {}
    for key in ("home", "page"):
        if key not in footers:
            errors.append("site.json: footers 必须包含 %r（页面条目按名引用它）" % key)

    # ---------- pages.json ----------
    if not isinstance(pages, dict) or not pages:
        errors.append("pages.json: 必须是非空的对象（键 = 相对路径，值 = 登记信息）")
        return errors, warnings

    seen_url_paths = {}
    for rel, meta in sorted(pages.items()):
        where = "pages.json[%s]" % rel
        if not rel.endswith(".html"):
            errors.append("%s: 键必须以 .html 结尾" % where)
        for key in REQUIRED_ALL:
            if not meta.get(key):
                errors.append("%s: 缺少必填字段 %s" % (where, key))
        if meta.get("footer") and meta["footer"] not in footers:
            errors.append("%s: footer=%r 在 site.json footers 里不存在" % (where, meta["footer"]))
        if meta.get("og_type") and meta["og_type"] not in ALLOWED_OG_TYPES:
            errors.append("%s: og_type=%r 不在合法取值 %s 里"
                          % (where, meta["og_type"], sorted(ALLOWED_OG_TYPES)))

        # body 文件必须存在
        body_name = meta.get("body") or ""
        body_file = os.path.join(PAGES_DIR, body_name)
        if not body_name or not os.path.isfile(body_file):
            errors.append("%s: body 指向的文件不存在: src/pages/%s" % (where, body_name))
        else:
            body = read(body_file)
            is_post = bool(POST_URL_RE.match(rel))
            if is_post:
                if "<h1" not in body:
                    errors.append("%s: 正文缺少 <h1>（博客列表卡片拿它当标题）" % where)
                if '<div class="date">' not in body:
                    errors.append('%s: 正文缺少 <div class="date">（卡片日期与日期推断都依赖它）' % where)
                for key in POST_REQUIRED:
                    if not meta.get(key):
                        errors.append("%s: 博客文章缺少必填字段 %s" % (where, key))
                d = meta.get("date")
                if d:
                    if not ISO_DATE.match(str(d)):
                        errors.append("%s: date 必须是 YYYY-MM-DD 格式，现在是 %r" % (where, d))
                    else:
                        try:
                            datetime.date.fromisoformat(str(d))
                        except ValueError:
                            errors.append("%s: date 不是有效日期: %r" % (where, d))
            # url_path 唯一性
            url_path = meta.get("url_path")
            if url_path in seen_url_paths:
                errors.append("%s: url_path=%r 与 %s 重复（会生成同一个地址）"
                              % (where, url_path, seen_url_paths[url_path]))
            else:
                seen_url_paths[url_path] = rel
            # 正文日期与登记表日期不一致 → 提示（可能是忘了同步，不拦截）
            if is_post and meta.get("date"):
                from .content import extract_body_date
                body_date = extract_body_date(body)
                if body_date and body_date != meta["date"]:
                    warnings.append("%s: 登记表 date=%s 与正文日期 %s 不一致，以登记表为准"
                                    % (where, meta["date"], body_date))

    return errors, warnings
