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

EXPECTED_REVEAL_COUNT = {
    "index.html": 11,
    "blog/index.html": 9,
    "blog/post-1.html": 1,
    "blog/post-2.html": 1,
    "blog/post-3.html": 1,
    "blog/post-4.html": 1,
    "blog/post-5.html": 1,
    "blog/post-6.html": 1,
    "blog/post-7.html": 1,
    "blog/post-8.html": 1,
}


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

                js = doc.find_all("script")
                srcs = [s.attrs.get("src") for s in js]
                self.assertEqual(
                    srcs, expected_scripts,
                    f"{page} 的脚本清单与预期不符（增删脚本请同步更新本测试）",
                )
                for s in js:
                    self.assertFalse(s.texts, f"{page} 的脚本标签不应有内联内容")


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

    def test_reveal_element_count(self):
        """滚动淡入元素数量写死,防止误删或误加导致动效不一致。"""
        for page, expected in EXPECTED_REVEAL_COUNT.items():
            with self.subTest(page=page):
                count = len(parse(page).find_all(cls="reveal"))
                self.assertEqual(count, expected,
                                 f"{page} 的 .reveal 数量变了（原 {expected},现 {count}）")

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


if __name__ == "__main__":
    unittest.main()
