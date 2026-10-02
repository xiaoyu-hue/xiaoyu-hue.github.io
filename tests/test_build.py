"""build.py 的单元测试：JSON-LD 转义与机器可读产物。

为什么要单独测这些：
- JSON-LD 逃逸（标题里含 </script>）是"页面照样好看、搜索引擎静默失效、
  甚至能执行脚本"的一类问题，靠人眼和页面级测试都看不出来。
- sitemap / robots / feed / 404 是"没有页面会直接显示给用户"的产物，
  出错了没人会立刻发现 —— 只能靠测试盯着。
"""

import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import build  # noqa: E402


SITE = {
    "base_url": "https://example.com",
    "author": "xiaoyu-hue",
    "lang": "zh-CN",
    "feed_title": "示例源",
    "csp_meta": "default-src 'self'",
}


class TestJsonLdEscape(unittest.TestCase):
    """json_ld_script：内联 JSON-LD 必须防住 </script> 逃逸。"""

    def test_escapes_closing_script_tag(self):
        blob = {"@type": "WebSite", "name": "x</script><script>alert(1)</script>"}
        out = build.json_ld_script(blob)
        self.assertNotIn("</script", out.lower(),
                         "含 </script> 的字段未被转义，会提前闭合脚本块")
        self.assertNotIn("<script", out.lower(), "不应出现可解析的 <script")

    def test_escaped_output_is_still_valid_json(self):
        blob = {"@type": "WebSite", "name": "x</script><script>alert(1)</script>"}
        out = build.json_ld_script(blob)
        # 转义不能改变语义：解析回来必须与原对象逐字段相等
        self.assertEqual(json.loads(out), blob)

    def test_escapes_any_less_than(self):
        out = build.json_ld_script({"v": "a<b"})
        self.assertIn("\\u003c", out)
        self.assertEqual(json.loads(out), {"v": "a<b"})

    def test_keeps_non_ascii_readable(self):
        """ensure_ascii=False 保住了中文可读性，不该被转义方案破坏。"""
        out = build.json_ld_script({"name": "中文标题"})
        self.assertIn("中文标题", out)


class TestRenderHeadExtraEscapesTitle(unittest.TestCase):
    """端到端：一个恶意标题走完整条渲染链，产物里不能出现逃逸。"""

    def test_malicious_title_does_not_break_script_block(self):
        meta = {
            "url_path": "blog/post-1.html",
            "og_type": "article",
            "title": '正常标题</script><script>alert(1)</script>',
            "description": "d",
            "date": "2026-01-01",
        }
        out = build.render_head_extra(SITE, "blog/post-1.html", meta)
        # 只应有一个 </script>（我们自己写的收尾），且它前面没有多余的 <script
        self.assertEqual(out.lower().count("</script>"), 1,
                         "出现了额外的 </script>，说明注入逃逸发生了")
        self.assertNotIn("<script>alert", out)


class TestSitemap(unittest.TestCase):
    def setUp(self):
        self.pages = {
            "index.html": {"url_path": "index.html", "date": None},
            "blog/post-1.html": {"url_path": "blog/post-1.html", "date": "2026-01-02"},
        }

    def test_well_formed_and_absolute(self):
        xml = build.render_sitemap(SITE, self.pages)
        self.assertTrue(xml.startswith('<?xml version="1.0" encoding="UTF-8"?>'))
        self.assertIn("<urlset", xml)
        for url in re.findall(r"<loc>(.*?)</loc>", xml):
            self.assertTrue(url.startswith("https://example.com/"),
                            f"sitemap 里的地址不是绝对地址: {url}")

    def test_lastmod_only_when_date_present(self):
        """没有日期的页面不写 lastmod —— 编日期等于给搜索引擎喂假信号。"""
        xml = build.render_sitemap(SITE, self.pages)
        # 只有一个页面带 date，因此 lastmod 只应出现一次
        self.assertEqual(xml.count("<lastmod>"), 1)

    def test_escapes_special_chars_in_url(self):
        pages = {"a.html": {"url_path": "a.html?x=1&y=2", "date": None}}
        xml = build.render_sitemap(SITE, pages)
        self.assertIn("&amp;", xml, "URL 里的 & 未转义会让 sitemap 非法")
        self.assertNotIn("&y=", xml)


class TestRobots(unittest.TestCase):
    def test_allows_all_and_points_to_sitemap(self):
        txt = build.render_robots(SITE)
        self.assertIn("User-agent: *", txt)
        self.assertIn("Allow: /", txt)
        self.assertIn("Sitemap: https://example.com/sitemap.xml", txt)


class TestFeed(unittest.TestCase):
    def setUp(self):
        self.pages = {
            "blog/index.html": {"url_path": "blog/index.html",
                                "description": "博客列表", "date": None},
            "blog/post-1.html": {"url_path": "blog/post-1.html",
                                 "title": "标题 & 符号", "description": "d1",
                                 "date": "2026-01-02"},
            "blog/post-2.html": {"url_path": "blog/post-2.html",
                                 "title": "第二篇", "description": "d2",
                                 "date": "2026-01-05"},
        }
        self.bodies = {
            "blog/post-1.html": '<a href="post-2.html">next</a>',
            "blog/post-2.html": "<p>正文</p>",
        }

    def test_posts_sorted_newest_first(self):
        xml = build.render_feed(SITE, self.pages, self.bodies)
        i1 = xml.find("第二篇")
        i2 = xml.find("标题 &amp; 符号")
        self.assertGreater(i1, -1)
        self.assertGreater(i2, -1)
        self.assertLess(i1, i2, "RSS 条目应按日期倒序（新的在前）")

    def test_list_page_is_not_an_item(self):
        xml = build.render_feed(SITE, self.pages, self.bodies)
        self.assertEqual(xml.count("<item>"), 2, "首页/列表页不应被当成 RSS 条目")

    def test_relative_links_absolutized_in_body(self):
        """RSS 阅读器脱离页面上下文，相对链接必须变成绝对地址。"""
        xml = build.render_feed(SITE, self.pages, self.bodies)
        self.assertIn('href="https://example.com/blog/post-2.html"', xml)
        self.assertNotIn('href="post-2.html"', xml)

    def test_title_escaped_in_channel_and_items(self):
        xml = build.render_feed(SITE, self.pages, self.bodies)
        # 标题里的 & 必须转义，否则 RSS 源非法（浏览器会直接拒收）
        self.assertIn("标题 &amp; 符号", xml)


class TestRfc822Date(unittest.TestCase):
    def test_formats_as_rfc822(self):
        self.assertEqual(build.rfc822_date("2026-01-02"),
                         "Fri, 02 Jan 2026 00:00:00 GMT")


class TestXmlEscape(unittest.TestCase):
    def test_escapes_all_four_entities(self):
        self.assertEqual(build.xml_escape('a&b<c>d"e'),
                         "a&amp;b&lt;c&gt;d&quot;e")


if __name__ == "__main__":
    unittest.main()
