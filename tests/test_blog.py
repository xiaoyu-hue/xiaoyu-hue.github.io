"""博客列表页与文章之间的一致性。

卡片标题、文章标题、链接三者必须同步,改了一个忘了另外两个是最常见的翻车方式。
"""

import os
import unittest

from tests.support import exists, parse

BLOG_INDEX = "blog/index.html"

# 列表页的展示顺序：按日期倒序，同一天内新写的排在前面。
# 写死这个顺序是为了让「不小心打乱排序」变成一次测试失败，
# 而不是等读者发现列表排列奇怪。
EXPECTED_ORDER = [
    "post-8.html",   # 2026-10-01 读书摘录
    "post-7.html",   # 2026-10-01 随笔
    "post-6.html",   # 2026-10-01 随笔
    "post-5.html",   # 2026-10-01 项目故事
    "post-4.html",   # 2026-10-01 项目故事
    "post-3.html",   # 2026-10-01 项目故事
    "post-2.html",   # 2026-10-01 项目故事
    "post-1.html",   # 2026-09-30 关于方法
]


def cards():
    return parse(BLOG_INDEX).find_all(cls="post-card")


class TestPostCards(unittest.TestCase):
    def test_card_count_and_order(self):
        hrefs = [c.attrs.get("href") for c in cards()]
        self.assertEqual(
            hrefs, EXPECTED_ORDER,
            f"文章卡片的数量或顺序变了（应为 {EXPECTED_ORDER},实际 {hrefs}）",
        )

    def test_card_links_resolve(self):
        for card in cards():
            href = card.attrs.get("href", "")
            with self.subTest(card=href):
                self.assertTrue(href, "卡片缺少 href")
                self.assertTrue(
                    exists(os.path.join("blog", href)),
                    f"卡片指向的文章不存在: {href}",
                )

    def test_every_post_has_a_card(self):
        linked = {c.attrs.get("href") for c in cards()}
        for name in EXPECTED_ORDER:
            with self.subTest(post=name):
                self.assertIn(name, linked, f"{name} 没有被列表页收录")

    def test_card_title_matches_article_heading(self):
        """卡片标题和文章 <h1> 必须逐字一致。"""
        for card in cards():
            href = card.attrs.get("href")
            with self.subTest(card=href):
                heading = card.find("h3")
                self.assertIsNotNone(heading, f"卡片 {href} 没有标题")
                card_title = heading.text.strip()

                article = parse(os.path.join("blog", href)).find("h1")
                self.assertIsNotNone(article, f"{href} 没有 <h1>")
                self.assertEqual(
                    card_title, article.text.strip(),
                    f"卡片标题与 {href} 的标题不一致:\n"
                    f"  卡片: {card_title}\n  文章: {article.text.strip()}",
                )


class TestArticleContract(unittest.TestCase):
    def test_each_post_has_back_link(self):
        for name in EXPECTED_ORDER:
            with self.subTest(post=name):
                page = os.path.join("blog", name)
                back = next(
                    (a for a in parse(page).find_all("a")
                     if a.attrs.get("href") == "index.html"),
                    None,
                )
                self.assertIsNotNone(back, f"{name} 缺少返回博客的链接")

    def test_each_post_has_article_body(self):
        for name in EXPECTED_ORDER:
            with self.subTest(post=name):
                page = os.path.join("blog", name)
                article = parse(page).find(cls="article")
                self.assertIsNotNone(article, f"{name} 没有 .article 容器")
                self.assertIsNotNone(article.find("h1"), f"{name} 的正文没有标题")
                paragraphs = article.find_all("p")
                self.assertGreaterEqual(
                    len(paragraphs), 3,
                    f"{name} 的正文段落太少（{len(paragraphs)} 段）,可能内容没渲染出来",
                )

    def test_blog_index_has_heading(self):
        doc = parse(BLOG_INDEX)
        self.assertIsNotNone(doc.find("h1") or doc.find("h2"),
                             "博客列表页缺少标题")


if __name__ == "__main__":
    unittest.main()
