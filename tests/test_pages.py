"""7 个页面的结构与文案契约。

改页面时最容易悄悄破坏的就是这些「每页都一样」的东西,靠人眼是看不住的。
"""

import os
import unittest

from tests.support import (
    PAGES,
    SIGNATURE,
    exists,
    headers_csp,
    parse,
    read,
)

EXPECTED_CSS = {"index.html": "assets/style.css"}
DEFAULT_CSS = "../assets/style.css"

EXPECTED_REVEAL_COUNT = {
    "index.html": 11,
    "blog/index.html": 6,
    "blog/post-1.html": 1,
    "blog/post-2.html": 1,
    "blog/post-3.html": 1,
    "blog/post-4.html": 1,
    "blog/post-5.html": 1,
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


if __name__ == "__main__":
    unittest.main()
