// 可视化回归：守住「像素级外观」不退化。
//
// 为什么需要它：v7 那次「降级规则被文件末尾的 @supports 块压过」的 bug，
// 逻辑测试（site.spec）和 a11y 扫描（a11y.spec）都绿，但真实渲染出来的
// 标题配色、焦散描边已经错了 —— 这类「看起来对、算出来也对、画出来不对」
// 的隐性视觉 bug，只有像素比对能抓。
//
// 冻结动效是前提（否则每帧都不同，快照永远 flaky）：
//   直接复用项目自己的总开关 data-motion="off"（style.css 第 883 行起），
//   它会把 .ocean-bg / .hero h1 流光 / .reveal 入场 / 进度条 / 波纹 全部
//   animation:none。设完等两帧 + 等 document.fonts.ready，再截。
//   这套顺序在 a11y.spec 里验证过，照搬。
//
// 双主题：浅色 / 深色两套独立颜色令牌，各截一遍（v7 之前闹过浅色挂、
// 深色干净，只截一种会漏）。
// 双视口：桌面 + 移动，守住响应式布局不退化。
//
// ⚠️ 跨环境一致性：本仓库用系统字体栈（无 web font），macOS / Windows 的
// 中文字形与 Linux 不同。因此**基线以 Linux 为准**（CI 与本地沙箱同环境），
// 本地 macOS / Windows 只跑流程、不要用 --update-snapshots，否则会把
// 跨平台字形差异当成「回归」误提交。
//
// ⚠️ CI 字体：基线在本沙箱用 Noto Sans/Serif CJK SC 生成，而 GitHub
// ubuntu-latest 运行器默认**不装中文字体**，中文会渲染成豆腐块导致比对
// 失败。因此 test.yml 的 e2e job 会先 `apt-get install fonts-noto-cjk`，
// 让 CI 用同款字体渲染；下面 0.03 容差再吸收 jammy/noble 字体版本的小差异。
//
// 运行：
//   生成 / 更新基线： npx playwright test tests/e2e/visual.spec.mjs --update-snapshots
//   比对（CI 默认）：  npx playwright test tests/e2e/visual.spec.mjs
//
// 收到「快照不符」时：先肉眼在 playwright-report 里看 diff，确认是
// 「预期内的设计改动」才更新基线，不要无脑 --update-snapshots。

import { test, expect } from '@playwright/test';

// 本文件仅 chromium 项目运行；像素基线只在 chromium 下生成，
// firefox 项目跳过（否则会误生成 firefox 快照导致比对红）。Firefox 的跨浏览器验证见 cross-browser.spec。
test.skip(({ browserName }) => browserName === 'firefox', '仅 chromium 项目运行（基线以 chromium 为准）');

// 关键页面：覆盖首页（hero / 流光 / 导航）、博客列表（卡片网格）、
// 典型文章页（含正文排版 / 代码块）。不扫全部 11 页，控制快照数量。
const PAGES = [
  '/index.html',
  '/blog/index.html',
  '/blog/post-1.html',
  '/blog/post-4.html',
];

const VIEWPORTS = {
  desktop: { width: 1280, height: 800 },
  mobile: { width: 390, height: 844 },
};

// 冻结动效 + 等字体 + 滚到顶，保证快照确定性（顺序来自 a11y.spec）。
async function freeze(page) {
  await page.evaluate(
    () =>
      new Promise((resolve) => {
        document.documentElement.dataset.motion = 'off';
        requestAnimationFrame(() => requestAnimationFrame(resolve));
      }),
  );
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => window.scrollTo(0, 0));
}

for (const path of PAGES) {
  for (const scheme of ['light', 'dark']) {
    for (const [vp, size] of Object.entries(VIEWPORTS)) {
      const label = scheme === 'light' ? '浅色' : '深色';
      test(`${path}（${label}·${vp}）外观`, async ({ page }) => {
        await page.setViewportSize(size);
        await page.emulateMedia({ colorScheme: scheme });
        await page.goto(path, { waitUntil: 'load' });
        await freeze(page);
        const name = `${path.replace(/[\/.]/g, '_')}_${scheme}_${vp}`;
        await expect(page).toHaveScreenshot(name + '.png', {
          maxDiffPixelRatio: 0.03,
        });
      });
    }
  }
}
