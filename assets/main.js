// 滚动淡入 + 同组错落编排。
//
// 本文件是「微动效系统」的第 1 层（编排）与第 2 层（降级）的运行时部分。
// CSS 那边的第 0/3/4 层见 assets/style.css 末尾的「微动效系统」块。
//
// 改动前必读的三条约束：
// 1. CSP 为 style-src 'self'，没有 unsafe-inline。所以这里给元素写
//    --i 只能用 el.style.setProperty（行内自定义属性），不能用
//    setAttribute('style', ...)。前者不触发 CSP，后者会。（见下方说明）
// 2. CSP 为 script-src 'self'，一切逻辑都在本文件里，不许内联。
// 3. 无论发生什么，.reveal 元素最终都必须可见。
//    动效可以不要，内容不能没有 —— 这是整个系统的第一原则。

(function () {
  'use strict';

  var REVEAL = '.reveal';
  // 兜底硬超时：超过这个时间还没被观察到的元素，一律强制显示。
  // 存在的意义：IntersectionObserver 有个极小概率不回调的场景 ——
  // 元素在 observer 注册前就被脚本移出文档、或页面在后台标签页里
  // 被浏览器完全冻结。没有这条兜底，用户会看到一块永久空白。
  var REVEAL_TIMEOUT = 1500;

  function all(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  // ---------- 偏好读取 ----------
  // 为什么在这里再读一次 localStorage，而 theme-boot.js 已经读过：
  // theme-boot.js 只负责「第一帧之前」把属性写上去，它跑在 <head> 里，
  // 那时 DOM 还不存在，没法做任何元素级处理。本文件跑在 </body> 前，
  // 需要知道用户关没关动效，才能决定要不要装观察器。
  // 两处读的是同一个键，取值逻辑刻意保持简单，不做二次抽象 ——
  // 抽成共享模块要多一个 <script>，而多一个脚本就多一次串行请求，
  // 对首屏是净损失。
  function readPrefs() {
    try {
      var raw = window.localStorage.getItem('xiaoyu-hue:prefs:v1');
      if (!raw) return null;
      var obj = JSON.parse(raw);
      if (!obj || obj.schema !== 1) return null;
      return obj;
    } catch (e) {
      return null;   // 隐私模式 / 数据损坏：当作没有偏好
    }
  }

  function motionEnabled() {
    // 优先级最高：用户在设置面板里关掉了动效
    var root = document.documentElement;
    if (root && root.getAttribute('data-motion') === 'off') return false;
    var saved = readPrefs();
    if (saved && saved.motion === 'off') return false;
    // 其次：用户在操作系统里声明了「减少动画」
    try {
      if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return false;
      }
    } catch (e) {
      // matchMedia 不可用时按「允许动效」处理，
      // 因为 CSS 那边还有 @media(scripting:none) 与
      // @media(prefers-reduced-motion) 两道独立兜底
    }
    return true;
  }

  // ---------- 第 1 层：编排 ----------
  // 给每个 .reveal 元素标注它在「同组」里的序号，CSS 用
  // transition-delay: min(calc(--stagger-step * --i), 320ms) 消费它。
  //
  // 什么叫同组：同一个直接父元素下的 .reveal 算一组。
  // 为什么不是整页统一编号：整页编号会让首屏之外的元素也排到很后面，
  // 用户滚动到那里时延迟早就过完了，等于白排；
  // 按父元素分组，每一屏内的元素各自从头错落，节奏才对。
  function assignStaggerIndex() {
    var groups = new Map();
    all(REVEAL).forEach(function (el) {
      var parent = el.parentElement || document.body;
      var list = groups.get(parent);
      if (!list) {
        list = [];
        groups.set(parent, list);
      }
      list.push(el);
    });
    groups.forEach(function (list) {
      list.forEach(function (el, i) {
        // 只写真正需要错落的（第 2 个及以后）。
        // 第 1 个不写，让 CSS 的 var(--i, 0) 走缺省值，
        // 少一次行内属性写入 —— 首屏元素越少改动越好。
        if (i === 0) return;
        el.style.setProperty('--i', String(i));
      });
    });
  }

  // ---------- 第 2 层：降级 ----------
  // 路径 3：浏览器不支持 IntersectionObserver
  // 路径 4：动效逻辑本身抛异常
  // 两条都走同一个出口 —— 全部立刻显示。
  function showAll(reason) {
    all(REVEAL).forEach(function (el) { el.classList.add('in'); });
    if (reason && window.console && console.info) {
      console.info('[motion] 已降级为「立即显示」：' + reason);
    }
  }

  function initReveal() {
    if (!motionEnabled()) {
      showAll('用户关闭了动效');
      return;
    }
    if (!('IntersectionObserver' in window)) {
      showAll('浏览器不支持 IntersectionObserver');
      return;
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add('in');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12 });

    all(REVEAL).forEach(function (el) { io.observe(el); });

    // 硬超时兜底。清定时器不是必须的（元素已可见，再 add 一次 .in
    // 无副作用），但保留是为了让「降级日志」只在真的出问题时打出来，
    // 免得正常情况也刷一行 info，掩盖真正的异常。
    var timer = window.setTimeout(function () {
      var pending = all(REVEAL).filter(function (el) {
        return !el.classList.contains('in');
      });
      if (!pending.length) return;
      pending.forEach(function (el) { el.classList.add('in'); });
      if (window.console && console.info) {
        console.info('[motion] ' + pending.length + ' 个元素超时未进入视口，已强制显示');
      }
    }, REVEAL_TIMEOUT);

    // 路径 5：后台标签页暂停。
    // 页面切到后台时浏览器会节流定时器与观察器回调，用户切回来时
    // 可能看到一批元素「集体闪现」。主动在切回时把等待中的元素
    // 一次性显示，把「迟到的集体闪现」换成「一次干净的直达」。
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState !== 'visible') return;
      window.clearTimeout(timer);
      var pending = all(REVEAL).filter(function (el) {
        return !el.classList.contains('in');
      });
      // 只处理已经进入视口的，剩下的继续等观察器 ——
      // 否则用户一路滚到底再切回来，会看到整页瞬间全部亮起
      pending.forEach(function (el) {
        var rect = el.getBoundingClientRect();
        if (rect.top < (window.innerHeight || 0) && rect.bottom > 0) {
          el.classList.add('in');
        }
      });
    });
  }

  // ---------- 导航滚动加深 ----------
  // 滚过 8px 就给 .nav 加 .scrolled（纯 class 切换，守 CSP）。
  // 为什么用 rAF 节流而不是直接改：scroll 事件在某些触控板上
  // 一秒能触发上百次，每次都算一次 class 切换会白白占主线程。
  function initNav() {
    var nav = document.querySelector('.nav');
    if (!nav) return;
    var ticking = false;
    function update() {
      nav.classList.toggle('scrolled', window.scrollY > 8);
      ticking = false;
    }
    window.addEventListener('scroll', function () {
      if (!ticking && window.requestAnimationFrame) {
        ticking = true;
        window.requestAnimationFrame(update);
      } else if (!ticking) {
        update();
      }
    }, { passive: true });
  }

  // ---------- 跟手水波纹（⑩ 微动效新增） ----------
  // 在指针落点注入一个 .ripple__dot，由 CSS 负责「炸开 + 消散」动画。
  // 全程守 CSP：用 el.style.setProperty 写坐标，不写 style 属性（后者会触发 CSP）。
  // 门禁：motionEnabled() 已含 reduced-motion 与 data-motion=off 的双重否决，
  //       关动效时监听器根本不装，CSS 里 .ripple__dot 也另有 display:none 兜底。
  function initRipple() {
    if (!motionEnabled()) return;
    if (!document.addEventListener || !document.createElement) return;
    document.addEventListener('pointerdown', function (e) {
      var t = (e.target && e.target.closest)
        ? e.target.closest('.btn, .card, .post-card')
        : null;
      if (!t) return;
      var r = t.getBoundingClientRect();
      var d = Math.max(r.width, r.height) * 2;
      var span = document.createElement('span');
      span.className = 'ripple__dot';
      span.style.setProperty('width', d + 'px');
      span.style.setProperty('height', d + 'px');
      span.style.setProperty('left', (e.clientX - r.left - d / 2) + 'px');
      span.style.setProperty('top', (e.clientY - r.top - d / 2) + 'px');
      span.addEventListener('animationend', function () {
        if (span.parentNode) span.parentNode.removeChild(span);
      });
      t.appendChild(span);
    }, { passive: true });
  }

  // ---------- 启动 ----------
  // 整段包在 try/catch 里：这是第 2 层「降级路径 4」的落点。
  // 任何一处抛异常（老浏览器缺 API、扩展脚本污染了原型链…），
  // 都必须保证 .reveal 全部可见 —— 顶多动效没了，页面绝不能白屏。
  try {
    assignStaggerIndex();
    initReveal();
    initNav();
    initRipple();
    initCustomCursor();
    initMouseGlow();
    initCardTilt();
    initMagneticButtons();
  } catch (e) {
    showAll('动效脚本异常：' + (e && e.message ? e.message : e));
  }

  // ========== Phase 2 微交互（已纳入上方 IIFE：这样 initCustomCursor 等才能调用
  // 同一作用域内定义的 motionEnabled，修复此前因函数定义在 IIFE 之外而静默失效的 bug） ==========

// ⑪ 自定义光标 — 深海气泡跟随
// 守 CSP：全用 setProperty，不写 style 属性。
function initCustomCursor() {
  if (!motionEnabled()) return;
  // 触屏设备（无精确指针）不创建光标/光晕：它们永不触发 mousemove，
  // 否则留下静止装饰元素卡在视口某处（真实 UI 缺陷）。
  // 与 style.css 的 (hover:none),(pointer:coarse) 隐藏双保险。
  if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
  var cursor = document.createElement('div');
  cursor.className = 'custom-cursor';
  cursor.style.setProperty('position', 'fixed');
  cursor.style.setProperty('width', '20px');
  cursor.style.setProperty('height', '20px');
  cursor.style.setProperty('border', '2px solid rgba(72,202,228,0.8)');
  cursor.style.setProperty('border-radius', '50%');
  cursor.style.setProperty('pointer-events', 'none');
  cursor.style.setProperty('z-index', '9999');
  cursor.style.setProperty('transition', 'transform 0.1s ease-out, width 0.2s, height 0.2s, border-color 0.2s');
  cursor.style.setProperty('transform', 'translate(-50%, -50%)');
  document.body.appendChild(cursor);

  var cursorDot = document.createElement('div');
  cursorDot.className = 'custom-cursor-dot';
  cursorDot.style.setProperty('position', 'fixed');
  cursorDot.style.setProperty('width', '6px');
  cursorDot.style.setProperty('height', '6px');
  cursorDot.style.setProperty('background', 'rgba(72,202,228,0.9)');
  cursorDot.style.setProperty('border-radius', '50%');
  cursorDot.style.setProperty('pointer-events', 'none');
  cursorDot.style.setProperty('z-index', '9999');
  cursorDot.style.setProperty('transition', 'transform 0.05s ease-out');
  cursorDot.style.setProperty('transform', 'translate(-50%, -50%)');
  document.body.appendChild(cursorDot);

  document.addEventListener('mousemove', function(e) {
    cursor.style.setProperty('left', e.clientX + 'px');
    cursor.style.setProperty('top', e.clientY + 'px');
    cursorDot.style.setProperty('left', e.clientX + 'px');
    cursorDot.style.setProperty('top', e.clientY + 'px');
  }, { passive: true });

  document.addEventListener('mouseover', function(e) {
    var target = e.target.closest('a, button, .card, .btn, .tag');
    if (target) {
      cursor.style.setProperty('width', '40px');
      cursor.style.setProperty('height', '40px');
      cursor.style.setProperty('border-color', 'rgba(72,202,228,0.4)');
      cursor.style.setProperty('background', 'rgba(72,202,228,0.05)');
    }
  }, { passive: true });

  document.addEventListener('mouseout', function(e) {
    var target = e.target.closest('a, button, .card, .btn, .tag');
    if (target) {
      cursor.style.setProperty('width', '20px');
      cursor.style.setProperty('height', '20px');
      cursor.style.setProperty('border-color', 'rgba(72,202,228,0.8)');
      cursor.style.setProperty('background', 'transparent');
    }
  }, { passive: true });
}

// ⑫ 鼠标跟随光晕 — 深海氛围
function initMouseGlow() {
  if (!motionEnabled()) return;
  // 同上：触屏设备不创建鼠标光晕
  if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
  var glow = document.createElement('div');
  glow.className = 'mouse-glow';
  glow.style.setProperty('position', 'fixed');
  glow.style.setProperty('width', '400px');
  glow.style.setProperty('height', '400px');
  glow.style.setProperty('background', 'radial-gradient(circle, rgba(72,202,228,0.08) 0%, transparent 70%)');
  glow.style.setProperty('pointer-events', 'none');
  glow.style.setProperty('z-index', '1');
  glow.style.setProperty('transform', 'translate(-50%, -50%)');
  glow.style.setProperty('transition', 'left 0.3s ease-out, top 0.3s ease-out');
  document.body.appendChild(glow);

  document.addEventListener('mousemove', function(e) {
    glow.style.setProperty('left', e.clientX + 'px');
    glow.style.setProperty('top', e.clientY + 'px');
  }, { passive: true });
}

// ⑬ 卡片 3D 倾斜效果
function initCardTilt() {
  if (!motionEnabled()) return;
  var cards = document.querySelectorAll('.card, .post-card');
  cards.forEach(function(card) {
    card.style.setProperty('transform-style', 'preserve-3d');

    card.addEventListener('mousemove', function(e) {
      var rect = card.getBoundingClientRect();
      var x = (e.clientX - rect.left) / rect.width - 0.5;
      var y = (e.clientY - rect.top) / rect.height - 0.5;
      var tiltX = y * -8;
      var tiltY = x * 8;
      card.style.setProperty('transform', 'perspective(1000px) rotateX(' + tiltX + 'deg) rotateY(' + tiltY + 'deg) translateY(-8px) scale(1.02)');
    }, { passive: true });

    card.addEventListener('mouseleave', function() {
      card.style.setProperty('transform', 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0px) scale(1)');
    }, { passive: true });
  });
}

// ⑭ 磁吸按钮效果
function initMagneticButtons() {
  if (!motionEnabled()) return;
  var buttons = document.querySelectorAll('.btn');
  buttons.forEach(function(btn) {
    btn.addEventListener('mousemove', function(e) {
      var rect = btn.getBoundingClientRect();
      var x = e.clientX - rect.left - rect.width / 2;
      var y = e.clientY - rect.top - rect.height / 2;
      btn.style.setProperty('transform', 'translate(' + (x * 0.15) + 'px, ' + (y * 0.15) + 'px)');
    }, { passive: true });

    btn.addEventListener('mouseleave', function() {
      btn.style.setProperty('transform', 'translate(0px, 0px)');
    }, { passive: true });
  });
}
})();
