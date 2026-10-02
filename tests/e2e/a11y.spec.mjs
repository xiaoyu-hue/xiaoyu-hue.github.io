// 真浏览器可访问性基线：静态审查查不出来的那部分。
//
// 为什么需要它：CSS 里两个十六进制常量配在一起，对比度够不够，
// 不跑浏览器、不做色彩空间计算，读代码永远看不出来。本文件第一次跑
// 就在页脚署名上抓到 --text-faint #547689 配 --abyss #eaf4fa 只有
// 4.347:1（WCAG AA 要求 4.5:1）—— 那是个已经上线了的问题。
//
// 为什么严格 CSP 没拦住 axe：页面 CSP 是 script-src 'self'，没有
// unsafe-inline。axe 靠浏览器调试协议在页面上下文里执行，不走 <script>
// 标签，所以不受这条约束。这一条是实测确认的，不是推测。
//
// 运行：npx playwright test tests/e2e/a11y.spec.mjs

import { test, expect } from '@playwright/test';
import { AxeBuilder } from '@axe-core/playwright';

// 本文件仅 chromium 项目运行；firefox 项目跳过（cross-browser.spec 才覆盖 Firefox）
test.skip(({ browserName }) => browserName === 'firefox', '仅 chromium 项目运行');
import { readdirSync, statSync, readFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

// 只跑这四个 tag：规则稳定、误报少，够覆盖 WCAG 2.1 A/AA。
// 想扩到 wcag22aa 前先本地确认规则集，别直接加。
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

const ROOT = fileURLToPath(new URL('../..', import.meta.url));
// 只扫「用户真正能访问的成品页」，不扫构建源。
// src/ 是 build.py 的输入（布局模板 base.html + 各页 *.body.html 片段），
// 这些片段在线上永远不会单独出现 —— 它们会被套进带 --surface 卡片底色的
// 布局、并走完整的 data-theme 颜色令牌后才呈现。单独打开时样式残缺
// （没有 <html data-theme> 钩子、没有外层卡片底色），弱化文字直接落在更浅的
// 页面底色上，会被 axe 误判为 WCAG 对比度不达标。真实站点里整页能通过，
// 所以这是「把构建源当成品页扫」产生的假阳性，不是线上缺陷。
// 排除 src/ 后，所有对外服务的页面（根目录 + /blog/）依旧全覆盖。
const SKIP_DIRS = new Set(['node_modules', '.git', 'src', 'test-results', 'playwright-report', '.lighthouseci']);

// 页面清单不手写死：新增页面自动纳入扫描。
// site.spec.mjs 里那份是手写的数组，这里刻意不抄 —— 手写清单的问题是
// 加了新页面会忘了加测试，而忘了的那一个恰恰是最该测的那个。
function htmlFiles(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      if (!SKIP_DIRS.has(name)) out.push(...htmlFiles(full));
    } else if (name.endsWith('.html')) {
      out.push('/' + relative(ROOT, full).split(sep).join('/'));
    }
  }
  return out.sort();
}

const PAGES = htmlFiles(ROOT);

// 违规转成可读文本；没有违规时返回空数组，走快路径不做字符串处理。
function violationsToText(violations) {
  return violations.map((v) => {
    const nodes = v.nodes
      .slice(0, 5)
      .map((n) => {
        const why = (n.failureSummary || '')
          .split('\n')
          .filter(Boolean)
          .slice(1)
          .join(' ')
          .trim();
        return `      ${n.target.join(' ')}${why ? `\n      ↳ ${why}` : ''}`;
      })
      .join('\n');
    return `[${v.impact}] ${v.id} — ${v.help}（${v.nodes.length} 处）\n${nodes}`;
  });
}

// 扫描前必须先把动效关掉，否则结果不确定。
//
// .reveal 入场是 opacity 0 → 1 的渐变，扫到中间态会算出假的对比度：
// 实测同一个元素在终态是 6.4:1，在 alpha≈0.57 的中间态只有 2.5:1。
// 于是同一份代码这次绿、下次红 —— 这种 flaky 最要命，因为它会让人
// 习惯性重跑而不是去查问题。
//
// 用项目自己的总开关（data-motion="off"）把 .reveal 直接压到终态，
// 扫描才有确定性。顺便说一句：中间态对比度低不是缺陷，那是淡入效果
// 本来的样子，是瞬态的；真正的问题只是「测试不该在动画中途读数」。
//
// 关掉之后还要等两帧再扫。除了 .reveal 的淡入，.ocean-bg 还挂着一个
// 22s 循环、改 background-position 的动画，而文字就叠在这层背景上 ——
// 它跑到哪一段，局部背景色就不一样。设置属性会让动画停，但「停」这个
// 动作不会立刻反映到计算样式上，不等就扫有概率读到动画中途的背景色。
async function scan(page) {
  await page.evaluate(
    () =>
      new Promise((resolve) => {
        document.documentElement.dataset.motion = 'off';
        // 第一帧让样式生效，第二帧确认重绘完成
        requestAnimationFrame(() => requestAnimationFrame(resolve));
      }),
  );
  // 字体没就位时行高和换行都还没定，元素位置也就没定
  await page.evaluate(() => document.fonts.ready);
  return new AxeBuilder({ page }).withTags(TAGS).analyze();
}

test.describe('页面清单本身', () => {
  test('没扫空（防止 glob 失效后 0 个页面静默通过）', () => {
    // 全站页面目前是 11 个。新增页面会自动进来，所以只卡下限，
    // 但必须包含首页和离线页 —— 这两个是入口和兜底，不能漏。
    expect(PAGES.length).toBeGreaterThanOrEqual(10);
    expect(PAGES).toContain('/index.html');
    expect(PAGES).toContain('/offline.html');
  });
});

test.describe('可访问性基线', () => {
  // 浅色和深色是两套独立的颜色令牌，必须各扫一遍。
  // 上一轮就是浅色挂了、深色干净 —— 只扫一种会漏。
  //
  // ⚠️ 这里曾经失过效：循环写着 ['light','dark']，却忘了调 emulateMedia 真正切换，
  // 结果两个用例跑的都是同一个默认主题（深色对比度从未被扫到），
  // 而注释还写着"必须各扫一遍" —— 典型的「注释正确、实现失效」假护栏。
  // 所以下面除了切换主题，还补了一条自证断言：主题真的变了才继续，
  // 一旦将来主题机制改动导致切换失效，这条会立刻报错，而不是静默退化成假护栏。
  // 有些页面不参与主题切换（例如 offline.html 是极简离线页，只引 offline.js，
  // 固定深色不做主题）。对这类页面只扫一次，避免"浅色"用例去断言一个
  // 永远不会变浅的页面。判定依据是页面本身有没有引入 theme-boot.js，
  // 而不是手写页面名 —— 新增页面时结论自动正确。
  function hasThemeBoot(path) {
    const rel = path.replace(/^\//, '');
    try {
      return readFileSync(join(ROOT, rel), 'utf-8').includes('theme-boot.js');
    } catch {
      return false;
    }
  }

  const EXPECTED_BG = { light: 'rgb(234, 244, 250)', dark: 'rgb(4, 17, 29)' };
  for (const path of PAGES) {
    // 不参与主题切换的页面：只跑默认配色一次（标为"默认"以免误导）
    const schemes = hasThemeBoot(path) ? ['light', 'dark'] : ['default'];
    for (const scheme of schemes) {
      const label = scheme === 'light' ? '浅色' : scheme === 'dark' ? '深色' : '默认';
      test(`${path}（${label}）无 WCAG AA 违规`, async ({ page }) => {
        // ⚠️ 必须在 goto 之前切换配色：theme-boot.js 只在页面加载时读一次
        // matchMedia，它不监听媒体查询变化。若在 goto 之后切换，主题不会跟着变，
        // 断言就会随执行时机时红时绿（实测过：全量跑 7 failed / 6 failed 波动）。
        if (scheme !== 'default') {
          await page.emulateMedia({ colorScheme: scheme });
        }
        await page.goto(path, { waitUntil: 'load' });

        // 自证：主题确实切过去了（否则说明切换机制失效，立刻报错而非静默通过）
        if (scheme !== 'default') {
          const bg = await page.evaluate(
            () => getComputedStyle(document.body).backgroundColor
          );
          expect(bg, `主题未切换到${label}，本条会成为假护栏`).toBe(EXPECTED_BG[scheme]);
        }

        const { violations, incomplete } = await scan(page);

        // incomplete 只记录不阻断：大多是渐变 / 半透明背景上的对比度，
        // axe 算不出确定值。把它也卡进 CI 会被一堆永远算不准的项堵死，
        // 结果就是整条测试被人关掉。这里只留作本地排查的线索。
        if (incomplete.length) {
          test.info().annotations.push({
            type: 'axe-incomplete',
            description: `${incomplete.length} 项需人工确认`,
          });
        }

        expect(violationsToText(violations)).toEqual([]);
      });
    }
  }

  test('设置面板展开后，面板内部也无违规', async ({ page }) => {
    await page.goto('/', { waitUntil: 'load' });

    await page.locator('.prefs-toggle').click();
    // 面板关闭时是 visibility:hidden，所以这个断言能确认它真的展开了，
    // 而不是点了没反应、然后扫了个藏起来的面板假装通过。
    await expect(page.locator('.prefs-panel')).toBeVisible();

    const { violations } = await scan(page);
    expect(violationsToText(violations)).toEqual([]);
  });
});
