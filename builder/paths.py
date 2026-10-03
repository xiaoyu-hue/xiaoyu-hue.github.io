"""builder.paths —— 路径常量与命名约定（由 build.py 机械拆分而来）。

注意 ROOT 的算法：本文件在 builder/ 子目录里，要往上跳两级才是仓库根。
（原 build.py 在仓库根，只需跳一级。拆分时这是唯一被"改写"的一行，
其余内容逐字搬运。）
"""
import os
import re

# 原文（build.py 版）：ROOT = os.path.dirname(os.path.abspath(__file__))
# 拆分后本文件位于 builder/ 子目录，需要向上两级：
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
LAYOUTS = os.path.join(SRC, "layouts")
PAGES_DIR = os.path.join(SRC, "pages")
DATA = os.path.join(SRC, "data")

SITE_JSON = os.path.join(DATA, "site.json")
PAGES_JSON = os.path.join(DATA, "pages.json")
LAYOUT_FILE = os.path.join(LAYOUTS, "base.html")
# 离线页不用 base.html（它没有设置面板、只有 3 个导航项），单独一份模板
OFFLINE_TEMPLATE = os.path.join(SRC, "templates", "offline.html")
# Service Worker：手写逻辑 + 构建期接管的预缓存清单（仓库根，浏览器只认这个位置）
SW_FILE = os.path.join(ROOT, "sw.js")

# 文章正文的命名约定：src/pages/blog-post-<编号>.body.html
# 「目录即清单」—— 新增一篇文章只需放一个文件进来，不必再登记编号。
POST_BODY_RE = re.compile(r"^blog-post-(\d+)\.body\.html$")
POST_URL_RE = re.compile(r"^blog/post-(\d+)\.html$")

EXIT_OK, EXIT_DIFF, EXIT_ERR = 0, 1, 2
