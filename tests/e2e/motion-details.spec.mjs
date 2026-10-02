// v7 视觉细节断言：挑出「像素快照测不出原因」的那几项动效做精确校验。
//
// 为什么单独有这份文件：
//   visual.spec.mjs 的像素快照能发现「页面变了」，但报不出「哪里坏了」——
//   比如进度条从 3px 变成 0px、卡片光边动画名被改错、水波纹不再生成，
//   快照只会告诉你「有 35351 个像素不一样」，排障全程靠肉眼比对。
//   这份文件把这些细节变成带名字的断言，失败时直接指出坏的是哪一项。
//
// 覆盖范围（只保留 site.spec.mjs / cross-browser.spec.mjs 未覆盖的缺口）：
//   ③ 流光标题的 background-clip:text
//   ④ 滚动进度条 body::after 的高度
//   ⑤ 波浪分隔带 ::before 的存在性
//   ⑥ 卡片光边的 border-spin 动画
//   ⑦ 跟手水波纹 .ripple__dot 的生成
//   （.reveal 过渡、错落延迟、各降级路径已由 site.spec.mjs 覆盖，此处不重复）
//
// 仅 chromium 运行：这些效果依赖 @property / scroll() 时间线等 Chromium 系能力，
// 在 Firefox 本就不该存在（由 cross-browser.spec.mjs 验证「优雅降级」）。

import { test, expect } from '@playwright/test';

test.skip(({ browserName }) => browserName !== 'chromium', '视觉细节依赖 Chromium 系能力');

test.describe('v7 视觉细节', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/index.html', { waitUntil: 'load' });
  });

  test('流光标题用 background-clip:text 裁切', async ({ page }) => {
    const clip = await page.evaluate(() => {
      const cs = getComputedStyle(document.querySelector('.hero h1'));
      return cs.webkitBackgroundClip || cs.backgroundClip;
    });
    expect(clip, 'hero h1 的 background-clip 应为 text，否则流光会渲成整块色带').toContain('text');
  });

  test('滚动进度条高度为 3px', async ({ page }) => {
    const h = await page.evaluate(() => getComputedStyle(document.body, '::after').height);
    expect(h, 'body::after 是滚动进度条，高度被改掉会破坏视觉节奏').toBe('3px');
  });

  test('波浪分隔带 ::before 存在且有内容', async ({ page }) => {
    const wave = await page.evaluate(() => {
      const secs = [...document.querySelectorAll('main > section')];
      if (secs.length < 2) return null;
      const cs = getComputedStyle(secs[1], '::before');
      return { h: cs.height, content: cs.content };
    });
    expect(wave, '页面结构变化：main 下至少应有 2 个 section 才能放波浪带').not.toBeNull();
    expect(wave.h, '波浪分隔带高度不应为 0').not.toBe('0px');
    expect(wave.content, '波浪分隔带 ::before 应有 content（否则伪元素不渲染）').not.toBe('none');
  });

  test('卡片光边 ::after 在播放 border-spin 动画', async ({ page }) => {
    const anim = await page.evaluate(
      () => getComputedStyle(document.querySelector('.card'), '::after').animationName
    );
    expect(anim, '卡片光边动画名被改掉会静默失效（动画名写错不报错，只是不播）').toBe('border-spin');
  });

  test('按下时生成跟手水波纹 .ripple__dot', async ({ page }) => {
    await page.evaluate(() => {
      const b = document.querySelector('.btn');
      const r = b.getBoundingClientRect();
      b.dispatchEvent(
        new PointerEvent('pointerdown', {
          clientX: r.left + r.width / 2,
          clientY: r.top + r.height / 2,
          bubbles: true,
        })
      );
    });
    await page.waitForTimeout(60);
    const count = await page.evaluate(() => document.querySelectorAll('.ripple__dot').length);
    expect(count, 'pointerdown 应生成至少 1 个水波纹元素').toBeGreaterThanOrEqual(1);
  });
});
