# CSP 会不会拦掉 JSON-LD 结构化数据

> 这是本站的一条实测结论。实验脚本就在仓库里，谁都能重跑：
>
> ```
> python3 scripts/verify_csp_jsonld.py
> ```

## 问题

本站有两件事看起来直接冲突：

| 要求 | 做法 |
|---|---|
| 给搜索引擎、内容聚合器、AI 摘要工具看清楚结构 | 必须把 JSON-LD 内联写进 HTML |
| 严格 CSP：`script-src 'self'`，无 `unsafe-inline`、无 nonce、无 hash | 禁止所有内联 `<script>` |

如果 JSON-LD 被拦掉，后果很难发现：**页面外观完全正常**，只是结构化数据静默失效——看不到博主名片、看不到发布时间、AI 总结也少了一层依据。

## 为什么不靠查文档解决

查了一圈，能找到的说法既不全，也不一致：

- MDN 明确说内联 `<script>` 默认被拦，要用 nonce 或 hash 放行
- 一些技术博客建议给 JSON-LD 加 nonce，暗示它确实被拦
- 但完全找不到是谁真的测过 `type="application/ld+json"` 这一种

这些说法对错都有可能对——因为**它们讨论的可能不是同一个东西**。内联脚本和被内联的结构化数据块，在浏览器内部走的根本不是同一条路。继续查文档只会得到更多二手转述，所以改成实测。

## 实验设计

起一个本地服务器，真实下发本站的 CSP，用真浏览器加载页面，然后看 JSON-LD 能不能被读到。

页面故意放三样东西：

| 行号 | 内容 | 作用 |
|---|---|---|
| 行 2 | `<script type="application/ld+json">` 数据块 | **实验对象** |
| 行 5 | 内联 classic 脚本 | **对照组**：它必须被拦，否则说明 CSP 压根没生效，本轮结果作废 |
| 行 7 | 外链 `<script src=>` | 第二个对照：`'self'` 必须放行，否则装置同样有问题 |

**两条增加的严谨性：**

1. **必须有对照组。** 只看"没报错"是不够的——那也可能说明 CSP 根本没生效。对照组不通过就把整轮结论判为作废。
2. **违规事件按行号归属。** `securitypolicyviolation` 事件的内联脚本 `sample` 常常是空字符串，光看 sample 分不清是谁触发的，容易把对照组那条记到 JSON-LD 头上（这个坑我踩过一次）。所以按 `lineNumber` 精确定位。

## 结果

```
                  CSP 生效  JSON-LD 可读  JSON-LD 触发违规  对照组触发违规
chromium 145.0       是         是             0                1
firefox  146.0       是         是             0                1
webkit   26.0        是         是             0                1
```

三个引擎完全一致，且对照组全部按预期被拦——说明装置有效，不是"恰巧没报错"。

同时浏览器控制台确实报了：

```
Executing inline script violates the following Content Security Policy
directive 'script-src 'self''. Either the 'unsafe-inline' keyword, a hash
('sha256-kd/q1uy0ipYWpCSKvRalX5AqvPdYy7zZwRo1m0n00Jo='), or a nonce is required...
```

这条报错对应的是行 5 的对照组，不是 JSON-LD。**如果只看控制台有这条报错，很容易误判成 JSON-LD 被拦了。**

### 结论

**`script-src 'self'` 不会拦掉 `<script type="application/ld+json">`。**

原因是二者不在同一条执行路径上：HTML 规范的 *prepare the script* 算法规定，当 script 的 `type` 不匹配 JavaScript MIME 时，浏览器把它当成 **data block（数据块）**直接返回，不再往下走；而 CSP 的内联脚本检查挂在后面那一步。既然没走到，自然谈不上被拦。

## 这条结论的边界

不想把话说满，以下几点是**没实测过、我不知道**的：

- 测的是浏览器的行为，不是搜索引擎爬虫的行为。Google 用自己打包的 Chromium 渲染，理论上一致，但本站没有实测爬虫管线。
- 只测了上面三个引擎的当前版本。更老的浏览器（尤其老 Safari）没测。
- 如果将来给 CSP 加了 `require-trusted-types-for`、`sandbox` 之类指令，情况可能变化——没测。
- 这里只回答"会不会被拦"，不回答"搜索引擎买不买账"。后者取决于结构化数据本身写得对不对，与 CSP 无关。

## 因此在本站是怎么落地的

不因为这个结论就放宽检查。`scripts/check_integrity.py` 里对 `<script>` 的检查逻辑改为：

```python
if re.search(r"\ssrc=", attrs):
    continue                      # 外链脚本，'self' 下合法
tm = re.search(r'\stype\s*=\s*"([^"]+)"', attrs)
if tm and tm.group(1).strip() in DATA_BLOCK_TYPES:
    continue                      # 不可执行的 data block，CSP 不管
problems.append(...)
```

关键在用了**显式白名单**（只放行 `application/ld+json`、`application/json`），而不是"凡有 `type` 属性就放行"。这么写是为了避免将来某个新 type 被静默放过。

规则改完在 `tests/test_checker.py` 里补了 **10 条负向测试**（`test_data_block_*` 系列），确认没把真漏洞一起放过：

| 用例 | 判定 | 对应测试 |
|---|---|---|
| `<script>alert(1)</script>` | 拦截 | `test_data_block_classic_script_is_blocked` |
| `<script type="text/javascript">` | 拦截 | `test_data_block_text_javascript_is_blocked` |
| `<script type="module">` | 拦截 | `test_data_block_module_is_blocked` |
| 带 nonce 的 classic 脚本 | 拦截 | `test_data_block_nonce_classic_is_blocked` |
| `<script type="application/x-weird">` | 拦截 | `test_data_block_unknown_type_is_blocked` |
| 单引号 `type='application/ld+json'` | 拦截（偏严，宁可让人确认一次） | `test_data_block_single_quoted_type_is_blocked` |
| 大小写混淆 `TYPE="APPLICATION/LD+JSON"` | 拦截（同上） | `test_data_block_case_confused_type_is_blocked` |
| `<script type="application/ld+json">` | 放行 | `test_data_block_ld_json_is_allowed` |
| `<script type="application/json">` | 放行 | `test_data_block_json_is_allowed` |
| `<script src="./x.js">` | 放行 | `test_data_block_external_src_is_allowed` |

这 10 条测试已用**破坏性验证**确认是真护栏：把白名单改成"凡有 `type` 属性就放行"后，其中 3 条（未知 type、单引号、大小写混淆）立即变红，证明它们确实在守护边界，而不是恒真。

另外在 `tests/test_pages.py` 里加了一条**正向契约**：每个页面都必须有 JSON-LD、必须是合法 JSON、必须声明正确的 `@type`、里面的 URL 必须是绝对地址。理由是 JSON-LD 写错时肉眼完全看不出来，只有搜索引擎静默失效。

## 复现

```bash
pip install playwright && playwright install
python3 scripts/verify_csp_jsonld.py
```

需要 playwright，但这是**可选**的验证工具：不装也能完整构建和部署本站，只是没法亲自重跑这条结论。

脚本会自动跳过没装的引擎，并**明确报告未覆盖**——不会把没跑过的引擎算成"通过"。一个引擎都跑不起来时，脚本直接以非零码退出，不假装成功。
