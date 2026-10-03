"""builder.verify —— 构建结果比对与写入（机械搬运）。"""
import os

from .io_utils import read, write
from .paths import ROOT

def compare(outputs):
    """拿构建结果和磁盘上的现有文件逐字节比对，返回差异清单。"""
    diffs = []
    for rel_path, text in sorted(outputs.items()):
        disk = os.path.join(ROOT, rel_path)
        if not os.path.exists(disk):
            diffs.append((rel_path, "文件不存在（新建）", None))
            continue
        old = read(disk)
        if old != text:
            diffs.append((rel_path, describe_diff(old, text), None))
    return diffs


def describe_diff(old, new):
    """给人看的差异描述：第一个不同的位置 + 前后文。"""
    ol, nl = old.split("\n"), new.split("\n")
    for i in range(max(len(ol), len(nl))):
        o = ol[i] if i < len(ol) else "<缺少>"
        n = nl[i] if i < len(nl) else "<缺少>"
        if o != n:
            return "第 %d 行不同\n      现有: %s\n      构建: %s" % (
                i + 1, o.strip()[:100] or "(空行)", n.strip()[:100] or "(空行)")
    return "行数不同但内容看起来一样（可能是尾随换行差异）"


def do_write(outputs):
    for rel_path, text in sorted(outputs.items()):
        write(os.path.join(ROOT, rel_path), text)
    print("已写入 %d 个文件" % len(outputs))
