"""builder.layout —— 模板渲染：Layout 类、路径变量、canonical、404 页（机械搬运）。"""
import re

from .io_utils import fail, read

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
