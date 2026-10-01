// 从 icon.svg 导出 PWA 需要的 PNG 图标。
//
// 为什么用浏览器而不是图像库：站点本身零依赖，为了生成图标装 sharp/canvas
// 不划算；Playwright 已经在测试依赖里，直接用它截图。
//
// 运行：node scripts/build-icons.mjs

import { chromium } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, '..');
const svgPath = path.join(root, 'assets', 'icons', 'icon.svg');
const svg = readFileSync(svgPath, 'utf8');

// 尺寸清单。maskable 与 any 用同一份矢量（图形已按安全区缩进 80%），
// 区别只在于「是否加圆角」——见下面的圆角处理分支。
const TARGETS = [
  { file: 'icon-192.png', size: 192, rounded: true },
  { file: 'icon-512.png', size: 512, rounded: true },
  { file: 'icon-maskable-512.png', size: 512, rounded: false },
  { file: 'apple-touch-icon-180.png', size: 180, rounded: false },
];

const browser = await chromium.launch();

for (const { file, size, rounded } of TARGETS) {
  const page = await browser.newPage({
    viewport: { width: size, height: size },
    deviceScaleFactor: 1,
  });

  // 把 SVG 内联进 HTML 再截图，避免处理 file:// 的跨源限制。
  // 圆角用 CSS 的 border-radius 裁切；maskable / apple-touch 不裁，
  // 由目标平台自己决定形状。
  const radius = rounded ? Math.round(size * 0.22) : 0;
  await page.setContent(
    `<!doctype html><meta charset="utf-8">
     <style>
       html,body{margin:0;padding:0;background:transparent}
       svg{display:block;width:${size}px;height:${size}px;
           border-radius:${radius}px;overflow:hidden}
     </style>
     ${svg}`,
    { waitUntil: 'load' },
  );

  const buffer = await page.screenshot({
    type: 'png',
    omitBackground: true,
    clip: { x: 0, y: 0, width: size, height: size },
  });

  const out = path.join(root, 'assets', 'icons', file);
  writeFileSync(out, buffer);
  console.log(`✓ ${file}  ${size}×${size}  ${(buffer.length / 1024).toFixed(1)} KB`);
  await page.close();
}

await browser.close();
console.log(`\n共导出 ${TARGETS.length} 个图标。`);
