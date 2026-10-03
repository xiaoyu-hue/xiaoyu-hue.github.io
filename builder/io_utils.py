"""builder.io_utils —— 文件读写与报错小工具（机械搬运，未改逻辑）。"""
import os
import re
import sys

from .paths import EXIT_ERR, ROOT

def html_targets():
    """站点上需要被这套流程管理的成品文件（相对仓库根）。

    由磁盘扫描得出，不再写死「1 到 N」—— 那样每加一篇文章都得回来改一处，
    漏改了还不会报错，只会默默少构建一个页面。
    """
    found = ["index.html", "blog/index.html"]
    blog_dir = os.path.join(ROOT, "blog")
    nums = []
    if os.path.isdir(blog_dir):
        for name in os.listdir(blog_dir):
            m = re.match(r"^post-(\d+)\.html$", name)
            if m:
                nums.append(int(m.group(1)))
    return found + ["blog/post-%d.html" % n for n in sorted(nums)]

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def fail(msg):
    print("[错误] " + msg, file=sys.stderr)
    sys.exit(EXIT_ERR)
