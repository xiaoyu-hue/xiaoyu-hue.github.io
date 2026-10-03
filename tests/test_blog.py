"""博客列表页与文章之间的一致性。

卡片标题、文章标题、链接三者必须同步,改了一个忘了另外两个是最常见的翻车方式。
"""

import os
import unittest

from tests.support import PAGES, exists, parse

BLOG_INDEX = "blog/index.html"

def expected_order():
    """列表页应有的顺序：日期倒序，同一天里编号倒序（新写的在前）。

    这个顺序是从每篇文章自己的 <div class="date"> 和文件编号算出来的，
    不是写死的一张表。写死的话每加一篇文章都得回来改一次，忘了改就误报；
    改成算出来之后，「不小心打乱排序」依然会被抓到 —— 因为比对的是
    「实际卡片顺序」与「应有的顺序」，两边来源不同，仍然对得上才算通过。
    """
    import re
    rows = []
    for name in os.listdir("blog"):
        m = re.match(r"^post-(\d+)\.html$", name)
        if not m:
            continue
        doc = parse(os.path.join("blog", name))
        node = doc.find(cls="date")
        if node is None:
            raise AssertionError("%s 缺少 <div class='date'>，无法判断它该排在哪" % name)
        date = node.text.strip().split()[0]
        rows.append((date, int(m.group(1)), name))
    rows.sort(key=lambda r: (r[0], r[1]), reverse=True)
    return [r[2] for r in rows]


def cards():
    return parse(BLOG_INDEX).find_all(cls="post-card")


class TestPostCards(unittest.TestCase):
    def test_card_count_and_order(self):
        want = expected_order()
        hrefs = [c.attrs.get("href") for c in cards()]
        self.assertEqual(
            hrefs, want,
            f"文章卡片的数量或顺序变了（应为 {want},实际 {hrefs}）",
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
        for name in expected_order():
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


def post_pages():
    """所有文章页（blog/post-*.html）—— 与 PAGES 同源，随目录自动增减。"""
    return [p for p in PAGES if p.startswith("blog/post-")]


class TestArticleContract(unittest.TestCase):
    def test_each_post_has_back_link(self):
        for page in post_pages():
            with self.subTest(post=page):
                back = next(
                    (a for a in parse(page).find_all("a")
                     if a.attrs.get("href") == "index.html"),
                    None,
                )
                self.assertIsNotNone(back, f"{page} 缺少返回博客的链接")

    def test_each_post_has_article_body(self):
        for page in post_pages():
            with self.subTest(post=page):
                article = parse(page).find(cls="article")
                self.assertIsNotNone(article, f"{page} 没有 .article 容器")
                self.assertIsNotNone(article.find("h1"), f"{page} 的正文没有标题")
                paragraphs = article.find_all("p")
                self.assertGreaterEqual(
                    len(paragraphs), 3,
                    f"{page} 的正文段落太少（{len(paragraphs)} 段）,可能内容没渲染出来",
                )

    def test_blog_index_has_heading(self):
        doc = parse(BLOG_INDEX)
        self.assertIsNotNone(doc.find("h1") or doc.find("h2"),
                             "博客列表页缺少标题")


if __name__ == "__main__":
    unittest.main()
