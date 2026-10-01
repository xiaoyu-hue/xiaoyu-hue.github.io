// main.js 滚动淡入的逻辑测试。
//
// 说明这一层的定位：main.js 是一个立即执行函数（IIFE），无法 import，
// 所以这里用 vm 沙箱加一层极简 DOM 桩来执行它。它验证的是「分支逻辑」
// 而不是浏览器真实行为 —— 真实行为由 tests/e2e 用真 Chromium 覆盖。
// 这一层的价值是秒级反馈，不需要下载浏览器。
//
// 运行：node --test tests/js/

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const SOURCE = readFileSync(
  path.join(here, '..', '..', 'assets', 'main.js'),
  'utf8',
);

function createElement(name) {
  const classes = new Set();
  return {
    name,
    classes,
    classList: {
      add: (cls) => classes.add(cls),
    },
  };
}

/**
 * 在沙箱里执行 main.js。
 *
 * 两个坑：
 * 1. IntersectionObserver 要同时挂在沙箱根和 sandbox.window 上 ——
 *    main.js 里 `new IntersectionObserver()` 从全局解析，
 *    `'IntersectionObserver' in window` 从 window 解析。
 * 2. querySelectorAll 必须返回真数组（main.js 会调用 forEach）。
 */
function runMain({ reduce = false, hasIO = true, hasMatchMedia = true, elements = [] } = {}) {
  const sandbox = {};
  const observers = [];

  if (hasIO) {
    function IntersectionObserver(callback, options) {
      const record = { callback, options, observed: [], unobserved: [] };
      observers.push(record);
      this.observe = (el) => record.observed.push(el);
      this.unobserve = (el) => record.unobserved.push(el);
    }
    sandbox.IntersectionObserver = IntersectionObserver;
  }

  sandbox.document = {
    querySelectorAll: (selector) => {
      assert.equal(selector, '.reveal', 'main.js 应当只查询 .reveal');
      return elements;
    },
  };

  sandbox.window = {};
  if (hasMatchMedia) {
    sandbox.window.matchMedia = (query) => {
      assert.equal(
        query,
        '(prefers-reduced-motion: reduce)',
        'main.js 查询的媒体特性变了',
      );
      return { matches: reduce };
    };
  }
  if (hasIO) {
    sandbox.window.IntersectionObserver = sandbox.IntersectionObserver;
  }

  runInNewContext(SOURCE, sandbox);
  return { observers, elements };
}

test('正常环境：创建观察器，阈值 0.12，观察全部 .reveal', () => {
  const elements = [createElement('a'), createElement('b'), createElement('c')];
  const { observers } = runMain({ elements });

  assert.equal(observers.length, 1, '应当创建一个 IntersectionObserver');
  assert.equal(observers[0].options.threshold, 0.12, '阈值应当是 0.12');
  assert.deepEqual(observers[0].observed, elements, '应当观察全部 .reveal 元素');
  for (const el of elements) {
    assert.ok(!el.classes.has('in'), `${el.name} 未进入视口时不该加 .in`);
  }
});

test('正常环境：元素进入视口后加 .in 并停止观察', () => {
  const el = createElement('a');
  const { observers } = runMain({ elements: [el] });
  const [observer] = observers;

  observer.callback([{ isIntersecting: true, target: el }]);
  assert.ok(el.classes.has('in'), '进入视口后应当加 .in');
  assert.deepEqual(observer.unobserved, [el], '加完 .in 应当 unobserve，避免重复触发');
});

test('正常环境：未进入视口的元素保持原样', () => {
  const el = createElement('a');
  const { observers } = runMain({ elements: [el] });

  observers[0].callback([{ isIntersecting: false, target: el }]);
  assert.ok(!el.classes.has('in'), '未进入视口不该加 .in');
  assert.deepEqual(observers[0].unobserved, [], '不该 unobserve');
});

test('用户开了「减少动画」：立即全部显示，不创建观察器', () => {
  const elements = [createElement('a'), createElement('b')];
  const { observers } = runMain({ reduce: true, elements });

  assert.equal(observers.length, 0, '减少动画时不应创建观察器');
  for (const el of elements) {
    assert.ok(el.classes.has('in'), `${el.name} 应当立即可见`);
  }
});

test('浏览器不支持 IntersectionObserver：降级为立即全部显示', () => {
  const elements = [createElement('a'), createElement('b')];
  const { observers } = runMain({ hasIO: false, elements });

  assert.equal(observers.length, 0, '不支持时不应创建观察器');
  for (const el of elements) {
    assert.ok(el.classes.has('in'), `${el.name} 应当立即可见`);
  }
});

test('浏览器没有 matchMedia：不影响，照常走观察器分支', () => {
  const el = createElement('a');
  const { observers } = runMain({ hasMatchMedia: false, elements: [el] });

  assert.equal(observers.length, 1, '没有 matchMedia 时仍应创建观察器');
  assert.ok(!el.classes.has('in'), '未进入视口时不该加 .in');
});

test('页面没有 .reveal 元素：不报错', () => {
  assert.doesNotThrow(() => runMain({ elements: [] }));
  assert.doesNotThrow(() => runMain({ reduce: true, elements: [] }));
  assert.doesNotThrow(() => runMain({ hasIO: false, elements: [] }));
});
