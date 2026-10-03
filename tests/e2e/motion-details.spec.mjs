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

  // 回归护栏：v7 特效层的降级规则曾因「源顺序」而被反压失效。
  //
  // 背景：.card::after（焦散描边）定义在文件第 1332 行附近，而 CSS 里
  // 写在第 1093 行「降级层」和约 1200 行「总开关」中的
  //   .card::after{animation:none}
  // 都在它**之前**。CSS 同权重靠源顺序取胜，后面的 animation 会赢，
  // 于是 reduced-motion 下描边照转 —— 降级静默失效。
  //
  // 这类 bug 极其隐蔽：逻辑测试绿、a11y 扫描绿、像素快照也只能告诉你
  // 「有差异」，不会说「降级没生效」。只有真浏览器里读 computed style
  // 的 animationName 才看得出来。所以专门钉一条在这里。
  test('reduced-motion 下焦散描边与氛围动画必须真正停下（源顺序回归护栏）', async ({
    page,
  }) => {
    // 前置条件：默认媒体环境下这些动画确实在播。
    // 没有这一步，一旦哪天特效被整体删掉，本条会「因为本来就没有」而假通过。
    const before = await page.evaluate(() => ({
      spin: getComputedStyle(document.querySelector('.card'), '::after').animationName,
      bg: getComputedStyle(document.querySelector('.ocean-bg')).animationName,
    }));
    expect(before.spin, '前置条件失败：默认应有焦散描边动画').toBe('border-spin');
    expect(before.bg, '前置条件失败：默认应有氛围背景动画').not.toBe('none');

    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.reload({ waitUntil: 'load' });

    const names = await page.evaluate(() => {
      const spin = getComputedStyle(document.querySelector('.card'), '::after').animationName;
      const bg = getComputedStyle(document.querySelector('.ocean-bg')).animationName;
      return { spin, bg };
    });

    expect(
      names.spin,
      '焦散描边在 reduced-motion 下仍在播动画：说明降级规则被后面的特效规则按源顺序反压了，' +
        '需要把降级补丁挪到文件最末尾'
    ).toBe('none');
    expect(names.bg, '氛围背景在 reduced-motion 下仍在播动画，降级失效').toBe('none');
  });

  test('data-motion=off 下同一批特效也必须停（总开关回归护栏）', async ({ page }) => {
    // 先确认"没开开关时确实在播"——否则这条测试可能因为默认就是停的而假通过。
    const before = await page.evaluate(
      () => getComputedStyle(document.querySelector('.card'), '::after').animationName
    );
    expect(before, '前置条件失败：默认状态下焦散描边本应播放，否则本条断言无意义').toBe(
      'border-spin'
    );

    await page.evaluate(() => {
      document.documentElement.dataset.motion = 'off';
    });
    await page.waitForTimeout(50);

    const names = await page.evaluate(() => {
      const spin = getComputedStyle(document.querySelector('.card'), '::after').animationName;
      const bg = getComputedStyle(document.querySelector('.ocean-bg')).animationName;
      const hero = getComputedStyle(document.querySelector('.hero h1')).animationName;
      return { spin, bg, hero };
    });

    expect(names.spin, '总开关下焦散描边仍在播').toBe('none');
    expect(names.bg, '总开关下氛围背景仍在播').toBe('none');
    expect(names.hero, '总开关下流光标题仍在播').toBe('none');
  });
});
