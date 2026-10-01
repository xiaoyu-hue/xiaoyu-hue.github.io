// 站点偏好设置:主题(深色/浅色/跟随系统) + 动效开关 + 博客阅读进度
//
// 三条硬约束(改动前请先读):
// 1. CSP 为 style-src 'self',没有 unsafe-inline —— 任何 el.style.xxx 或
//    setAttribute('style',...) 都会触发违规并被拦截。所以主题切换一律用
//    class/属性切换(html[data-theme]、html[data-motion])实现。
//    唯一的例外是 setProperty('--i', ...),它写的是自定义属性、
//    作用在 CSSOM 而非 style 特性上,不触发 CSP(见 assets/main.js)。
// 2. CSP 为 connect-src 'self' —— 不做任何联网同步,数据只留在本机。
// 3. theme-boot.js 已在首屏应用过一次主题与动效。本文件是"运行时"的
//    唯一真相来源,两者必须对同一个 KEY、同一个 schema 保持兼容。
(function () {
  'use strict';

  var KEY = 'xiaoyu-hue:prefs:v1';
  var SCHEMA = 1;
  var THEMES = ['system', 'dark', 'light'];
  var MOTIONS = ['on', 'off'];

  // ---------- 存储层 ----------
  function read() {
    try {
      var raw = window.localStorage.getItem(KEY);
      if (!raw) return null;
      var obj = JSON.parse(raw);
      if (!obj || typeof obj !== 'object') return null;
      if (obj.schema !== SCHEMA) return null;   // 版本不符则忽略,交给导入流程处理
      return obj;
    } catch (e) {
      // localStorage 可能被禁用(隐私模式);静默降级,站点功能不受影响
      return null;
    }
  }

  function write(data) {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(data));
      return true;
    } catch (e) {
      return false;   // 写失败(配额/隐私模式)时不抛错,只是本次不持久化
    }
  }

  function defaults() {
    return {
      schema: SCHEMA,
      theme: 'system',
      motion: 'on',      // 'on' | 'off'，见 applyMotion()
      reading: {},       // { "post-1": { at: "ISO 时间" } }
      updatedAt: new Date().toISOString(),
    };
  }

  var state = (function () {
    var d = defaults();
    var saved = read();
    if (!saved) return d;
    // 逐字段做白名单校验,避免把损坏数据带进运行时
    if (THEMES.indexOf(saved.theme) >= 0) d.theme = saved.theme;
    // 老数据没有 motion 字段（PWA 版本升级上来的用户），
    // 缺省保持 'on' —— 不能因为字段缺失就静默关掉他们的动效
    if (MOTIONS.indexOf(saved.motion) >= 0) d.motion = saved.motion;
    if (saved.reading && typeof saved.reading === 'object') d.reading = saved.reading;
    if (typeof saved.updatedAt === 'string') d.updatedAt = saved.updatedAt;
    return d;
  })();

  function save() {
    state.updatedAt = new Date().toISOString();
    return write(state);
  }

  // ---------- 主题 ----------
  function effectiveTheme() {
    if (state.theme !== 'system') return state.theme;
    // 跟随系统:交给 matchMedia 判断,没有 matchMedia 时按深色(站点原有默认)
    try {
      return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    } catch (e) {
      return 'dark';
    }
  }

  function applyTheme() {
    var root = document.documentElement;
    var t = effectiveTheme();
    // 用 data 属性而不是 class,语义更清楚,也便于 CSS 里做 [data-theme="light"] 覆盖
    root.setAttribute('data-theme', t);
    // 记录用户真实选择(而非生效值),面板上的选中态要用它
    root.setAttribute('data-theme-pref', state.theme);
    var m = document.querySelector('meta[name="color-scheme"]');
    if (m) m.setAttribute('content', t === 'light' ? 'light dark' : 'dark light');
  }

  function setTheme(theme) {
    if (THEMES.indexOf(theme) < 0) return false;
    state.theme = theme;
    applyTheme();
    save();
    syncPanel();
    return true;
  }

  // ---------- 动效总开关 ----------
  // 第 4 层开关的落点：把偏好写到 html[data-motion]，
  // CSS 那边的 :root[data-motion="off"] 会把全部时长/位移令牌归零。
  //
  // 为什么开关必须落在 CSS 变量上，而不是让 JS 去逐个关动画：
  // 逐个关意味着每加一个动效组件都要记得回来改这里，一定会漏。
  // 归零令牌则是一次性的全局作用 —— 新加的任何动效只要用了令牌，
  // 自动受开关管辖，不需要额外维护。
  //
  // 注意：本开关不影响系统级 prefers-reduced-motion。
  // 系统偏好由 CSS 的 @media 独立生效，二者是"或"的关系 ——
  // 系统说不要动效，用户在本站也开不回来（这是正确的：
  // 系统级设置表达的是无障碍需求，不该被站点覆盖）。
  function applyMotion() {
    document.documentElement.setAttribute('data-motion', state.motion);
  }

  function setMotion(motion) {
    if (MOTIONS.indexOf(motion) < 0) return false;
    state.motion = motion;
    applyMotion();
    save();
    syncPanel();
    return true;
  }

  // ---------- 博客阅读进度 ----------
  function currentPostId() {
    var m = window.location.pathname.match(/post-(\d+)\.html$/);
    return m ? 'post-' + m[1] : null;
  }

  function markRead() {
    var id = currentPostId();
    if (!id) return;
    if (state.reading[id] && state.reading[id].at) return;  // 已记录过就不覆盖首次时间
    state.reading[id] = { at: new Date().toISOString() };
    save();
    renderReading();
  }

  function readCount() {
    return Object.keys(state.reading).length;
  }

  // ---------- 面板渲染 ----------
  function syncPanel() {
    var panel = document.querySelector('.prefs-panel');
    if (!panel) return;
    var current = state.theme;
    Array.prototype.forEach.call(panel.querySelectorAll('[data-theme-option]'), function (btn) {
      var on = btn.getAttribute('data-theme-option') === current;
      btn.classList.toggle('is-active', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    // 动效开关：同一套"选中态 + aria-pressed"约定，
    // 屏幕阅读器读到的状态与实际生效状态保持一致
    var motion = state.motion;
    Array.prototype.forEach.call(panel.querySelectorAll('[data-motion-option]'), function (btn) {
      var on = btn.getAttribute('data-motion-option') === motion;
      btn.classList.toggle('is-active', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }

  function renderReading() {
    var box = document.querySelector('.prefs-reading');
    if (!box) return;
    var ids = Object.keys(state.reading).sort();
    box.textContent = '';
    if (!ids.length) {
      var p = document.createElement('p');
      p.className = 'prefs-empty';
      p.textContent = '还没有阅读记录。打开任意一篇博客后会在这里出现。';
      box.appendChild(p);
      return;
    }
    var ul = document.createElement('ul');
    ul.className = 'prefs-list';
    ids.forEach(function (id) {
      var li = document.createElement('li');
      var a = document.createElement('a');
      // 首页与博客页的层级不同,路径要跟着走
      var prefix = /\/blog\//.test(window.location.pathname) ? '' : 'blog/';
      a.href = prefix + id + '.html';
      a.textContent = id;
      var time = document.createElement('time');
      var at = state.reading[id].at || '';
      time.textContent = at ? at.slice(0, 10) : '';
      li.appendChild(a);
      li.appendChild(time);
      ul.appendChild(li);
    });
    box.appendChild(ul);
  }

  function renderStorageNote() {
    var el = document.querySelector('.prefs-storage');
    if (!el) return;
    var ok = true;
    try {
      window.localStorage.setItem('xiaoyu-hue:probe', '1');
      window.localStorage.removeItem('xiaoyu-hue:probe');
    } catch (e) {
      ok = false;
    }
    el.textContent = ok
      ? '数据只存在这台设备的浏览器里，不会上传到任何服务器。'
      : '当前浏览器禁用了本地存储（可能是隐私模式），设置无法保存。';
    el.classList.toggle('is-warn', !ok);
  }

  // ---------- 导入导出 ----------
  // 导出时插入的 <a> 会被临时挂到 body 上，它的 click() 会冒泡到 document，
  // 被「点击面板外部就关闭」的逻辑误判，导致面板在导出后立刻关掉、
  // 用户看不到「已导出」的提示。用一个标记让这次点击不参与外部判定。
  var programmaticClick = false;

  function exportJSON() {
    var payload = {
      schema: SCHEMA,
      exportedAt: new Date().toISOString(),
      source: 'xiaoyu-hue.github.io',
      data: { theme: state.theme, motion: state.motion, reading: state.reading },
    };
    var text = JSON.stringify(payload, null, 2);
    var blob = new Blob([text], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    var d = new Date();
    var stamp = d.getFullYear() + '-' +
      String(d.getMonth() + 1).padStart(2, '0') + '-' +
      String(d.getDate()).padStart(2, '0');
    a.href = url;
    a.download = 'xiaoyu-hue-prefs-' + stamp + '.json';
    // 挂到一个不在面板内的位置，同时标记这是程序触发
    a.setAttribute('data-prefs-internal', '1');
    document.body.appendChild(a);
    programmaticClick = true;
    a.click();
    programmaticClick = false;
    document.body.removeChild(a);
    // 立刻 revoke 会让部分浏览器来不及下载,延后释放
    window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function importJSON(text) {
    var parsed;
    try {
      parsed = JSON.parse(text);
    } catch (e) {
      return { ok: false, msg: '不是合法的 JSON 文件。' };
    }
    if (!parsed || typeof parsed !== 'object') {
      return { ok: false, msg: '文件内容不是对象。' };
    }
    if (parsed.schema !== SCHEMA) {
      return { ok: false, msg: '版本不匹配（期望 schema ' + SCHEMA + '，实际 ' + parsed.schema + '）。' };
    }
    var d = parsed.data;
    if (!d || typeof d !== 'object') {
      return { ok: false, msg: '文件里缺少 data 字段。' };
    }
    if (THEMES.indexOf(d.theme) < 0) {
      return { ok: false, msg: '主题值不合法。' };
    }
    // motion 是后加的字段。老备份文件里没有它，
    // 此时保持当前设置而不是判定为非法 —— 拒绝整个文件会让用户
    // 无法用旧备份恢复主题和阅读记录，代价远大于收益。
    if (d.motion !== undefined && MOTIONS.indexOf(d.motion) < 0) {
      return { ok: false, msg: '动效设置值不合法。' };
    }
    state.theme = d.theme;
    if (MOTIONS.indexOf(d.motion) >= 0) state.motion = d.motion;
    state.reading = (d.reading && typeof d.reading === 'object') ? d.reading : {};
    applyTheme();
    applyMotion();
    save();
    syncPanel();
    renderReading();
    return { ok: true, msg: '已导入：主题 ' + d.theme + '，阅读记录 ' + readCount() + ' 条。' };
  }

  function resetAll() {
    state = defaults();
    applyTheme();
    applyMotion();
    save();
    syncPanel();
    renderReading();
  }

  function notify(el, msg, isWarn) {
    if (!el) return;
    el.textContent = msg;
    el.classList.toggle('is-warn', !!isWarn);
    el.classList.add('is-visible');
  }

  // ---------- 面板交互 ----------
  function initPanel() {
    var toggle = document.querySelector('.prefs-toggle');
    var panel = document.querySelector('.prefs-panel');
    if (!toggle || !panel) return;

    var lastFocus = null;

    function open() {
      lastFocus = document.activeElement;
      panel.classList.add('is-open');
      toggle.setAttribute('aria-expanded', 'true');
      var first = panel.querySelector('[data-theme-option]');
      if (first) first.focus();
    }
    function close() {
      panel.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
      if (lastFocus && lastFocus.focus) lastFocus.focus();
    }
    function isOpen() { return panel.classList.contains('is-open'); }

    toggle.addEventListener('click', function () {
      if (isOpen()) { close(); } else { open(); }
    });

    // Esc 关闭
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && isOpen()) close();
    });

    // 点击面板外部关闭
    document.addEventListener('click', function (e) {
      if (!isOpen()) return;
      // 导出时程序触发的下载点击不算「外部点击」，否则面板会自己关掉
      if (programmaticClick) return;
      if (panel.contains(e.target) || toggle.contains(e.target)) return;
      close();
    });

    // 主题三选一
    Array.prototype.forEach.call(panel.querySelectorAll('[data-theme-option]'), function (btn) {
      btn.addEventListener('click', function () {
        setTheme(btn.getAttribute('data-theme-option'));
      });
    });

    // 动效开关
    Array.prototype.forEach.call(panel.querySelectorAll('[data-motion-option]'), function (btn) {
      btn.addEventListener('click', function () {
        setMotion(btn.getAttribute('data-motion-option'));
      });
    });

    // 导出
    var btnExport = panel.querySelector('.prefs-export');
    if (btnExport) {
      btnExport.addEventListener('click', function () {
        var msg = panel.querySelector('.prefs-msg');
        exportJSON();
        notify(msg, '已导出为 JSON 文件。');
      });
    }

    // 导入(隐藏的 file input 由按钮触发)
    var inputFile = panel.querySelector('.prefs-file');
    var btnImport = panel.querySelector('.prefs-import');
    if (inputFile && btnImport) {
      btnImport.addEventListener('click', function () { inputFile.click(); });
      inputFile.addEventListener('change', function () {
        var msg = panel.querySelector('.prefs-msg');
        var file = inputFile.files && inputFile.files[0];
        if (!file) return;
        var reader = new FileReader();
        reader.onload = function () {
          var res = importJSON(String(reader.result));
          notify(msg, res.msg, !res.ok);
          inputFile.value = '';   // 允许重复导入同一个文件
        };
        reader.onerror = function () {
          notify(msg, '文件读取失败。', true);
        };
        reader.readAsText(file);
      });
    }

    // 清空
    var btnReset = panel.querySelector('.prefs-reset');
    if (btnReset) {
      var armed = false;
      var armTimer = null;
      btnReset.addEventListener('click', function () {
        var msg = panel.querySelector('.prefs-msg');
        // 二次确认:避免误点丢掉记录
        if (!armed) {
          armed = true;
          btnReset.classList.add('is-armed');
          btnReset.textContent = '再点一次确认清空';
          notify(msg, '清空后无法恢复，建议先导出备份。', true);
          armTimer = window.setTimeout(function () {
            armed = false;
            btnReset.classList.remove('is-armed');
            btnReset.textContent = '清空全部数据';
          }, 4000);
          return;
        }
        window.clearTimeout(armTimer);
        armed = false;
        btnReset.classList.remove('is-armed');
        btnReset.textContent = '清空全部数据';
        resetAll();
        notify(msg, '已清空，恢复为默认设置。');
      });
    }

    syncPanel();
    renderReading();
    renderStorageNote();
  }

  // ---------- 启动 ----------
  // 主题与动效必须在最早时机应用,避免刷新时先闪一下默认状态。
  // theme-boot.js 已经在 <head> 里应用过一次;这里再应用一次不是冗余 ——
  // 它是为了让"页面被 bfcache 还原"和"运行中被别的脚本改过属性"
  // 这两种情况下,运行时的真相来源仍然收敛到本文件。
  applyTheme();
  applyMotion();

  // 系统主题变化时,只有「跟随系统」模式下才需要跟着变
  try {
    var mq = window.matchMedia('(prefers-color-scheme: light)');
    var onChange = function () { if (state.theme === 'system') applyTheme(); };
    if (mq.addEventListener) mq.addEventListener('change', onChange);
    else if (mq.addListener) mq.addListener(onChange);
  } catch (e) { /* 不支持就维持现状 */ }

  function boot() {
    initPanel();
    markRead();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
