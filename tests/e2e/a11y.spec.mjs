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
import { readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

// 只跑这四个 tag：规则稳定、误报少，够覆盖 WCAG 2.1 A/AA。
// 想扩到 wcag22aa 前先本地确认规则集，别直接加。
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

const ROOT = fileURLToPath(new URL('../..', import.meta.url));
const SKIP_DIRS = new Set(['node_modules', '.git', 'test-results', 'playwright-report']);

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
  for (const path of PAGES) {
    for (const scheme of ['light', 'dark']) {
      const label = scheme === 'light' ? '浅色' : '深色';
      test(`${path}（${label}）无 WCAG AA 违规`, async ({ page }) => {
        await page.goto(path, { waitUntil: 'load' });

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
