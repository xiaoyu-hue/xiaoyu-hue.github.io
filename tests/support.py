"""测试用的极简 HTML 解析工具。

只用标准库,不引入任何依赖 —— 站点定位是「零构建、零依赖」,测试也不能破例。
"""

import os
import struct
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGES = ["index.html", "blog/index.html"] + [f"blog/post-{i}.html" for i in range(1, 11)]

SIGNATURE = "一半烟火以谋生，一半诗意以谋爱"

# HTML 的空元素（不需要闭合标签）
VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class Node:
    """一个 DOM 节点。"""

    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = attrs
        self.classes = (attrs.get("class") or "").split()
        self.children = []
        self.texts = []

    @property
    def text(self):
        parts = list(self.texts)
        for child in self.children:
            parts.append(child.text)
        return "".join(parts)

    def walk(self):
        for child in self.children:
            yield child
            yield from child.walk()

    def find(self, tag=None, cls=None):
        for n in self.walk():
            if tag and n.tag != tag:
                continue
            if cls and cls not in n.classes:
                continue
            return n
        return None

    def find_all(self, tag=None, cls=None):
        return [
            n for n in self.walk()
            if (not tag or n.tag == tag) and (not cls or cls in n.classes)
        ]


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {})
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, dict(attrs)))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].texts.append(data)


def parse_string(html):
    p = _Parser()
    p.feed(html)
    return p.root


def parse(rel_path):
    return parse_string(read(rel_path))


def read(rel_path):
    with open(os.path.join(ROOT, rel_path), encoding="utf-8") as fh:
        return fh.read()


def read_bytes(rel_path):
    """读二进制文件（校验 PNG 图标时需要）。"""
    with open(os.path.join(ROOT, rel_path), "rb") as fh:
        return fh.read()


def png_size(data):
    """从 PNG 文件头读出真实宽高，不依赖任何图像库。

    PNG 的 IHDR 块固定在偏移 16..24：8 字节魔数 + 4 字节块长 + 4 字节类型
    = 16，其后 4 字节宽、4 字节高，均为大端无符号整数。

    为什么要读真实尺寸而不是相信 manifest 里写的 sizes：
    图标尺寸写错时，浏览器会把图标拉伸变形，而 manifest 本身仍然"合法"，
    只有比对文件头才抓得到。
    """
    if len(data) < 24:
        raise ValueError("文件太小，不是合法 PNG")
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是 PNG（魔数不符）")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def exists(rel_path):
    return os.path.exists(os.path.join(ROOT, rel_path))


def headers_csp():
    """从 _headers 里取出 Cloudflare Pages 用的 CSP 字符串。"""
    for line in read("_headers").splitlines():
        if line.strip().lower().startswith("content-security-policy:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError("_headers 里找不到 Content-Security-Policy")
