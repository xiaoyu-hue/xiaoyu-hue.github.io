"""检查器自检：证明 scripts/check_integrity.py 真的能抓到问题。

一个不会失败的检查比没有检查更危险 —— 它给人虚假的安全感。

注意：样本全部写在临时目录里。检查器会递归扫描自己所在目录的父目录,
如果把 .html 样本放进仓库,会把真实的检查结果污染掉。
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKER = os.path.join("scripts", "check_integrity.py")


def _csp_from_checker():
    """从检查器源码里提取 EXPECTED_CSP,而不是在这里再抄一份。

    抄一份的问题是:以后改 CSP 要改两个地方,忘了改这里,
    样本就会自带旧策略,测试会「通过」但检查器其实已经在报不一致 ——
    测了个假东西。让真值只有一个来源。
    """
    src = open(os.path.join(ROOT, CHECKER), encoding="utf-8").read()
    m = re.search(r"EXPECTED_CSP\s*=\s*\((.*?)\)", src, re.S)
    if not m:
        raise AssertionError("在 check_integrity.py 里找不到 EXPECTED_CSP")
    return "".join(re.findall(r'"([^"]*)"', m.group(1)))


CSP = _csp_from_checker()

CLEAN_PAGE = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>t</title>
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="strict-origin-when-cross-origin">
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#04111d" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#eaf4fb" media="(prefers-color-scheme: light)">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<a href="other.html">ok</a>
{'''<button type="button" data-motion-option="on" aria-pressed="false">开启</button>
<button type="button" data-motion-option="off" aria-pressed="false">关闭</button>'''}
<script src="assets/main.js"></script>
</body>
</html>
"""

OTHER_PAGE = CLEAN_PAGE.replace('<a href="other.html">ok</a>', "")

# 动效开关的「关闭」按钮，抽成常量方便在用例里精确删除
# （测试「只加了一半开关」这种漏写场景）。
MOTION_OFF = '<button type="button" data-motion-option="off" aria-pressed="false">关闭</button>'

# 检查器现在还会校验 PWA 资产，样本站点必须自带一份最小的，
# 否则「干净站点」会因为缺 manifest / sw.js / offline.html 而报错。
MINI_MANIFEST = """{
  "name": "t",
  "short_name": "t",
  "start_url": "/index.html",
  "scope": "/",
  "display": "standalone",
  "icons": [
    {"src": "/assets/icon.png", "sizes": "192x192", "type": "image/png", "purpose": "any"}
  ]
}
"""

MINI_SW = """const CACHE_VERSION = 'v1';
const PRECACHE = ['/index.html', '/offline.html'];
"""

# 最小合法 PNG（1x1），检查器只验存在性不验尺寸
MINI_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6360000002000100ffff030000060005"
    "57bfab6d0000000049454e44ae426082"
)

# 带完整微动效令牌的最小样式表。检查器现在会校验这些令牌与降级路径，
# 所以样本站点的 style.css 不能是空占位 —— 否则旧测试（比如「干净站点应通过」）
# 会被新检查无差别拦下。这份样式表满足检查器对微动效的全部要求，
# 各测试类再用 mutate() 故意改坏它来触发对应检查。
MINI_STYLE = """\
:root{
  --dur-fast:140ms;--dur-base:240ms;--dur-slow:1600ms;
  --shift-sm:2px;--shift-md:6px;--shift-lg:14px;--stagger-step:40ms;
}
/* 微动效系统 */
.card,.post-card{transition-property:border-color;transition-duration:var(--dur-fast)}
.reveal{opacity:0;transition-property:opacity;transition-delay:40ms}
.prefs-panel{visibility:hidden;opacity:0}
.prefs-panel.is-open{visibility:visible;opacity:1}
:root[data-motion="off"]{--dur-fast:1ms;--dur-base:1ms;--dur-slow:1ms;
  --shift-sm:0px;--shift-md:0px;--shift-lg:0px}
@media(prefers-reduced-motion:reduce){.reveal{transition:none}}
@media(prefers-contrast:more){.reveal{opacity:1}}
@media(scripting:none){.reveal{opacity:1}}
"""

# 不带微动效的占位样式表，供「故意制造缺令牌」类测试使用
BARE_STYLE = "/* placeholder */\n"


def build_site(tmp, pages, style=None):
    """在临时目录里搭一个最小站点,并把真实的检查器复制进去。

    style 默认用 MINI_STYLE（带完整微动效令牌），这样所有
    不关心微动效的测试（死链、CSP、PWA…）不会被新检查无差别拦下。
    需要测试「缺令牌」的用例可传 BARE_STYLE 再 mutate。
    """
    os.makedirs(os.path.join(tmp, "scripts"), exist_ok=True)
    shutil.copyfile(os.path.join(ROOT, CHECKER), os.path.join(tmp, CHECKER))
    # 样本会引用这两个资源,补上占位文件,否则死链检查会因为样本自身不完整而误报
    os.makedirs(os.path.join(tmp, "assets"), exist_ok=True)
    with open(os.path.join(tmp, "assets", "style.css"), "w", encoding="utf-8") as fh:
        fh.write(style if style is not None else MINI_STYLE)
    with open(os.path.join(tmp, "assets", "main.js"), "w", encoding="utf-8") as fh:
        fh.write("/* placeholder */\n")
    # PWA 资产
    with open(os.path.join(tmp, "manifest.webmanifest"), "w", encoding="utf-8") as fh:
        fh.write(MINI_MANIFEST)
    with open(os.path.join(tmp, "sw.js"), "w", encoding="utf-8") as fh:
        fh.write(MINI_SW)
    with open(os.path.join(tmp, "offline.html"), "w", encoding="utf-8") as fh:
        fh.write(CLEAN_PAGE)
    with open(os.path.join(tmp, "assets", "icon.png"), "wb") as fh:
        fh.write(MINI_PNG)
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


class TestCheckerCatchesPwaProblems(unittest.TestCase):
    """PWA 检查项的自检。

    新增的检查如果永远不失败，就等于没有检查 ——
    这里逐项制造故障，证明它真的会红。
    """

    def run_case(self, mutate):
        """mutate(tmp) 在样本站点建好后改坏它。"""
        with tempfile.TemporaryDirectory() as tmp:
            build_site(tmp, {"index.html": CLEAN_PAGE, "other.html": OTHER_PAGE})
            mutate(tmp)
            proc = run_checker(tmp)
        self.assertNotIn("Traceback", proc.stderr,
                         "检查器抛异常了,不是发现了问题:\n" + proc.stderr)
        return proc

    def test_detects_relative_icon_path(self):
        """相对图标路径会让 blog/ 下的页面 404，且没有任何提示。"""
        def mutate(tmp):
            p = os.path.join(tmp, "manifest.webmanifest")
            with open(p, encoding="utf-8") as fh:
                s = fh.read()
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(s.replace('"/assets/icon.png"', '"assets/icon.png"'))
            # 相对路径下这个文件也就不该存在了
            os.remove(os.path.join(tmp, "assets", "icon.png"))

        proc = self.run_case(mutate)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[图标路径]", proc.stdout)

    def test_detects_missing_icon_file(self):
        def mutate(tmp):
            os.remove(os.path.join(tmp, "assets", "icon.png"))

        proc = self.run_case(mutate)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[图标缺失]", proc.stdout)

    def test_detects_precache_dead_link(self):
        """预缓存清单写错时，安装阶段会被静默吞掉，
        表现为「装是装上了，某个页面离线打不开」。"""
        def mutate(tmp):
            p = os.path.join(tmp, "sw.js")
            with open(p, encoding="utf-8") as fh:
                s = fh.read()
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(s.replace("'/offline.html'", "'/offline.html', '/nope.js'"))

        proc = self.run_case(mutate)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[预缓存死链]", proc.stdout)

    def test_detects_sw_in_assets(self):
        """sw.js 放进 assets/ 会限制作用域，站点看起来"注册成功"却不能离线。"""
        def mutate(tmp):
            shutil.move(os.path.join(tmp, "sw.js"),
                        os.path.join(tmp, "assets", "sw.js"))

        proc = self.run_case(mutate)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[SW 位置错误]", proc.stdout)

    def test_detects_missing_manifest_link(self):
        def mutate(tmp):
            p = os.path.join(tmp, "index.html")
            with open(p, encoding="utf-8") as fh:
                s = fh.read()
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(s.replace('<link rel="manifest" href="manifest.webmanifest">', ""))

        proc = self.run_case(mutate)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[缺 manifest 声明]", proc.stdout)

    def test_detects_missing_theme_color(self):
        def mutate(tmp):
            p = os.path.join(tmp, "index.html")
            with open(p, encoding="utf-8") as fh:
                s = fh.read()
            s = s.replace(
                '<meta name="theme-color" content="#04111d" media="(prefers-color-scheme: dark)">\n', ""
            )
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(s)

        proc = self.run_case(mutate)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[theme-color]", proc.stdout)

    def test_detects_invalid_manifest_json(self):
        def mutate(tmp):
            with open(os.path.join(tmp, "manifest.webmanifest"), "w", encoding="utf-8") as fh:
                fh.write("{ this is not json")

        proc = self.run_case(mutate)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[manifest 非法]", proc.stdout)


class TestCheckerCatchesMotionProblems(unittest.TestCase):
    """微动效检查项的自检。

    这些检查针对的都是「沉默失效」：CSS 不报错、JS 测试全绿，
    只有真浏览器里量 computed style 才看得出动效没生效。
    正因如此，检查器自己必须被证明「真的会红」。
    """

    # 页面要带动效开关，否则会被 [微动效] on/off 检查拦下。
    # 动效按钮已内联进 CLEAN_PAGE（见文件顶部），所以这里直接复用，
    # 不要再 replace 一次 —— 否则会变成 on=2/off=2。
    MOTION_PAGE = CLEAN_PAGE

    def run_case(self, mutate, page=None):
        with tempfile.TemporaryDirectory() as tmp:
            # build_site 默认会写入带完整微动效令牌的样式表（见 MINI_STYLE），
            # 因此干净样本应当直接通过；mutate 再故意改坏它来触发对应检查。
            build_site(tmp, {
                "index.html": page or self.MOTION_PAGE,
                "other.html": self.MOTION_PAGE,
            })
            mutate(tmp)
            proc = run_checker(tmp)
        self.assertNotIn("Traceback", proc.stderr,
                         "检查器抛异常了,不是发现了问题:\n" + proc.stderr)
        return proc

    def test_clean_motion_setup_passes(self):
        """干净样本必须通过，否则后面每条断言都无从判断。"""
        proc = self.run_case(lambda tmp: None)
        self.assertEqual(proc.returncode, 0,
                         "带完整微动效的最小站点应当通过:\n" + proc.stdout)

    def test_detects_missing_token(self):
        def mutate(tmp):
            p = os.path.join(tmp, "assets", "style.css")
            s = open(p, encoding="utf-8").read()
            open(p, "w", encoding="utf-8").write(s.replace("--stagger-step:40ms", ""))

        proc = self.run_case(mutate)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("[微动效] style.css 缺少令牌 --stagger-step", proc.stdout)

    def test_detects_missing_master_switch(self):
        def mutate(tmp):
            p = os.path.join(tmp, "assets", "style.css")
            s = open(p, encoding="utf-8").read()
            # 总开关选择器是 :root[data-motion="off"]，删掉这一行
            # 即可让检查器找不到开关。注意只删选择器前缀，
            # 不要连带删后面的令牌（那会变成另一类问题）。
            open(p, "w", encoding="utf-8").write(
                s.replace(':root[data-motion="off"]', ""))

        proc = self.run_case(mutate)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("缺少 html[data-motion=off] 总开关", proc.stdout)

    def test_detects_duplicate_reveal_rule(self):
        """两处 .reveal 定义会靠源顺序决定谁生效，改了 A 坏了 B。"""
        def mutate(tmp):
            p = os.path.join(tmp, "assets", "style.css")
            s = open(p, encoding="utf-8").read()
            open(p, "w", encoding="utf-8").write(
                s + "\n.reveal{opacity:0;transition-delay:99ms}\n")

        proc = self.run_case(mutate)
        self.assertEqual(proc.returncode, 1)
        self.assertIn(".reveal 的基础规则应当只有一处", proc.stdout)

    def test_detects_transition_shorthand_on_card(self):
        """这条是真实踩过的坑：.card 用 transition 简写会重置
        transition-delay，把 .reveal 的错落延迟冲成 0。"""
        def mutate(tmp):
            p = os.path.join(tmp, "assets", "style.css")
            s = open(p, encoding="utf-8").read()
            open(p, "w", encoding="utf-8").write(
                s.replace(
                    ".card,.post-card{transition-property:border-color;"
                    "transition-duration:var(--dur-fast)}",
                    ".card,.post-card{transition:border-color 140ms ease}",
                ))

        proc = self.run_case(mutate)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("transition 简写", proc.stdout)

    def test_detects_missing_reduced_motion_path(self):
        def mutate(tmp):
            p = os.path.join(tmp, "assets", "style.css")
            s = open(p, encoding="utf-8").read()
            open(p, "w", encoding="utf-8").write(
                s.replace("@media(prefers-reduced-motion:reduce){.reveal{transition:none}}", ""))

        proc = self.run_case(mutate)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("系统级「减少动画」", proc.stdout)

    def test_detects_missing_contrast_path(self):
        def mutate(tmp):
            p = os.path.join(tmp, "assets", "style.css")
            s = open(p, encoding="utf-8").read()
            open(p, "w", encoding="utf-8").write(
                s.replace("@media(prefers-contrast:more){.reveal{opacity:1}}", ""))

        proc = self.run_case(mutate)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("增强对比度", proc.stdout)

    def test_detects_missing_scripting_none_path(self):
        def mutate(tmp):
            p = os.path.join(tmp, "assets", "style.css")
            s = open(p, encoding="utf-8").read()
            open(p, "w", encoding="utf-8").write(
                s.replace("@media(scripting:none){.reveal{opacity:1}}", ""))

        proc = self.run_case(mutate)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("脚本不可用", proc.stdout)

    def test_detects_missing_motion_switch_in_page(self):
        """页面缺动效开关时，用户根本无从关闭动效。"""
        page = CLEAN_PAGE.replace(MOTION_OFF, "").replace(
            '<button type="button" data-motion-option="on" aria-pressed="false">开启</button>', "",
        )
        proc = self.run_case(lambda tmp: None, page=page)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("动效开关应有 on/off 各 1 个", proc.stdout)

    def test_detects_half_present_motion_switch(self):
        """只加了一半开关（忘了 off）是最容易犯的错。"""
        page = CLEAN_PAGE.replace(MOTION_OFF, "")
        proc = self.run_case(lambda tmp: None, page=page)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("实际 on=1 off=0", proc.stdout)


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
