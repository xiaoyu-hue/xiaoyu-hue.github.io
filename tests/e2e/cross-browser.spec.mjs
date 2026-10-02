// 跨浏览器护栏：重点验证「五层降级」与「内容可见性」在 Firefox 真生效。
//
// 为什么单独给 Firefox 一个项目：
//   本项目 v7 的流光 / 视差 / 进度条依赖 @property 与 scroll() 时间线，
//   这些是 Chromium 系专属能力，Firefox 至今不支持。所以这些效果在 Firefox
//   必须「优雅降级」而非「破版」——本文件就是守住这条底线。
//
// 关键风险点（均为真实可踩的坑）：
//   1) .reveal 滚动入场被 @supports(animation-timeline:view()) 包裹，
//      Firefox 不支持 → 回退到 main.js 的 IntersectionObserver 兜底。
//      若 main.js 在 Firefox 抛错，.reveal 会永远停在 opacity:0（白屏）。
//      所以必须断言 .reveal 最终可见（computed opacity≈1），否则即「白屏」回归。
//   2) prefers-reduced-motion:reduce 的降级在 Firefox 也要生效（动画归零）。
//   3) 不能出现横向溢出（Firefox 排版差异可能撑破布局）。
//   4) 不能有未捕获的 JS 异常（main.js / sw.js 在 Firefox 跑通）。
//
// 本文件只跑在 firefox 项目下：
//   - playwright.config.mjs 用 project.include 限定
//   - 下面 test.skip 再兜底，避免污染 chromium 项目的既有视觉基线

import { test, expect } from '@playwright/test';

// 仅 Firefox 项目运行；chromium 项目直接跳过，保持视觉基线干净
test.skip(({ browserName }) => browserName !== 'firefox', '本文件仅在 firefox 项目下运行');

const PAGES = ['/index.html', '/blog/index.html', '/blog/post-1.html', '/blog/post-4.html'];

test.describe('Firefox 跨浏览器降级护栏', () => {
  // 监听未捕获异常：任何 main.js 在 Firefox 抛错都会让这里失败
  let pageErrors = [];
  test.beforeEach(async ({ page }) => {
    pageErrors = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));
  });

  for (const path of PAGES) {
    test(`${path}：内容可见 + 无 JS 异常 + 无横向溢出`, async ({ page }) => {
      await page.goto(path, { waitUntil: 'load' });

      // 滚到底再回顶，触发 IntersectionObserver 兜底，确保所有 .reveal 显现
      await page.evaluate(async () => {
        window.scrollTo(0, document.body.scrollHeight);
        await new Promise((r) => setTimeout(r, 60));
        window.scrollTo(0, 0);
      });
      await page.waitForTimeout(500);

      // 1) 正文已渲染（不依赖具体标签：blog/index 等页用 h2 作主标题，没有 h1）
      const bodyLen = await page.evaluate(
        () => document.body.innerText.trim().length,
      );
      expect(bodyLen, '页面正文为空（内容未渲染 / 白屏）').toBeGreaterThan(100);

      // 主标题存在且有文字（优先 h1，退而 h2）
      const heading = page.locator('h1, h2').first();
      await expect(heading).toBeVisible();
      expect((await heading.innerText()).trim().length).toBeGreaterThan(0);

      // 2) .reveal 在 Firefox 经 JS 兜底（IntersectionObserver + 1500ms 硬超时）后必须可见。
      //    main.js 有「REVEAL_TIMEOUT=1500ms 强制 .in」兜底，所以最多等 1.5s 必显现；
      //    这里等最长 5s 仍不显现，才是真 bug（白屏风险）。
      //    排除 offsetParent===null 的元素：它们在 display:none 容器里（如设置面板），本就不该显示。
      await page.waitForFunction(
        () => {
          const els = Array.from(document.querySelectorAll('.reveal'));
          if (!els.length) return true;
          return els.every(
            (el) =>
              el.offsetParent === null ||
              parseFloat(getComputedStyle(el).opacity) > 0.1,
          );
        },
        { timeout: 5000 },
      );
      // 二次确认：确实没有「真实渲染却不可见」的 .reveal
      const invisible = await page.evaluate(() => {
        const els = Array.from(document.querySelectorAll('.reveal'));
        return els.filter(
          (el) => el.offsetParent !== null && parseFloat(getComputedStyle(el).opacity) < 0.1,
        ).length;
      });
      expect(invisible, `Firefox 下有 ${invisible} 个 .reveal 不可见（降级兜底失效，可能白屏）`).toBe(0);

      // 3) 无横向溢出（Firefox 排版差异撑破布局会这里暴露）
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      );
      expect(overflow, '存在横向溢出（Firefox 排版差异撑破布局）').toBeLessThanOrEqual(1);

      // 4) 无未捕获 JS 异常（main.js 在 Firefox 跑通）
      expect(pageErrors, `Firefox 下有未捕获 JS 异常: ${pageErrors.join(' | ')}`).toHaveLength(0);
    });
  }

  // 5) prefers-reduced-motion 降级在 Firefox 也生效：动画归零
  test('prefers-reduced-motion:reduce 在 Firefox 生效（动效归零）', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/index.html', { waitUntil: 'load' });

    const checks = ['.hero-card', '.ocean-bg'];
    for (const sel of checks) {
      const el = page.locator(sel).first();
      if ((await el.count()) > 0) {
        const anim = await el.evaluate((node) => getComputedStyle(node).animationName);
        expect(anim, `reduced-motion 下 ${sel} 动画未归零`).toBe('none');
      }
    }
  });
});
