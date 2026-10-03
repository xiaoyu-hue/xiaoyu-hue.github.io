"""builder.bootstrap —— 反向生成：从手写 HTML 生成 src/（首次迁移用，机械搬运）。"""
import os
import re
import sys

from .content import extract_body_date
from .io_utils import fail, html_targets, read, write
from .layout import Layout
from .paths import (LAYOUT_FILE, PAGES_DIR, PAGES_JSON, ROOT, SITE_JSON)

def bootstrap():
    """从现有手写 HTML 反向生成 src/。只应在首次迁移时运行。

    它会把每份 HTML 的重复区块抽出来，并**逐份交叉验证**：
    除了已知的 per-page 字段外必须完全一致，否则说明这套模板化漏了东西。
    """
    print("从现有 HTML 反向生成 src/ ...\n")

    blocks = {}
    for rel in html_targets():
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
