// prefs.js 的纯逻辑测试。
//
// 定位说明：prefs.js 是 IIFE，无法 import，所以这里用 vm 沙箱 + 极简桩来跑。
// 覆盖的是「存储读写、数据校验、导入导出格式」这些不依赖真实浏览器的部分；
// 真实 DOM 交互（面板开关、文件导入）由 tests/e2e 覆盖。
//
// 本次扩展重点：动效开关（motion 字段）的读写与向后兼容。
//
// 运行：node --test tests/js/

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(path.join(here, '..', '..', 'assets', 'prefs.js'), 'utf8');

const KEY = 'xiaoyu-hue:prefs:v1';

/** 造一个够用的 localStorage 桩 */
function makeStorage(initial = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => { map.set(k, String(v)); },
    removeItem: (k) => { map.delete(k); },
    _dump: () => Object.fromEntries(map),
  };
}

/**
 * 在沙箱里执行 prefs.js。
 * pathname 用来模拟"当前在哪一页"，影响阅读进度的键名。
 * attrs 收集所有写进 documentElement 的属性，用来验证 data-motion。
 */
function runPrefs({
  storage = makeStorage(),
  light = false,
  pathname = '/',
  hasMatchMedia = true,
  panel = null,
} = {}) {
  const sandbox = {};
  const listeners = {};
  const attrs = {};

  // .prefs-toggle 的最小桩：initPanel 的两个守卫之一
  const toggleStub = {
    setAttribute() {},
    focus() {},
    contains: () => false,
    addEventListener() {},
    classList: { add() {}, remove() {} },
  };

  sandbox.window = {
    localStorage: storage,
    location: { pathname },
    setTimeout: (fn) => { fn(); return 0; },
    clearTimeout: () => {},
    addEventListener: (t, fn) => { (listeners[t] ||= []).push(fn); },
    matchMedia: hasMatchMedia
      ? (q) => ({ matches: light && /light/.test(q), addEventListener: () => {}, addListener: () => {} })
      : undefined,
  };
  sandbox.document = {
    readyState: 'complete',
    documentElement: {
      setAttribute: (k, v) => { attrs[k] = v; },
      getAttribute: (k) => (k in attrs ? attrs[k] : null),
    },
    // initPanel 需要同时找到 toggle 与 panel 才会继续；
    // 少给 toggle 会让它静默提前返回，syncPanel 一次都不跑，
    // 测试就会「全绿但什么都没验证」。
    querySelector: (sel) => {
      if (sel === '.prefs-panel') return panel;
      if (sel === '.prefs-toggle') return toggleStub;
      return null;
    },
    querySelectorAll: () => [],
    addEventListener: () => {},
    createElement: () => ({
      style: {}, setProperty() {},
      classList: { add(){}, remove(){}, toggle(){} },
      appendChild(){}, setAttribute(){}, click(){},
    }),
    body: { appendChild(){}, removeChild(){} },
  };
  sandbox.Blob = function () {};
  sandbox.URL = { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} };
  sandbox.FileReader = function () {};
  sandbox.localStorage = storage;

  // IIFE 立即执行；把内部状态通过 storage 与 attrs 观察
  runInNewContext(SRC, sandbox);
  return { storage, attrs };
}

/** 造一个最小的面板桩，供 syncPanel 读取选中态。 */
function makePanel(themeOptions, motionOptions) {
  const make = (attr, value) => {
    const btn = {
      _attrs: { [attr]: value },
      _classes: new Set(),
      getAttribute: (k) => (k === attr ? value : null),
      setAttribute(k, v) { if (k.startsWith('aria-')) this._aria = v; },
      // 注意：这里不能用箭头函数 —— 箭头函数不绑定 this，
      // 会写到外层的词法 this 上，_classes 永远是空的，
      // 测试就会「断言通过但什么都没测到」。
      classList: {
        toggle(cls, on) { if (on) btn._classes.add(cls); else btn._classes.delete(cls); },
        add() {}, remove() {},
      },
      addEventListener() {},
    };
    return btn;
  };
  const buttons = [
    ...themeOptions.map((v) => make('data-theme-option', v)),
    ...motionOptions.map((v) => make('data-motion-option', v)),
  ];
  return {
    _buttons: buttons,
    querySelector: () => null,
    querySelectorAll: (sel) => {
      if (sel === '[data-theme-option]') return buttons.filter((b) => b._attrs['data-theme-option']);
      if (sel === '[data-motion-option]') return buttons.filter((b) => b._attrs['data-motion-option']);
      return [];
    },
    classList: { toggle() {}, add() {}, remove() {}, contains: () => false },
  };
}

// ---------- 基础存储行为 ----------

test('全新用户：不写入任何数据，只是空读', () => {
  const { storage } = runPrefs({ pathname: '/' });
  // 首页没有阅读进度可记，不该产生写入
  assert.equal(storage.getItem(KEY), null, '首次访问不该写入 localStorage');
});

test('打开博客文章后记录阅读进度', () => {
  const { storage } = runPrefs({ pathname: '/blog/post-3.html' });
  const raw = storage.getItem(KEY);
  assert.ok(raw, '应当写入 localStorage');
  const obj = JSON.parse(raw);
  assert.equal(obj.schema, 1, 'schema 版本应为 1');
  assert.ok(obj.reading['post-3'], '应记录 post-3');
  assert.match(obj.reading['post-3'].at, /^\d{4}-\d{2}-\d{2}T/, 'at 应为 ISO 时间');
});

test('阅读进度不会被二次访问覆盖首次时间', () => {
  const first = runPrefs({ pathname: '/blog/post-1.html' });
  const t1 = JSON.parse(first.storage.getItem(KEY)).reading['post-1'].at;
  // 用第一次的结果作为第二次的初始存储
  const second = runPrefs({ pathname: '/blog/post-1.html', storage: first.storage });
  const t2 = JSON.parse(second.storage.getItem(KEY)).reading['post-1'].at;
  assert.equal(t2, t1, '重复打开同一篇不该刷新首次阅读时间');
});

test('损坏的 localStorage 数据被忽略，不抛异常', () => {
  assert.doesNotThrow(() => {
    runPrefs({ storage: makeStorage({ [KEY]: '{ 这不是 JSON' }) });
  });
  assert.doesNotThrow(() => {
    runPrefs({ storage: makeStorage({ [KEY]: '{"schema":999,"theme":"rainbow"}' }) });
  });
});

test('schema 不匹配时忽略旧数据', () => {
  const stale = makeStorage({ [KEY]: JSON.stringify({ schema: 0, theme: 'dark', reading: {} }) });
  const { storage } = runPrefs({ storage: stale, pathname: '/blog/post-2.html' });
  const obj = JSON.parse(storage.getItem(KEY));
  assert.equal(obj.schema, 1, '应当用新 schema 覆盖');
  assert.ok(obj.reading['post-2'], '新数据应正常记录');
});

test('localStorage 被禁用时不抛异常（隐私模式）', () => {
  const broken = {
    getItem: () => { throw new Error('SecurityError'); },
    setItem: () => { throw new Error('SecurityError'); },
    removeItem: () => { throw new Error('SecurityError'); },
  };
  assert.doesNotThrow(() => {
    runPrefs({ storage: broken, pathname: '/blog/post-1.html' });
  });
});

test('非文章页不产生阅读记录', () => {
  for (const p of ['/', '/blog/index.html']) {
    const { storage } = runPrefs({ pathname: p });
    assert.equal(storage.getItem(KEY), null, `${p} 不该写入阅读进度`);
  }
});

// ---------- 动效开关（本次新增） ----------

test('全新用户：data-motion 默认写入 on', () => {
  const { attrs } = runPrefs({ pathname: '/' });
  assert.equal(attrs['data-motion'], 'on', '默认必须是显式的 on');
});

test('motion=off 时写入 data-motion=off', () => {
  const storage = makeStorage({
    [KEY]: JSON.stringify({ schema: 1, theme: 'system', motion: 'off', reading: {} }),
  });
  const { attrs } = runPrefs({ storage });
  assert.equal(attrs['data-motion'], 'off');
});

test('老数据缺 motion 字段：保持 on，不静默关掉老用户动效', () => {
  // 本次改动之前的用户数据都没有 motion 字段
  const storage = makeStorage({
    [KEY]: JSON.stringify({ schema: 1, theme: 'dark', reading: { 'post-1': { at: 'x' } } }),
  });
  const { attrs } = runPrefs({ storage });
  assert.equal(attrs['data-motion'], 'on');
});

test('motion 取值非法时退回默认 on', () => {
  for (const weird of ['OFF', 'yes', 0, true, null]) {
    const storage = makeStorage({
      [KEY]: JSON.stringify({ schema: 1, theme: 'system', motion: weird, reading: {} }),
    });
    const { attrs } = runPrefs({ storage });
    assert.equal(attrs['data-motion'], 'on', `motion=${JSON.stringify(weird)} 应退回 on`);
  }
});

test('动效开关与主题互不干扰：改主题不影响 motion', () => {
  const storage = makeStorage({
    [KEY]: JSON.stringify({ schema: 1, theme: 'system', motion: 'off', reading: {} }),
  });
  const { attrs } = runPrefs({ storage, light: true });
  assert.equal(attrs['data-theme'], 'light', '主题应正常跟随系统');
  assert.equal(attrs['data-motion'], 'off', 'motion 不该被主题逻辑覆盖');
});

test('三个属性在任何启动路径下都被写入', () => {
  // 防的是「某个分支漏写 data-motion」——那会导致开关在刷新后失效
  const cases = [
    { pathname: '/' },
    { pathname: '/blog/post-1.html' },
    { storage: makeStorage({ [KEY]: '{坏数据' }) },
    { hasMatchMedia: false },
    { light: true },
  ];
  for (const c of cases) {
    const { attrs } = runPrefs(c);
    for (const k of ['data-theme', 'data-theme-pref', 'data-motion']) {
      assert.ok(attrs[k] !== undefined, `输入 ${JSON.stringify(c)} 下漏写了 ${k}`);
    }
  }
});

// ---------- 面板选中态 ----------

test('面板渲染时把当前 motion 标为选中', () => {
  const storage = makeStorage({
    [KEY]: JSON.stringify({ schema: 1, theme: 'dark', motion: 'off', reading: {} }),
  });
  const panel = makePanel(['system', 'dark', 'light'], ['on', 'off']);
  runPrefs({ storage, panel });

  const themeActive = panel._buttons
    .filter((b) => b._attrs['data-theme-option'])
    .filter((b) => b._classes.has('is-active'))
    .map((b) => b._attrs['data-theme-option']);
  const motionActive = panel._buttons
    .filter((b) => b._attrs['data-motion-option'])
    .filter((b) => b._classes.has('is-active'))
    .map((b) => b._attrs['data-motion-option']);

  assert.deepEqual(themeActive, ['dark'], '主题选中态应指向 dark');
  assert.deepEqual(motionActive, ['off'], '动效选中态应指向 off');
});
