"""7 个页面的结构与文案契约。

改页面时最容易悄悄破坏的就是这些「每页都一样」的东西,靠人眼是看不住的。
"""

import json
import os
import re
import struct
import unittest

from tests.support import (
    PAGES,
    SIGNATURE,
    exists,
    headers_csp,
    parse,
    png_size,
    read,
    read_bytes,
)

# 离线页不参与 PAGES 的常规契约（它没有 prefs 面板、没有 4 个导航链接），
# 但它同样必须带 CSP 且被完整性检查覆盖。单独的契约见 TestOfflinePage。
OFFLINE_PAGE = "offline.html"

# 站点全部页面 = 常规页 + 离线页
ALL_PAGES = PAGES + [OFFLINE_PAGE]

EXPECTED_CSS = {"index.html": "assets/style.css"}
DEFAULT_CSS = "../assets/style.css"

# <script type="application/ld+json"> 是 data block（数据块），不是可执行脚本：
# HTML 规范里 script 的 type 不匹配 JavaScript MIME 时浏览器把它当纯数据返回，
# 不进入执行路径，因此不受 script-src 'self' 约束。三引擎实测确认，
# 详见 docs/csp-jsonld.md。这里仍然用显式白名单，不放开任意 type。
DATA_BLOCK_TYPES = ("application/ld+json", "application/json")

# 每页应有的结构化数据类型：搜索引擎靠它显示面包屑/作者/发布时间，
# 内容聚合器与 AI 摘要工具也主要读这一层而不是猜正文。404(离线)页刻意不写。
EXPECTED_JSONLD_TYPE = {
    "index.html": "WebSite",
    "blog/index.html": "CollectionPage",
}

# 每页应有的滚动淡入元素数量。
#
# · 文章页一律 0：正文不参与滚动淡入是刻意的设计，长文逐段淡入会让人读不下去。
# · 列表页 = 1 个区块标题 + 每篇文章一张卡片，由文章数算出来。
#   这里如果写死「10」，每加一篇文章都要回来改一次，不改就误报成失败 ——
#   而它本该抓的是「卡片被动了」，不是「文章变多了」。
# · 首页不是文章列表，数量来自它自己的版式，仍然写死：这里变了说明版式被改过，
#   正是需要人看一眼的情况。
EXPECTED_REVEAL_COUNT = {
    "index.html": 11,
}


def expected_reveal_count(page):
    if page.startswith("blog/post-"):
        return 0
    if page == "blog/index.html":
        posts = [n for n in os.listdir("blog") if re.match(r"^post-\d+\.html$", n)]
        return 1 + len(posts)
    if page not in EXPECTED_REVEAL_COUNT:
        raise AssertionError("没有为 %s 约定 .reveal 数量" % page)
    return EXPECTED_REVEAL_COUNT[page]


def asset_prefix(page):
    """页面所在层级决定相对路径前缀。"""
    return "" if os.path.dirname(page) == "" else "../"


class TestHeadContract(unittest.TestCase):
    """<head> 里每页都必须一致的部分。"""

    def test_doctype(self):
        for page in PAGES:
            with self.subTest(page=page):
                self.assertTrue(
                    read(page).lstrip().lower().startswith("<!doctype html>"),
                    f"{page} 缺少或写错了 DOCTYPE",
                )

    def test_html_lang(self):
        for page in PAGES:
            with self.subTest(page=page):
                html = parse(page).find("html")
                self.assertIsNotNone(html, f"{page} 没有 <html>")
                self.assertEqual(html.attrs.get("lang"), "zh-CN")

    def test_charset_and_viewport(self):
        for page in PAGES:
            with self.subTest(page=page):
                doc = parse(page)
                charset = next(
                    (m for m in doc.find_all("meta") if m.attrs.get("charset")), None
                )
                self.assertIsNotNone(charset, f"{page} 缺少 charset")
                viewport = next(
                    (m for m in doc.find_all("meta")
                     if m.attrs.get("name") == "viewport"), None
                )
                self.assertIsNotNone(viewport, f"{page} 缺少 viewport")
                self.assertIn("width=device-width", viewport.attrs.get("content", ""))

    def test_referrer_policy(self):
        for page in PAGES:
            with self.subTest(page=page):
                ref = next(
                    (m for m in parse(page).find_all("meta")
                     if m.attrs.get("name") == "referrer"), None
                )
                self.assertIsNotNone(ref, f"{page} 缺少 referrer 策略")
                self.assertEqual(ref.attrs.get("content"), "strict-origin-when-cross-origin")

    def test_csp_matches_headers(self):
        """页面 meta CSP 必须与 _headers 里的策略同源,只差 frame-ancestors。

        frame-ancestors 通过 <meta> 下发会被浏览器忽略,所以它只能出现在 _headers。
        这条测试同时防止两处策略悄悄漂移。
        """
        expected = headers_csp()
        self.assertTrue(expected.endswith("; frame-ancestors 'none'"),
                        "_headers 的 CSP 应以 frame-ancestors 'none' 结尾")
        meta_should_be = expected[: -len("; frame-ancestors 'none'")]

        for page in PAGES:
            with self.subTest(page=page):
                csp = next(
                    (m for m in parse(page).find_all("meta")
                     if (m.attrs.get("http-equiv") or "").lower() == "content-security-policy"),
                    None,
                )
                self.assertIsNotNone(csp, f"{page} 缺少 meta CSP")
                self.assertEqual(csp.attrs.get("content"), meta_should_be,
                                 f"{page} 的 CSP 与 _headers 不一致")
                for bad in ("unsafe-inline", "unsafe-eval",
                            "frame-ancestors", "sandbox", "report-uri", "report-to"):
                    self.assertNotIn(bad, csp.attrs.get("content"),
                                     f"{page} 的 CSP 不应包含 {bad}")

    def test_favicon(self):
        for page in PAGES:
            with self.subTest(page=page):
                icon = next(
                    (l for l in parse(page).find_all("link")
                     if l.attrs.get("rel") == "icon"), None
                )
                self.assertIsNotNone(icon, f"{page} 缺少 favicon 声明")
                href = icon.attrs.get("href", "")
                target = os.path.normpath(os.path.join(os.path.dirname(page), href))
                self.assertTrue(exists(target),
                                f"{page} 的 favicon 指向了不存在的 {href}")

    def test_stylesheet_and_script_paths(self):
        """相对路径必须跟着目录层级走,移动文件会立刻断链。

        脚本从「只允许一个」改成「只允许清单内这几个」——
        站点现在确实需要三个脚本(防闪 / 偏好设置 / 滚动动效),
        真正要防的是「不知不觉挂上第 N 个脚本拖慢首屏」,
        所以用白名单而不是放开数量。
        """
        for page in PAGES:
            with self.subTest(page=page):
                doc = parse(page)
                css = next(
                    (l for l in doc.find_all("link") if l.attrs.get("rel") == "stylesheet"),
                    None,
                )
                self.assertIsNotNone(css, f"{page} 没有样式表")
                self.assertEqual(css.attrs.get("href"),
                                 EXPECTED_CSS.get(page, DEFAULT_CSS))

                prefix = "" if os.path.dirname(page) == "" else "../"
                expected_scripts = [
                    f"{prefix}assets/theme-boot.js",   # <head> 内,防首屏闪烁
                    f"{prefix}assets/pwa.js",          # Service Worker 注册与安装引导
                    f"{prefix}assets/prefs.js",        # 主题与设置面板
                    f"{prefix}assets/main.js",         # 滚动动效
                ]

                # 只把「可执行脚本」纳入清单比对，data block 单独处理
                js = [
                    s for s in doc.find_all("script")
                    if s.attrs.get("type") not in DATA_BLOCK_TYPES
                ]
                srcs = [s.attrs.get("src") for s in js]
                self.assertEqual(
                    srcs, expected_scripts,
                    f"{page} 的脚本清单与预期不符（增删脚本请同步更新本测试）",
                )
                for s in js:
                    self.assertFalse(s.texts, f"{page} 的脚本标签不应有内联内容")

    def test_jsonld_present_and_parsable(self):
        """结构化数据必须存在、必须是合法 JSON、必须声明正确的 @type。

        这条契约的价值在于：JSON-LD 写错时页面看起来毫无异常，
        只有搜索引擎静默失效——靠肉眼完全看不到。
        """
        for page in PAGES:
            with self.subTest(page=page):
                doc = parse(page)
                blocks = [
                    s for s in doc.find_all("script")
                    if s.attrs.get("type") == "application/ld+json"
                ]
                self.assertTrue(
                    blocks, f"{page} 没有任何 JSON-LD 结构化数据",
                )
                parsed = []
                for b in blocks:
                    raw = b.text
                    self.assertIsNotNone(raw, f"{page} 的 JSON-LD 是空的")
                    try:
                        parsed.append(json.loads(raw))
                    except json.JSONDecodeError as e:
                        self.fail(f"{page} 的 JSON-LD 不是合法 JSON：{e}")
                types = [p.get("@type") for p in parsed]
                want = EXPECTED_JSONLD_TYPE.get(page) or "BlogPosting"
                self.assertIn(
                    want, types,
                    f"{page} 的 JSON-LD 缺 @type={want}，实际为 {types}",
                )

    def test_jsonld_urls_are_absolute(self):
        """结构化数据里的 url 必须是绝对地址。

        相对路径在本地渲染毫无问题，但被搜索引擎抓走后会指向它自己的域名，
        等于给自己制造一堆错 URL。
        """
        for page in PAGES:
            with self.subTest(page=page):
                for b in parse(page).find_all("script"):
                    if b.attrs.get("type") != "application/ld+json":
                        continue
                    data = json.loads(b.text)
                    if "url" in data:
                        self.assertTrue(
                            data["url"].startswith("https://"),
                            f"{page} 的 JSON-LD 字段 url 不是绝对 URL：{data['url']!r}",
                        )
                    if data.get("author", {}).get("url"):
                        self.assertTrue(
                            data["author"]["url"].startswith("https://"),
                            f"{page} 的 author.url 不是绝对 URL",
                        )


class TestTitleAndDescription(unittest.TestCase):
    def test_title_unique_and_non_empty(self):
        seen = {}
        for page in PAGES:
            with self.subTest(page=page):
                title = parse(page).find("title")
                self.assertIsNotNone(title, f"{page} 没有 <title>")
                text = title.text.strip()
                self.assertTrue(text, f"{page} 的 title 是空的")
                seen.setdefault(text, []).append(page)
        dup = {t: ps for t, ps in seen.items() if len(ps) > 1}
        self.assertEqual(dup, {}, f"这些页面的 title 重复了: {dup}")

    def test_description_unique_and_non_empty(self):
        seen = {}
        for page in PAGES:
            with self.subTest(page=page):
                desc = next(
                    (m for m in parse(page).find_all("meta")
                     if m.attrs.get("name") == "description"), None
                )
                self.assertIsNotNone(desc, f"{page} 没有 description")
                text = (desc.attrs.get("content") or "").strip()
                self.assertTrue(text, f"{page} 的 description 是空的")
                seen.setdefault(text, []).append(page)
        dup = {t: ps for t, ps in seen.items() if len(ps) > 1}
        self.assertEqual(dup, {}, f"这些页面的 description 重复了: {dup}")


class TestBodyContract(unittest.TestCase):
    def test_footer_signature_identical(self):
        """签名串在 7 个页面重复出现,改一处要改七处 —— 用测试盯住。"""
        for page in PAGES:
            with self.subTest(page=page):
                sign = parse(page).find(cls="sign")
                self.assertIsNotNone(sign, f"{page} 没有签名")
                self.assertEqual(sign.text, SIGNATURE)
                footer = parse(page).find("footer")
                self.assertIsNotNone(footer, f"{page} 没有 footer")
                self.assertIn("© 2026 xiaoyu-hue", footer.text)

    def test_nav_links(self):
        for page in PAGES:
            with self.subTest(page=page):
                doc = parse(page)
                nav = doc.find(cls="nav")
                self.assertIsNotNone(nav, f"{page} 没有导航")
                links = nav.find(cls="nav-links")
                self.assertIsNotNone(links, f"{page} 没有 nav-links")
                anchors = links.find_all("a")
                self.assertEqual(len(anchors), 4, f"{page} 的导航应有 4 个链接")
                for a in anchors:
                    self.assertTrue(a.attrs.get("href"), f"{page} 的导航链接缺少 href")
                brand = nav.find(cls="brand")
                self.assertIsNotNone(brand, f"{page} 没有品牌链接")
                self.assertEqual(brand.attrs.get("href"),
                                 "index.html" if page == "index.html" else "../index.html")

    def test_aria_current_marks_current_section(self):
        """博客区页面必须给「博客」导航项加 aria-current="page"，首页不加。

        这条属性此前是零测试覆盖：把它从模板里删掉，全部测试仍然通过
        （实测确认）。对读屏用户来说，少了它就无法知道"我在哪一节"，
        而视觉上完全看不出来 —— 正是最该有回归测试的那类问题。

        注意导航里「博客」项的 href 随层级变化（首页是 blog/index.html、
        博客页是 index.html），所以按链接文字定位，而不是匹配某个固定 href。
        """
        for page in PAGES:
            with self.subTest(page=page):
                links = parse(page).find(cls="nav-links")
                self.assertIsNotNone(links, f"{page} 没有 nav-links")
                blog_link = next((a for a in links.find_all("a")
                                  if a.text.strip() == "博客"), None)
                self.assertIsNotNone(blog_link, f"{page} 导航里没有「博客」链接")
                if page.startswith("blog/"):
                    self.assertEqual(
                        blog_link.attrs.get("aria-current"), "page",
                        f'{page} 在博客区，博客导航项应带 aria-current="page"')
                else:
                    self.assertIsNone(
                        blog_link.attrs.get("aria-current"),
                        f"{page} 不在博客区，博客导航项不该带 aria-current")

    def test_aria_current_appears_exactly_once_per_page(self):
        """每页最多只有一处 aria-current —— 多个"当前项"会让读屏用户困惑。"""
        for page in PAGES:
            with self.subTest(page=page):
                doc = parse(page)
                marked = [n for n in doc.walk()
                          if n.attrs.get("aria-current") == "page"]
                self.assertLessEqual(
                    len(marked), 1,
                    f'{page} 出现了 {len(marked)} 处 aria-current="page"，至多允许 1 处')

    def test_reveal_element_count(self):
        """滚动淡入元素数量写死,防止误删或误加导致动效不一致。"""
        for page in PAGES:
            with self.subTest(page=page):
                expected = expected_reveal_count(page)
                count = len(parse(page).find_all(cls="reveal"))
                self.assertEqual(count, expected,
                                 f"{page} 的 .reveal 数量变了（应为 {expected},现 {count}）")

    def test_no_inline_style_or_event_attributes(self):
        """CSP 不含 unsafe-inline,内联样式和事件属性会被浏览器直接拦掉。"""
        for page in PAGES:
            with self.subTest(page=page):
                html = read(page)
                self.assertNotIn("style=", html, f"{page} 含内联 style=")
                for node in parse(page).walk():
                    for attr in node.attrs:
                        self.assertFalse(attr.startswith("on"),
                                         f"{page} 的元素含内联事件属性 {attr}")


class TestMotionContract(unittest.TestCase):
    """微动效系统的跨页契约。

    这些断言防的是「动效开关看起来在，实际点不动」这类沉默故障：
    按钮渲染出来但没有绑定逻辑，或属性名写错导致 CSS 规则选不中，
    浏览器都不会报任何错。
    """

    def panels(self):
        return [(p, parse(p)) for p in PAGES]

    def test_theme_buttons_still_present(self):
        """动效开关是加到「外观」之后的新分组，不该动到主题按钮。"""
        for page, doc in self.panels():
            with self.subTest(page=page):
                opts = [
                    n.attrs.get("data-theme-option")
                    for n in doc.find_all("button")
                    if n.attrs.get("data-theme-option")
                ]
                self.assertEqual(
                    sorted(opts), ["dark", "light", "system"],
                    f"{page} 的主题三档按钮变了",
                )

    def test_motion_buttons_present_and_complete(self):
        """每个页面都必须有两个动效按钮（on / off），一个都不能少。"""
        for page, doc in self.panels():
            with self.subTest(page=page):
                opts = [
                    n.attrs.get("data-motion-option")
                    for n in doc.find_all("button")
                    if n.attrs.get("data-motion-option")
                ]
                self.assertEqual(
                    sorted(opts), ["off", "on"],
                    f"{page} 的动效开关应有 on / off 两个按钮，实际 {opts}",
                )

    def test_motion_buttons_initial_aria_pressed_is_false(self):
        """初始 aria-pressed 必须是 false。

        真实选中态由 prefs.js 的 syncPanel 在运行时写入。
        如果这里写死 true，那么动效关闭的用户会看到「关闭」按钮
        显示为已按下 —— 而且 syncPanel 还没跑，屏幕阅读器也会读错。
        """
        for page, doc in self.panels():
            with self.subTest(page=page):
                for n in doc.find_all("button"):
                    if not n.attrs.get("data-motion-option"):
                        continue
                    self.assertEqual(
                        n.attrs.get("aria-pressed"), "false",
                        f"{page} 的动效按钮初始 aria-pressed 应当是 false",
                    )

    def test_motion_buttons_are_type_button(self):
        """必须是 type="button"，否则在表单内会触发提交。"""
        for page, doc in self.panels():
            with self.subTest(page=page):
                for n in doc.find_all("button"):
                    if n.attrs.get("data-motion-option"):
                        self.assertEqual(n.attrs.get("type"), "button",
                                         f"{page} 的动效按钮缺少 type=button")

    def test_motion_group_has_accessible_name(self):
        """按钮组要有 aria-label，否则屏幕阅读器只读得出「开启 / 关闭」。"""
        for page, doc in self.panels():
            with self.subTest(page=page):
                groups = [
                    n for n in doc.find_all("div")
                    if n.attrs.get("role") == "group"
                    and "prefs-seg" in n.classes
                    and n.attrs.get("aria-label") == "界面动效"
                ]
                self.assertEqual(len(groups), 1, f"{page} 缺少动效按钮组或 aria-label")

    def test_motion_labels_are_plain_words(self):
        """按钮文案要保持朴素可读，不要用「开 / 关」这种单字。"""
        for page, doc in self.panels():
            with self.subTest(page=page):
                texts = {
                    n.attrs.get("data-motion-option"): n.text.strip()
                    for n in doc.find_all("button")
                    if n.attrs.get("data-motion-option")
                }
                self.assertEqual(texts.get("on"), "开启", f"{page} 的开启按钮文案变了")
                self.assertEqual(texts.get("off"), "关闭", f"{page} 的关闭按钮文案变了")

    def test_motion_switch_is_documented_in_panel(self):
        """开关旁边要有一句话解释它做了什么，否则用户不知道为什么要点。"""
        for page, doc in self.panels():
            with self.subTest(page=page):
                hints = [n for n in doc.find_all("p") if "prefs-hint" in n.classes]
                self.assertTrue(hints, f"{page} 的动效开关缺少说明文案")


class TestMotionStylesheet(unittest.TestCase):
    """style.css 里微动效系统的结构契约。

    这些是最容易被后人「顺手整理」掉的东西 ——
    比如把末尾的令牌块上移合并，或删掉看起来重复的降级规则。
    """

    def css(self):
        return read("assets/style.css")

    def test_reveal_defined_exactly_once(self):
        """`.reveal` 的过渡只能有一处定义。

        两处定义时，靠源顺序决定谁生效，改动会变成「改了这个那个坏了」。
        注意必须行首锚定：`.grid .reveal:nth-child(2){` 这类后代选择器
        也含 `.reveal`，用子串计数会把它们一并算进来，测出假失败。
        """
        css = self.css()
        self.assertEqual(
            len(re.findall(r"^\.reveal\{", css, re.M)), 1,
            "style.css 里 .reveal 的基础规则应当只有一处",
        )
        self.assertEqual(
            len(re.findall(r"^\.reveal\.in\{", css, re.M)), 1,
            "style.css 里 .reveal.in 应当只有一处",
        )

    def test_motion_tokens_are_defined(self):
        """三档时长与三档位移令牌必须齐备，缺一个会让对应动效失灵。"""
        css = self.css()
        for token in (
            "--dur-fast:", "--dur-base:", "--dur-slow:",
            "--shift-sm:", "--shift-md:", "--shift-lg:",
            "--stagger-step:",
        ):
            self.assertIn(token, css, f"style.css 缺少动效令牌 {token}")

    def test_motion_master_switch_exists(self):
        """总开关是全站唯一一处能把所有动效归零的地方。"""
        css = self.css()
        self.assertIn('[data-motion="off"]', css,
                      "style.css 缺少 html[data-motion=off] 总开关规则")

    def test_motion_block_is_at_the_end(self):
        """微动效系统必须在文件末尾。

        同权重靠源顺序取胜：一旦上移，前面的基础规则会反覆盖它，
        总开关与降级路径会静默失效（浅色主题块踩过同一个坑）。
        """
        css = self.css()
        pos = css.find("微动效系统")
        self.assertGreater(pos, 0, "找不到微动效系统块")
        # 令牌块之后只允许有零散的收尾空白，不允许再出现组件级规则
        tail = css[pos:]
        self.assertIn('[data-motion="off"]', tail,
                      "总开关没有落在微动效系统块内")

    def test_reduced_motion_path_exists(self):
        css = self.css()
        self.assertIn("prefers-reduced-motion:reduce", css,
                      "缺少系统级「减少动画」降级")

    def test_high_contrast_path_exists(self):
        css = self.css()
        self.assertIn("prefers-contrast:more", css,
                      "缺少增强对比度降级：这类用户需要关掉 opacity 过渡")

    def test_no_scripting_path_exists(self):
        css = self.css()
        self.assertIn("scripting:none", css,
                      "缺少脚本不可用时的兜底：没有它 .reveal 会永久白屏")


class TestThemeTokens(unittest.TestCase):
    """主题令牌的结构契约。

    浅色主题的令牌在 style.css 里抄了两遍：一处给显式选择
    （html[data-theme="light"]），一处给「跟随系统且系统是浅色」
    （@media(prefers-color-scheme:light) 里的
    html[data-theme-pref="system"]）。两块必须逐字一致。

    这不是洁癖。只改一处会造成「手动切浅色正常、跟随系统却不达标」
    这种只在部分路径复现的问题，而这类问题最难查 —— 它取决于访问者
    机器的系统设置，开发者本地往往复现不出来。

    本次浏览器实测抓到的 --text-faint 对比度不达标就是这条风险的变现：
    那个值确实在两块里各写了一遍，改色时漏一处就会留下半条修复。
    """

    # 令牌声明形如 `--dur-base:240ms;   /* 注释 */`。
    # 值只取到分号为止，行尾注释不会被算进来。
    TOKEN_RE = re.compile(r"--([a-z0-9-]+)\s*:\s*([^;]+);")

    EXPLICIT_LIGHT = r'html\[data-theme="light"\]\s*\{(.*?)\}'
    SYSTEM_LIGHT = (
        r'@media\(prefers-color-scheme:light\)\s*\{\s*'
        r'html\[data-theme-pref="system"\]\s*\{(.*?)\}'
    )

    def css(self):
        return read("assets/style.css")

    def _tokens(self, pattern):
        """从一个选择器块里抽出令牌字典。

        块内只有单行声明，没有嵌套，所以非贪婪到第一个 } 就够了。
        """
        m = re.search(pattern, self.css(), re.S)
        self.assertIsNotNone(m, f"style.css 里找不到块：{pattern}")
        return {k: v.strip() for k, v in self.TOKEN_RE.findall(m.group(1))}

    def test_light_tokens_are_identical_in_both_blocks(self):
        explicit = self._tokens(self.EXPLICIT_LIGHT)
        system = self._tokens(self.SYSTEM_LIGHT)

        if explicit != system:
            keys = sorted(set(explicit) | set(system))
            diffs = [
                f"  {k}: 显式={explicit.get(k)!r} 跟随系统={system.get(k)!r}"
                for k in keys
                if explicit.get(k) != system.get(k)
            ]
            self.fail("两块浅色令牌不一致，改色时容易只改一处：\n"
                      + "\n".join(diffs))

    def test_token_blocks_are_not_empty(self):
        """防止正则失效后拿两个空字典互相比对，还自认为通过。"""
        for name, pattern in (("显式浅色", self.EXPLICIT_LIGHT),
                              ("跟随系统浅色", self.SYSTEM_LIGHT)):
            tokens = self._tokens(pattern)
            self.assertGreater(
                len(tokens), 10,
                f"{name}块里应当抽出完整的一组令牌，实际只有 {len(tokens)} 个",
            )


class TestPwaContract(unittest.TestCase):
    """PWA 相关的跨页契约。

    这些断言防的是「装得上但离线打不开」这类沉默故障 ——
    它们在浏览器里表现为「有时候能用」，最难排查。
    """

    MANIFEST = "manifest.webmanifest"

    def manifest(self):
        return json.loads(read(self.MANIFEST))

    def test_manifest_link_present(self):
        """每个页面都要声明 manifest，且路径跟着目录层级走。"""
        for page in ALL_PAGES:
            with self.subTest(page=page):
                link = next(
                    (l for l in parse(page).find_all("link")
                     if l.attrs.get("rel") == "manifest"),
                    None,
                )
                self.assertIsNotNone(link, f"{page} 缺少 manifest 声明")
                href = link.attrs.get("href", "")
                target = os.path.normpath(os.path.join(os.path.dirname(page), href))
                self.assertTrue(exists(target),
                                f"{page} 的 manifest 指向了不存在的 {href}")

    def test_manifest_is_valid_json_with_required_fields(self):
        m = self.manifest()
        for field in ("name", "short_name", "start_url", "scope", "display", "icons"):
            with self.subTest(field=field):
                self.assertIn(field, m, f"manifest 缺少 {field}")
        self.assertEqual(m["scope"], "/", "scope 必须是 /，否则装到子路径会失效")
        self.assertIn(m["display"], ("standalone", "fullscreen", "minimal-ui"),
                      "display 值不合法，无法安装")
        self.assertTrue(m["icons"], "manifest 的 icons 不能为空")

    def test_manifest_icons_exist_and_size_matches(self):
        """图标的 sizes 字段必须与文件真实尺寸一致。

        写错时 manifest 本身仍然「合法」，浏览器也照装，
        但图标会被拉伸变形 —— 只有读 PNG 文件头才抓得到。
        """
        for icon in self.manifest()["icons"]:
            with self.subTest(src=icon["src"]):
                rel = icon["src"].lstrip("/")
                self.assertTrue(exists(rel), f"图标不存在：{icon['src']}")
                width, height = png_size(read_bytes(rel))
                self.assertEqual(f"{width}x{height}", icon["sizes"],
                                 f"{icon['src']} 的真实尺寸 {width}x{height} "
                                 f"与声明的 {icon['sizes']} 不符")

    def test_manifest_has_maskable_icon(self):
        """没有 maskable 图标时，Android 会把图标塞进白底方块里裁，很难看。"""
        purposes = " ".join(i.get("purpose", "") for i in self.manifest()["icons"])
        self.assertIn("maskable", purposes, "缺少 purpose=maskable 的图标")

    def test_manifest_icon_paths_are_absolute(self):
        """图标路径必须是绝对的。

        用相对路径时 blog/ 下的页面会把清单解释成 /blog/assets/...，
        图标 404 且没有任何提示 —— 这正是本测试存在的理由。
        """
        for icon in self.manifest()["icons"]:
            with self.subTest(src=icon["src"]):
                self.assertTrue(icon["src"].startswith("/"),
                                f"图标路径必须是绝对路径：{icon['src']}")

    def test_theme_color_meta(self):
        """每个页面两个 theme-color，各带 media，覆盖深/浅两套系统偏好。"""
        for page in ALL_PAGES:
            with self.subTest(page=page):
                metas = [m for m in parse(page).find_all("meta")
                         if m.attrs.get("name") == "theme-color"]
                self.assertEqual(len(metas), 2,
                                 f"{page} 应有 2 个 theme-color（深/浅各一），实际 {len(metas)}")
                medias = [m.attrs.get("media", "") for m in metas]
                self.assertTrue(any("dark" in x for x in medias),
                                f"{page} 缺少 prefers-color-scheme: dark 的 theme-color")
                self.assertTrue(any("light" in x for x in medias),
                                f"{page} 缺少 prefers-color-scheme: light 的 theme-color")
                for m in metas:
                    self.assertRegex(m.attrs.get("content", ""), r"^#[0-9a-fA-F]{6}$",
                                     f"{page} 的 theme-color 不是合法的十六进制颜色")

    def test_apple_touch_icon(self):
        for page in ALL_PAGES:
            with self.subTest(page=page):
                link = next(
                    (l for l in parse(page).find_all("link")
                     if l.attrs.get("rel") == "apple-touch-icon"),
                    None,
                )
                self.assertIsNotNone(link, f"{page} 缺少 apple-touch-icon")
                href = link.attrs.get("href", "")
                target = os.path.normpath(os.path.join(os.path.dirname(page), href))
                self.assertTrue(exists(target),
                                f"{page} 的 apple-touch-icon 指向了不存在的 {href}")

    def test_service_worker_at_root(self):
        """SW 必须在站点根目录。

        放进 assets/ 时作用域会被限制在 /assets/，
        拦不到页面导航 —— 站点看起来「注册成功了」但完全不能离线。
        """
        self.assertTrue(exists("sw.js"), "sw.js 必须放在仓库根目录（不在 assets/）")
        self.assertFalse(exists("assets/sw.js"), "sw.js 不该放在 assets/ 下")

    def test_precache_list_files_exist(self):
        """预缓存清单里的每个路径都必须真实存在。

        写错时安装阶段会被 allSettled 悄悄吞掉（这是有意的容错），
        表现为「装是装上了，某个页面就是离线打不开」。
        """
        src = read("sw.js")
        m = re.search(r"const PRECACHE = \[(.*?)\];", src, re.S)
        self.assertIsNotNone(m, "在 sw.js 里找不到 PRECACHE 清单")
        urls = re.findall(r"'([^']+)'", m.group(1))
        self.assertTrue(urls, "PRECACHE 是空的")
        for u in urls:
            with self.subTest(url=u):
                # '/' 在文件系统上映射到 index.html
                path = "index.html" if u == "/" else u.lstrip("/")
                self.assertTrue(exists(path), f"预缓存清单里的 {u} 不存在")

    def test_precache_has_no_duplicates(self):
        src = read("sw.js")
        m = re.search(r"const PRECACHE = \[(.*?)\];", src, re.S)
        urls = re.findall(r"'([^']+)'", m.group(1))
        self.assertEqual(len(urls), len(set(urls)), "预缓存清单里有重复项")

    def test_offline_assets_are_precached(self):
        """离线页和它的脚本必须进预缓存，否则离线时回退到一个打不开的页面。"""
        src = read("sw.js")
        m = re.search(r"const PRECACHE = \[(.*?)\];", src, re.S)
        urls = set(re.findall(r"'([^']+)'", m.group(1)))
        self.assertIn("/offline.html", urls, "offline.html 必须在预缓存清单里")
        self.assertIn("/assets/offline.js", urls, "offline.js 必须在预缓存清单里")

    def test_sw_cache_version_is_declared(self):
        """缓存版本号存在且格式正确 —— 发布新内容时靠改它来让用户看到更新。"""
        src = read("sw.js")
        m = re.search(r"const CACHE_VERSION = '([^']+)'", src)
        self.assertIsNotNone(m, "sw.js 必须有 CACHE_VERSION 常量")
        self.assertRegex(m.group(1), r"^v\d+$", "CACHE_VERSION 格式应为 v1、v2 …")

    def test_sw_uses_absolute_registration_path(self):
        """注册路径必须是 /sw.js。

        写相对路径 'sw.js' 时，blog/ 下的页面会去找 /blog/sw.js → 404。
        """
        src = read("assets/pwa.js")
        self.assertIn("register('/sw.js'", src,
                      "pwa.js 必须以绝对路径 '/sw.js' 注册 Service Worker")

    def test_sw_does_not_skip_waiting_unconditionally(self):
        """skipWaiting 只能由 message 事件触发。

        在 install 里无条件调用会让用户正在阅读的页面被突然替换。
        """
        src = read("sw.js")
        # 去掉注释再判断，避免注释里的文字造成误报
        code = re.sub(r"//.*?$|/\*.*?\*/", "", src, flags=re.S | re.M)
        install_block = code[code.find("addEventListener('install'"):code.find("addEventListener('activate'")]
        self.assertNotIn("skipWaiting", install_block,
                         "install 阶段不应调用 skipWaiting（应由用户确认更新后触发）")
        self.assertIn("SKIP_WAITING", code, "sw.js 应当处理 SKIP_WAITING 消息")


class TestOfflinePage(unittest.TestCase):
    """离线页的专属契约。它不在 PAGES 里，页脚/导航结构与常规页不同。"""

    def test_csp_matches_base(self):
        csp = next(
            (m for m in parse(OFFLINE_PAGE).find_all("meta")
             if (m.attrs.get("http-equiv") or "").lower() == "content-security-policy"),
            None,
        )
        self.assertIsNotNone(csp, "offline.html 缺少 meta CSP")
        expected = headers_csp()
        self.assertEqual(csp.attrs.get("content"),
                         expected[: -len("; frame-ancestors 'none'")])

    def test_does_not_register_service_worker(self):
        """离线页不该注册 SW：已经离线了，再注册只会制造噪音。"""
        srcs = [s.attrs.get("src") for s in parse(OFFLINE_PAGE).find_all("script")]
        self.assertNotIn("assets/pwa.js", srcs,
                         "offline.html 不应加载 pwa.js（离线时注册没有意义）")

    def test_has_link_back_to_cached_articles(self):
        """离线页必须给出可点的文章链接，否则用户被卡在死路上。"""
        links = [a.attrs.get("href", "") for a in parse(OFFLINE_PAGE).find_all("a")]
        posts = [h for h in links if re.search(r"post-\d+\.html$", h)]
        expected = len([p for p in PAGES if re.search(r"post-\d+\.html$", p)])
        self.assertEqual(len(posts), expected,
                         f"离线页应链接全部 {expected} 篇文章，实际 {len(posts)}")

    def test_listed_post_titles_match_real_pages(self):
        """离线页列的文章标题必须与真实页面一致。

        手抄标题极易出错（写错的时候页面仍然「正常」，
        只是挂着一个不存在的文章名），所以这里比对真值。
        """
        doc = parse(OFFLINE_PAGE)
        listed = {}
        for a in doc.find_all("a"):
            href = a.attrs.get("href", "")
            m = re.search(r"(post-\d+\.html)$", href)
            if m:
                listed[m.group(1)] = a.text.strip()

        for name, shown in listed.items():
            with self.subTest(post=name):
                real = parse(f"blog/{name}").find("title").text
                # 真实 title 形如「标题 · xiaoyu-hue」，取「 · 」前的部分
                real_title = real.split("·")[0].strip()
                self.assertEqual(shown, real_title,
                                 f"离线页里的标题与 {name} 不符")

    def test_has_retry_control(self):
        """离线页要给一个重试入口，否则用户只能自己想别的办法。"""
        self.assertIn("offline-retry", read(OFFLINE_PAGE),
                      "offline.html 缺少重试按钮")

    def test_footer_signature_identical(self):
        sign = parse(OFFLINE_PAGE).find(cls="sign")
        self.assertIsNotNone(sign, "offline.html 没有签名")
        self.assertEqual(sign.text, SIGNATURE)


class Test404Page(unittest.TestCase):
    """404 页的专属契约。

    此前 404.html 完全不在测试覆盖里（既不在 PAGES，也没有专属测试类）——
    改坏它没有任何测试会响。它是被托管平台在所有未知路径上返回的页面，
    出问题时用户看到的是一张白页，而本地访问任何真实文件都发现不了。
    """

    PAGE = "404.html"

    def test_exists(self):
        self.assertTrue(exists(self.PAGE), "仓库应包含 404.html")

    def test_has_csp(self):
        csp = next(
            (m for m in parse(self.PAGE).find_all("meta")
             if (m.attrs.get("http-equiv") or "").lower() == "content-security-policy"),
            None,
        )
        self.assertIsNotNone(csp, "404.html 缺少 meta CSP")
        expected = headers_csp()
        self.assertEqual(csp.attrs.get("content"),
                         expected[: -len("; frame-ancestors 'none'")])

    def test_uses_root_relative_asset_paths(self):
        """404 会在任意深度被返回，资源路径必须相对站点根，不能是 ../。

        写成 "../assets/..." 时，/blog/x/y 这类深层路径下会解析到错误位置，
        页面直接失去样式。这是 404 页最容易踩、又最难在本地复现的坑。
        """
        text = read(self.PAGE)
        for ref in re.findall(r'(?:src|href)="([^"]+\.(?:css|js))"', text):
            self.assertFalse(ref.startswith(".."),
                             f"404.html 的资源路径 {ref!r} 用了 ../，深层路径下会失效")
            self.assertFalse(ref.startswith("/"),
                             f"404.html 的资源路径 {ref!r} 用了绝对路径，"
                             f"GitHub Pages 子路径部署下会失效")

    def test_canonical_points_to_404(self):
        """模板里 canonical 是固定行，404 页保留它并指向 /404.html。

        这里锁住它的取值，避免哪天 rel 前缀改动时把 404 的 canonical
        拼成了别的东西（比如带 ../ 的错误路径）。
        """
        canon = [m for m in parse(self.PAGE).find_all("link")
                 if (m.attrs.get("rel") or "").lower() == "canonical"]
        self.assertEqual(len(canon), 1, "404.html 应恰好有一个 canonical")
        self.assertTrue(canon[0].attrs.get("href", "").endswith("/404.html"),
                        f"404 的 canonical 应指向 /404.html，实际 {canon[0].attrs.get('href')!r}")

    def test_does_not_declare_jsonld(self):
        """404 不是有效内容，给它结构化数据等于邀请搜索引擎收录。"""
        self.assertNotIn("application/ld+json", read(self.PAGE),
                         "404.html 不应包含 JSON-LD")

    def test_gives_way_back(self):
        """必须给出回到首页与博客的出口，否则用户被卡在死路上。"""
        hrefs = [a.attrs.get("href", "") for a in parse(self.PAGE).find_all("a")]
        self.assertIn("index.html", hrefs, "404.html 应给出回首页的链接")
        self.assertIn("blog/index.html", hrefs, "404.html 应给出回博客的链接")

    def test_carries_noindex(self):
        """404 必须带 noindex。

        托管平台会在任意未知路径返回这一页，不加 noindex 的话
        搜索引擎会把每一个失效 URL 都当成可索引页面收进去。
        """
        metas = parse(self.PAGE).find_all("meta")
        robots = next(
            (m for m in metas if (m.attrs.get("name") or "").lower() == "robots"),
            None,
        )
        self.assertIsNotNone(robots, "404.html 缺少 meta robots")
        self.assertIn("noindex", (robots.attrs.get("content") or "").lower(),
                      "404.html 的 robots 应含 noindex")


if __name__ == "__main__":
    unittest.main()
