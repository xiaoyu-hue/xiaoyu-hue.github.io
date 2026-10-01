// main.js 的滚动淡入 + 错落编排逻辑测试。
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

const KEY = 'xiaoyu-hue:prefs:v1';

/** 造一个够用的元素桩。parent 用来测试「同父元素算一组」的分组逻辑。 */
function createElement(name, parent = null) {
  const classes = new Set();
  const props = new Map();
  const el = {
    name,
    classes,
    props,
    parentElement: parent,
    classList: {
      add: (cls) => classes.add(cls),
      remove: (cls) => classes.delete(cls),
      toggle: (cls, on) => { if (on) classes.add(cls); else classes.delete(cls); },
      contains: (cls) => classes.has(cls),
    },
    style: {
      setProperty: (k, v) => props.set(k, v),
    },
    getBoundingClientRect: () => ({ top: 100, bottom: 200 }),
  };
  if (parent) parent.children.push(el);
  return el;
}

/** 造一个容器桩，.children 记录它的子元素。 */
function createContainer(name) {
  const c = { name, children: [] };
  return c;
}

/**
 * 在沙箱里执行 main.js。
 *
 * 三个坑：
 * 1. IntersectionObserver 要同时挂在沙箱根和 sandbox.window 上 ——
 *    main.js 里 `new IntersectionObserver()` 从全局解析，
 *    `'IntersectionObserver' in window` 从 window 解析。
 * 2. querySelectorAll 必须返回真数组（main.js 会调用 forEach/filter）。
 * 3. documentElement.getAttribute 要能返回 data-motion，
 *    否则读不到总开关状态。
 */
function runMain({
  reduce = false,
  hasIO = true,
  hasMatchMedia = true,
  elements = [],
  motionAttr = null,
  storage = null,
  throwOnObserve = false,
} = {}) {
  const sandbox = {};
  const observers = [];
  const timers = [];
  const listeners = {};

  if (hasIO) {
    function IntersectionObserver(callback, options) {
      const record = { callback, options, observed: [], unobserved: [] };
      observers.push(record);
      this.observe = (el) => {
        if (throwOnObserve) throw new Error('observe 炸了');
        record.observed.push(el);
      };
      this.unobserve = (el) => record.unobserved.push(el);
    }
    sandbox.IntersectionObserver = IntersectionObserver;
  }

  sandbox.document = {
    readyState: 'complete',
    documentElement: {
      getAttribute: (k) => (k === 'data-motion' ? motionAttr : null),
    },
    body: createContainer('body'),
    visibilityState: 'visible',
    querySelectorAll: (selector) => {
      assert.equal(selector, '.reveal', 'main.js 应当只查询 .reveal');
      return elements;
    },
    querySelector: (selector) => {
      assert.equal(selector, '.nav', 'main.js 只额外查询 .nav');
      return null;   // 本层不测导航，交给 E2E
    },
    addEventListener: (t, fn) => { (listeners[t] ||= []).push(fn); },
  };

  sandbox.window = {
    setTimeout: (fn) => { timers.push(fn); return timers.length; },
    clearTimeout: () => {},
    addEventListener: (t, fn) => { (listeners[t] ||= []).push(fn); },
    scrollY: 0,
    innerHeight: 800,
    requestAnimationFrame: null,
  };
  if (storage) sandbox.window.localStorage = storage;
  if (hasMatchMedia) {
    sandbox.window.matchMedia = (query) => {
      assert.match(
        query,
        /prefers-reduced-motion/,
        'main.js 查询的媒体特性变了',
      );
      return { matches: reduce };
    };
  }
  if (hasIO) {
    sandbox.window.IntersectionObserver = sandbox.IntersectionObserver;
  }

  runInNewContext(SOURCE, sandbox);
  return { observers, elements, timers, listeners };
}

/** 造一个够用的 localStorage 桩 */
function makeStorage(initial = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
  };
}

// ---------- 基础观察器行为 ----------

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

// ---------- 第 1 层：错落编排 ----------

test('同组错落：同父元素下第 2 个起依次注入 --i', () => {
  const wrap = createContainer('wrap');
  const a = createElement('a', wrap);
  const b = createElement('b', wrap);
  const c = createElement('c', wrap);
  runMain({ elements: [a, b, c] });

  assert.equal(a.props.get('--i'), undefined, '第 1 个不该写 --i（走 CSS 缺省 0）');
  assert.equal(b.props.get('--i'), '1', '第 2 个应当是 1');
  assert.equal(c.props.get('--i'), '2', '第 3 个应当是 2');
});

test('同组错落：不同父元素各自从 0 开始编号', () => {
  // 关键行为：错落是「每屏各自错开」，不是「全页统一排队」。
  // 若按全页编号，首屏之外的元素会排到很后面，等用户滚到时延迟早已过完。
  const wrapA = createContainer('A');
  const wrapB = createContainer('B');
  const a1 = createElement('a1', wrapA);
  const a2 = createElement('a2', wrapA);
  const b1 = createElement('b1', wrapB);
  const b2 = createElement('b2', wrapB);
  runMain({ elements: [a1, a2, b1, b2] });

  assert.equal(a2.props.get('--i'), '1');
  assert.equal(b2.props.get('--i'), '1', '第二个容器应当重新从 1 开始');
  assert.equal(b1.props.get('--i'), undefined, '每组第 1 个都不写 --i');
});

test('同组错落：单个元素不写 --i', () => {
  const wrap = createContainer('wrap');
  const only = createElement('only', wrap);
  runMain({ elements: [only] });

  assert.equal(only.props.get('--i'), undefined);
});

// ---------- 第 2 层：降级路径 ----------

test('降级路径 1：用户开了「减少动画」，立即全部显示，不创建观察器', () => {
  const elements = [createElement('a'), createElement('b')];
  const { observers } = runMain({ reduce: true, elements });

  assert.equal(observers.length, 0, '减少动画时不应创建观察器');
  for (const el of elements) {
    assert.ok(el.classes.has('in'), `${el.name} 应当立即可见`);
  }
});

test('降级路径 1：读不到 matchMedia 时按允许动效处理', () => {
  const el = createElement('a');
  const { observers } = runMain({ hasMatchMedia: false, elements: [el] });

  assert.equal(observers.length, 1, '没有 matchMedia 时仍应创建观察器');
  assert.ok(!el.classes.has('in'), '未进入视口时不该加 .in');
});

test('降级路径 3：浏览器不支持 IntersectionObserver，降级为立即全部显示', () => {
  const elements = [createElement('a'), createElement('b')];
  const { observers } = runMain({ hasIO: false, elements });

  assert.equal(observers.length, 0, '不支持时不应创建观察器');
  for (const el of elements) {
    assert.ok(el.classes.has('in'), `${el.name} 应当立即可见`);
  }
});

test('降级路径 4：观察器构造过程中抛异常，全部元素仍可见', () => {
  // 这条是整个系统的第一原则：动效可以没有，内容不能没有。
  const elements = [createElement('a'), createElement('b')];
  assert.doesNotThrow(() => {
    runMain({ elements, throwOnObserve: true });
  });
  for (const el of elements) {
    assert.ok(el.classes.has('in'), `${el.name} 在异常后必须可见，否则就是白屏`);
  }
});

test('降级路径 5：硬超时兜底，1.5 秒后强制显示仍未出现的元素', () => {
  const elements = [createElement('a'), createElement('b')];
  const { timers } = runMain({ elements });

  assert.equal(timers.length, 1, '应当注册一个兜底定时器');
  // 模拟「观察器始终没回调」的场景
  assert.ok(elements.some((el) => !el.classes.has('in')), '前置条件：元素尚未显示');
  timers[0]();
  for (const el of elements) {
    assert.ok(el.classes.has('in'), `${el.name} 超时后必须被强制显示`);
  }
});

test('降级路径 5：已全部显示时定时器不产生副作用', () => {
  const el = createElement('a');
  const { timers, observers } = runMain({ elements: [el] });
  observers[0].callback([{ isIntersecting: true, target: el }]);

  assert.doesNotThrow(() => timers[0]());
  assert.ok(el.classes.has('in'));
});

// ---------- 第 4 层：总开关 ----------

test('总开关：html[data-motion=off] 时不创建观察器，立即全部显示', () => {
  const elements = [createElement('a'), createElement('b')];
  const { observers } = runMain({ elements, motionAttr: 'off' });

  assert.equal(observers.length, 0, '关闭动效后不该再有观察器');
  for (const el of elements) {
    assert.ok(el.classes.has('in'), `${el.name} 应当立即显示`);
  }
});

test('总开关：偏好里 motion=off 时同样降级', () => {
  const storage = makeStorage({
    [KEY]: JSON.stringify({ schema: 1, theme: 'system', motion: 'off', reading: {} }),
  });
  const elements = [createElement('a')];
  const { observers } = runMain({ elements, storage });

  assert.equal(observers.length, 0);
  assert.ok(elements[0].classes.has('in'));
});

test('总开关：偏好里 motion=on 时正常走观察器', () => {
  const storage = makeStorage({
    [KEY]: JSON.stringify({ schema: 1, theme: 'system', motion: 'on', reading: {} }),
  });
  const el = createElement('a');
  const { observers } = runMain({ elements: [el], storage });

  assert.equal(observers.length, 1);
  assert.ok(!el.classes.has('in'));
});

test('偏好数据损坏时不抛异常，按允许动效处理', () => {
  const storage = makeStorage({ [KEY]: '{ 这不是 JSON' });
  const el = createElement('a');
  assert.doesNotThrow(() => {
    const { observers } = runMain({ elements: [el], storage });
    assert.equal(observers.length, 1, '坏数据应当被忽略，退回默认行为');
  });
});

// ---------- 边界 ----------

test('页面没有 .reveal 元素：不报错', () => {
  assert.doesNotThrow(() => runMain({ elements: [] }));
  assert.doesNotThrow(() => runMain({ reduce: true, elements: [] }));
  assert.doesNotThrow(() => runMain({ hasIO: false, elements: [] }));
});

test('无父元素的孤立节点不会导致分组失败', () => {
  const orphan = createElement('orphan', null);
  assert.doesNotThrow(() => runMain({ elements: [orphan] }));
});
