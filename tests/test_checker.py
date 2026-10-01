"""检查器自检：证明 scripts/check_integrity.py 真的能抓到问题。

一个不会失败的检查比没有检查更危险 —— 它给人虚假的安全感。

注意：样本全部写在临时目录里。检查器会递归扫描自己所在目录的父目录,
如果把 .html 样本放进仓库,会把真实的检查结果污染掉。
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKER = os.path.join("scripts", "check_integrity.py")
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; "
    "img-src 'self' data:; connect-src 'none'; object-src 'none'; "
    "base-uri 'self'; form-action 'none'"
)

CLEAN_PAGE = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>t</title>
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="strict-origin-when-cross-origin">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<a href="other.html">ok</a>
<script src="assets/main.js"></script>
</body>
</html>
"""

OTHER_PAGE = CLEAN_PAGE.replace('<a href="other.html">ok</a>', "")


def build_site(tmp, pages):
    """在临时目录里搭一个最小站点,并把真实的检查器复制进去。"""
    os.makedirs(os.path.join(tmp, "scripts"), exist_ok=True)
    shutil.copyfile(os.path.join(ROOT, CHECKER), os.path.join(tmp, CHECKER))
    # 样本会引用这两个资源,补上占位文件,否则死链检查会因为样本自身不完整而误报
    os.makedirs(os.path.join(tmp, "assets"), exist_ok=True)
    for name in ("style.css", "main.js"):
        with open(os.path.join(tmp, "assets", name), "w", encoding="utf-8") as fh:
            fh.write("/* placeholder */\n")
    for rel, content in pages.items():
        path = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)


def run_checker(tmp):
    proc = subprocess.run(
        [sys.executable, os.path.join(tmp, CHECKER)],
        capture_output=True, text=True, cwd=tmp,
    )
    return proc


class TestCheckerCatchesProblems(unittest.TestCase):
    def run_case(self, pages):
        with tempfile.TemporaryDirectory() as tmp:
            build_site(tmp, pages)
            proc = run_checker(tmp)
        # 关键:Python 未捕获异常的退出码也是 1,只看退出码会把
        # 「检查器自己崩了」误判成「检查器发现了问题」。
        self.assertNotIn("Traceback", proc.stderr,
                         "检查器抛异常了,不是发现了问题:\n" + proc.stderr)
        return proc

    def test_clean_site_passes(self):
        proc = self.run_case({"index.html": CLEAN_PAGE, "other.html": OTHER_PAGE})
        self.assertEqual(proc.returncode, 0, "干净站点应当通过:\n" + proc.stdout)

    def test_detects_dead_link(self):
        pages = {"index.html": CLEAN_PAGE.replace("other.html", "missing.html")}
        proc = self.run_case(pages)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[死链]", proc.stdout)

    def test_detects_missing_csp(self):
        pages = {"index.html": CLEAN_PAGE.replace(
            f'<meta http-equiv="Content-Security-Policy" content="{CSP}">\n', "")}
        proc = self.run_case(pages)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[缺 CSP]", proc.stdout)

    def test_detects_weakened_csp(self):
        pages = {"index.html": CLEAN_PAGE.replace(CSP, CSP + "; script-src 'self' 'unsafe-inline'")}
        proc = self.run_case(pages)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("unsafe-inline", proc.stdout)

    def test_detects_third_party_resource(self):
        pages = {"index.html": CLEAN_PAGE.replace(
            '<link rel="stylesheet" href="assets/style.css">',
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css">')}
        proc = self.run_case(pages)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[第三方资源]", proc.stdout)

    def test_detects_inline_script(self):
        pages = {"index.html": CLEAN_PAGE.replace(
            '<script src="assets/main.js"></script>',
            '<script>var a = 1;</script>')}
        proc = self.run_case(pages)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[内联脚本]", proc.stdout)

    def test_detects_inline_event_attribute(self):
        pages = {"index.html": CLEAN_PAGE.replace("<body>", '<body onclick="x()">')}
        proc = self.run_case(pages)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[事件属性]", proc.stdout)

    def test_detects_ignored_csp_directive(self):
        """frame-ancestors 通过 <meta> 下发会被浏览器忽略,检查器必须拦住它。"""
        pages = {"index.html": CLEAN_PAGE.replace(CSP, CSP + "; frame-ancestors 'none'")}
        proc = self.run_case(pages)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[无效指令]", proc.stdout)


class TestCheckerIgnoresTooling(unittest.TestCase):
    def test_node_modules_is_skipped(self):
        """测试工具链生成的 .html 不是站点内容,不该被当成缺 CSP 的页面。"""
        pages = {
            "index.html": CLEAN_PAGE,
            "other.html": OTHER_PAGE,
            "node_modules/pkg/report.html": "<html><body>x</body></html>",
            "playwright-report/index.html": "<html><body>x</body></html>",
        }
        with tempfile.TemporaryDirectory() as tmp:
            build_site(tmp, pages)
            proc = run_checker(tmp)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(proc.returncode, 0,
                         "工具链产物不应影响检查:\n" + proc.stdout)


if __name__ == "__main__":
    unittest.main()
