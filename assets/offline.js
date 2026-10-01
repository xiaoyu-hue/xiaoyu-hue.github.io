// 离线页的「重试」按钮。
//
// 为什么单独一个文件而不是内联 <script>:
// CSP 的 script-src 'self' 不带 unsafe-inline，内联脚本会被直接拦掉。
//
// 逻辑本身很简单 —— 能读到这个文件就说明缓存管用，
// 点击后重新加载，此时网络若已恢复，Service Worker 的网络优先策略
// 会自然地把用户带回真实页面。
(function () {
  'use strict';

  function init() {
    var btn = document.querySelector('.offline-retry');
    if (!btn) return;
    btn.addEventListener('click', function () {
      btn.disabled = true;
      btn.textContent = '正在重试…';
      window.location.reload();
    });
  }

  // 顺便把「在线了」这件事反馈给用户，避免他反复点重试
  function watchOnline() {
    window.addEventListener('online', function () {
      var note = document.querySelector('.offline-note');
      if (note) note.textContent = '网络已恢复，点击下方按钮回到最新内容。';
    });
  }

  function boot() {
    init();
    watchOnline();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
