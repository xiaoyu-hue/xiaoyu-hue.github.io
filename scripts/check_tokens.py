#!/usr/bin/env python3
"""
check_tokens.py —— 设计契约校验（阶段2 · 设计契约层的执行者）

契约规则：
  R1 全局设计变量只能定义在令牌语境（:root / html[data-theme] / :root[data-motion] /
     包着它们的 @media）。@keyframes/@property 内的属性动画与注册、.reveal 的 --i
     序号等组件实现细节豁免。
  R2 颜色类令牌在暗色 :root 与浅色主题必须成对（结构类令牌——字号/间距/时长/缓动/位移——
     豁免，它们不随主题变化是正常的）。
  R3 每个 var(--x) 引用都必须在某处有定义（防拼写错误静默失效）。
  R4 组件规则中的裸十六进制色值数量不得超过基线（token_allowlist.json），
     防止改版时绕过令牌体系直接写死颜色。

用法：
  python3 scripts/check_tokens.py            # 全量检查，退出码非0 = 违约
  python3 scripts/check_tokens.py --baseline # 重建裸色值基线（改版有意新增颜色后）
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "assets" / "style.css"
ALLOWLIST = Path(__file__).parent / "token_allowlist.json"

# 组件作用域豁免：这些变量的定义属于实现细节，不算全局令牌违约
COMPONENT_SCOPED = re.compile(r"^--i$")
# 颜色类令牌前缀：这些必须在浅色主题有覆盖
COLOR_PREFIXES = (
    "--abyss", "--deep", "--ocean", "--accent", "--glass", "--hairline",
    "--text", "--body-text",
)


def strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


def top_level_blocks(css: str):
    """深度扫描，返回 [(head原文, body, 起始行)]。head = 上一个块结束到 '{' 之间。"""
    depth = 0
    open_pos = None
    prev_close = -1
    out = []
    for i, ch in enumerate(css):
        if ch == "{":
            depth += 1
            if depth == 1:
                open_pos = i
        elif ch == "}":
            depth -= 1
            if depth == 0 and open_pos is not None:
                head = css[prev_close + 1:open_pos]
                out.append((head, css[open_pos + 1:i], css[:i].count("\n") + 1))
                prev_close = i
                open_pos = None
    return out


def selector_of(head: str) -> str:
    """选择器 = 最后一段注释结束后的残余文本（防横幅注释干扰）。"""
    tail = head.split("*/")[-1].strip()
    return " ".join(tail.split())


def is_token_context(sel: str) -> bool:
    return (sel == ":root" or sel.startswith(":root[")
            or sel.startswith("html[data-theme"))


def main() -> None:
    css = CSS.read_text(encoding="utf-8")
    errors, warnings = [], []

    token_defs = {"base": set(), "light": set()}  # R1/R2：令牌语境中的定义
    all_defs = set()                              # R3：全文件所有自定义属性定义
    refs = set(re.findall(r"var\(\s*(--[\w-]+)", css))
    hexes = []                                    # R4：组件规则中的裸色值

    for head_raw, body, line in top_level_blocks(css):
        sel = selector_of(head_raw)
        clean_body = strip_comments(body)

        # R3 数据源：所有上下文的属性定义都算“有定义”
        for m in re.finditer(r"(--[\w-]+)\s*:", clean_body):
            all_defs.add(m.group(1))

        if sel.startswith("@keyframes") or sel.startswith("@property"):
            continue  # 属性动画/注册是合法的自定义属性语境

        if sel.startswith("@media") or sel.startswith("@supports"):
            # 条件块：逐个检查内层块的选择器（@media 里包 :root 是合法令牌语境）
            for sel_in, body_in in re.findall(r"([^{}]+)\{([^{}]*)\}", clean_body):
                sel_in = " ".join(sel_in.split())
                if is_token_context(sel_in):
                    light = "light" in sel or "light" in sel_in
                    for m in re.finditer(r"(--[\w-]+)\s*:", body_in):
                        token_defs["light" if light else "base"].add(m.group(1))
                else:
                    for m in re.finditer(r"(--[\w-]+)\s*:[^;]*;", body_in):
                        name = m.group(1)
                        if COMPONENT_SCOPED.match(name):
                            continue
                        errors.append(
                            f"R1 违约 L{line}: [{sel[:40]} {sel_in[:40]}] 定义了 {name}")
                    hexes.extend(re.findall(r"#[0-9a-fA-F]{3,8}\b", body_in))
        elif is_token_context(sel):
            light = "light" in sel
            for m in re.finditer(r"(--[\w-]+)\s*:", clean_body):
                token_defs["light" if light else "base"].add(m.group(1))
        else:
            # 组件规则：R1 检查 + R4 裸色值收集
            for m in re.finditer(r"(--[\w-]+)\s*:[^;]*;", clean_body):
                name = m.group(1)
                if COMPONENT_SCOPED.match(name):
                    continue
                errors.append(f"R1 违约 L{line}: 组件规则 [{sel[:60]}] 定义了 {name}")
            hexes.extend(re.findall(r"#[0-9a-fA-F]{3,8}\b", clean_body))

    # R2 颜色令牌浅色成对
    for t in sorted(token_defs["base"]):
        if t.startswith(COLOR_PREFIXES) and t not in token_defs["light"]:
            errors.append(f"R2 违约: 颜色令牌 {t} 浅色主题缺覆盖")

    # R3 引用必须有定义
    for r in sorted(refs - all_defs):
        errors.append(f"R3 违约: var({r}) 被引用但从未定义")

    # R4 裸色值基线
    if "--baseline" in sys.argv:
        ALLOWLIST.write_text(json.dumps(
            {"count": len(hexes), "note": "基线，仅可增不可减地审视"}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"基线已更新：{len(hexes)} 个裸色值")
        return
    if ALLOWLIST.exists():
        baseline = json.loads(ALLOWLIST.read_text(encoding="utf-8"))["count"]
        if len(hexes) > baseline:
            errors.append(f"R4 违约: 组件裸色值 {len(hexes)} > 基线 {baseline}，"
                          "新增颜色应定义成令牌；确属例外请更新基线")
    else:
        ALLOWLIST.write_text(json.dumps(
            {"count": len(hexes), "note": "初次基线"}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        warnings.append(f"R4: 首次运行，生成基线 {len(hexes)} 个裸色值")

    # 报告
    print(f"暗色基线令牌: {len(token_defs['base'])} | "
          f"浅色覆盖: {len(token_defs['light'])} | "
          f"var引用: {len(refs)} | 组件裸色值: {len(hexes)}")
    for w in warnings:
        print(f"  ⚠ {w}")
    if errors:
        for e in errors:
            print(f"  ✗ {e}")
        print(f"\n设计契约违约 {len(errors)} 项")
        sys.exit(1)
    print("✓ 设计契约全部通过")


if __name__ == "__main__":
    main()
