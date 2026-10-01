// 滚动淡入:尊重 prefers-reduced-motion(CSS 已禁用动画时此处也跳过)
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var items = document.querySelectorAll('.reveal');
  if (reduce || !('IntersectionObserver' in window)) {
    items.forEach(function (el) { el.classList.add('in'); });
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
  items.forEach(function (el) { io.observe(el); });
})();

// 导航滚动加深质感:滚过一屏后给 .nav 加 .scrolled(纯 class 切换,守 CSP)
(function () {
  if (typeof document.querySelector !== 'function') return;
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
})();
