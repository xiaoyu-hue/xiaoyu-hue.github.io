# 设计契约（DESIGN_CONTRACT）

> 本文档是 `assets/style.css` 设计体系的**使用说明书 + 变更规则**。
> 任何改版（无论人还是 AI Agent）动手前必须先读完本文。
> 强制执行者：`scripts/check_tokens.py`（CI 每次推送自动运行，违约即红灯）。

---

## 一、这套设计的核心思想

整站的视觉由 **61 个全局令牌**（CSS 自定义变量）驱动。它们全部定义在
`assets/style.css` 的令牌语境块里：

| 语境块 | 作用 |
|---|---|
| `:root{…}`（文件前部） | 暗色基线：颜色 / 玻璃质感 / 发丝线 / 文字 / 间距 / 字号 |
| `:root{…}`（动效区） | 动效令牌：时长 / 缓动 / 位移 / 氛围节奏 |
| `html[data-theme="light"]{…}` | 浅色主题覆盖 |
| `@media(prefers-color-scheme:light){ html[data-theme-pref="system"]{…} }` | 跟随系统的浅色覆盖 |
| `@media(prefers-reduced-motion:reduce){ :root{…} }` | 无障碍降级（动效归零） |
| `:root[data-motion="off"]{…}` | 用户手动关闭动效的总开关 |

**⚠️ 这些块的位置是刻意安排的，不要移动。**
CSS 同权重时靠源码顺序取胜——主题块 / 降级块必须排在它们要覆盖的规则之后。
历史上已经踩过这个坑（见 style.css 内"浅色主题块当初踩过同一个坑"的注释）。

## 二、四条契约规则（CI 强制）

### R1 · 令牌的唯一产地
全局设计变量只能写在上面列出的令牌语境里。
组件规则**禁止**定义全局令牌。
豁免：`@keyframes`/`@property` 内的属性动画（如 `--aurora-angle`）、
`.reveal` 的 `--i` 交错序号等组件内部实现细节。

### R2 · 颜色令牌必须双主题成对
暗色 `:root` 里每个**颜色类**令牌（前缀 `--abyss/--deep/--ocean/--accent/
--glass/--hairline/--text/--body-text`）都必须在浅色主题有对应覆盖。
结构类令牌（字号 `--fs-*`、间距 `--space-*`、时长 `--dur-*`、缓动 `--ease-*`、
位移 `--shift-*`）不随主题变，豁免。

### R3 · 引用必须可解析
任何 `var(--x)` 引用都必须有定义。拼错名字不会报错、只会静默失效——
这是最阴险的前端 bug 之一，本规则专治它。

### R4 · 裸色值有配额
组件规则里直接写死的十六进制色值数量不得超过基线
（`scripts/token_allowlist.json`，当前 13 个）。
新颜色 = 新令牌（并同步浅色覆盖），而不是又写死一个色值。
确属一次性例外：改完令牌后运行
`python3 scripts/check_tokens.py --baseline` 更新基线，并在 PR 里说明理由。

## 三、"破坏性视觉更新"的标准流程

本仓库的目标：**换皮肤不伤筋骨**。改版按下述顺序走：

1. **只动令牌**：新配色 / 新玻璃质感 / 新节奏 → 修改令牌语境块。
   颜色令牌改一份，同步改浅色（R2 会盯着你）。
2. **跑契约校验**：`python3 scripts/check_tokens.py` → 必须全绿。
3. **跑构建**：`python3 build.py` → 产物必须与提交文件一致。
4. **跑全部测试**：`python3 -m unittest discover -s tests -t .` + `npx playwright test`。
5. **视觉快照更新**：改动是**有意的**视觉变化时，
   `npx playwright test --update-snapshots` 刷新基线，diff 逐张确认
   （只该有你改的那些差异，多一张都是事故）。
6. **微调组件层**：仅当令牌层无法表达时才动组件规则，
   且不得违反 R1/R4（需要新形状 = 新令牌，不是新硬编码）。

## 四、令牌语义速查（暗色基线）

- **海洋深度轴**：`--abyss`（海沟·页面底）→ `--deep`（中层·导航）→ `--ocean`（近海·卡片内）。
  同一条色阶，改一个必须检查另外两个的相对明度。
- **强调色刻度**：`--accent-whisper → faint → soft → line → line-strong → glow → solid`，
  从弱到强，按语义取用，禁止"差不多就随手一个透明度"。
- **液态玻璃**：`--glass-bg / bg-strong / border / shadow / sheen`。
- **发丝线**：`--hairline / strong / faint / table`。
- **动效三档**：`--dur-fast(140ms) / base(240ms) / slow(1600ms)`。
  `--dur-slow` 当前无消费者但**不要删**（tests/test_pages.py 要求三档齐备）。
- 逐条语义见 style.css 内注释（写得很全，改前必读）。

## 五、本契约的边界（诚实声明）

- `--lh-display/heading/title`（标题行高）等少量令牌定义在文件中部，
  由 R3 兜底防拼写；R1 允许它们存在（它们在 `:root` 语境里，合法）。
- 裸色值基线里的 13 个存量值大多在 `@property` 渐变注册和噪点纹理里，
  属于历史存量，新代码不得模仿。
- 本契约管 CSS。JS 侧的主题切换（`theme-boot.js`）通过 `data-theme` 属性
  与本体系对接，改主题机制时两边要一起评估。
