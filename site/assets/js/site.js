/* 柴垣医院 テストサイト 共通スクリプト（外部ライブラリなし） */
(function () {
  'use strict';
  var d = document;

  /* テストバナーの高さを CSS 変数へ（スマホの MENU ボタン位置に使う） */
  var banner = d.getElementById('test-banner');
  if (banner) d.documentElement.style.setProperty('--banner-h', banner.offsetHeight + 'px');

  /* ---- 現在ページの強調 ---- */
  var path = location.pathname.replace(/index\.html$/, '');
  d.querySelectorAll('#nav a, #menu-main_menu a').forEach(function (a) {
    var href = a.getAttribute('href');
    if (href && href !== '/' && path.indexOf(href) === 0) {
      a.setAttribute('aria-current', 'page');
      var li = a.closest('#nav > li');
      if (li) li.classList.add('is-current');
    }
  });

  /* ---- PC ナビ：子メニューをクリックでも開閉（タブレット対応） ---- */
  d.querySelectorAll('#nav > li.menu-item-has-children > button').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var li = btn.parentElement, open = li.classList.toggle('is-open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      d.querySelectorAll('#nav > li.is-open').forEach(function (o) { if (o !== li) { o.classList.remove('is-open'); o.querySelector('button').setAttribute('aria-expanded', 'false'); } });
    });
  });
  d.addEventListener('click', function (e) {
    if (!e.target.closest('#nav')) d.querySelectorAll('#nav > li.is-open').forEach(function (o) { o.classList.remove('is-open'); o.querySelector('button').setAttribute('aria-expanded', 'false'); });
  });

  /* ---- スクロールでナビを固定 ---- */
  var gNav = d.getElementById('gNav'), header = d.getElementById('header');
  function onScroll() {
    if (!gNav || !header || window.innerWidth <= 768) return;
    var fix = window.scrollY > header.offsetTop + header.offsetHeight;
    gNav.classList.toggle('is-fixed', fix);
    d.body.classList.toggle('nav-fixed', fix);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
  onScroll();

  /* ---- スマホメニュー ---- */
  var mobile = d.getElementById('mobile'), sidr = d.getElementById('sidr'), closeBtn = d.getElementById('sidr-close');
  function setMenu(open) {
    if (!sidr) return;
    sidr.classList.toggle('is-open', open);
    sidr.setAttribute('aria-hidden', open ? 'false' : 'true');
    mobile.classList.toggle('side-open', open);
    mobile.setAttribute('aria-expanded', open ? 'true' : 'false');
    d.body.classList.toggle('menu-open', open);
    if (open) closeBtn.focus(); else mobile.focus();
  }
  if (mobile) mobile.addEventListener('click', function () { setMenu(true); });
  if (closeBtn) closeBtn.addEventListener('click', function () { setMenu(false); });
  d.addEventListener('keydown', function (e) { if (e.key === 'Escape' && sidr && sidr.classList.contains('is-open')) setMenu(false); });
  d.querySelectorAll('#menu-main_menu li.menu-item-has-children > button.accordion-elm').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var li = btn.parentElement, open = li.classList.toggle('is-open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  });

  /* ---- トップのスライダー ---- */
  var slider = d.querySelector('.hero-slider');
  if (slider) {
    var slides = slider.querySelectorAll('.hero-slider__slide'), dots = slider.querySelectorAll('.hero-slider__dots button');
    var i = 0, timer, n = slides.length;
    function show(k) {
      i = (k + n) % n;
      slides.forEach(function (s, j) { s.classList.toggle('is-active', j === i); });
      dots.forEach(function (b, j) { if (j === i) b.setAttribute('aria-current', 'true'); else b.removeAttribute('aria-current'); });
    }
    function start() { stop(); if (n > 1 && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) timer = setInterval(function () { show(i + 1); }, 8000); }
    function stop() { if (timer) clearInterval(timer); }
    dots.forEach(function (b, j) { b.addEventListener('click', function () { show(j); start(); }); });
    var prev = slider.querySelector('.hero-slider__nav--prev'), next = slider.querySelector('.hero-slider__nav--next');
    if (prev) prev.addEventListener('click', function () { show(i - 1); start(); });
    if (next) next.addEventListener('click', function () { show(i + 1); start(); });
    slider.addEventListener('mouseenter', stop); slider.addEventListener('mouseleave', start);
    slider.addEventListener('focusin', stop); slider.addEventListener('focusout', start);
    show(0); start();
  }

  /* ---- FAQ：カテゴリ切替と Q&A の開閉 ---- */
  d.querySelectorAll('.faq-page__category').forEach(function (btn) {
    btn.addEventListener('click', function () {
      d.querySelectorAll('.faq-page__category').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
      d.querySelectorAll('.faq-page__panel').forEach(function (p) { p.hidden = true; });
      btn.setAttribute('aria-pressed', 'true');
      var panel = d.getElementById(btn.getAttribute('aria-controls'));
      if (panel) { panel.hidden = false; var h = panel.querySelector('h3, h2'); if (h) { h.setAttribute('tabindex', '-1'); h.focus(); } }
    });
  });
  d.querySelectorAll('.faq-page__question').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var open = btn.getAttribute('aria-expanded') !== 'true';
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      var a = d.getElementById(btn.getAttribute('aria-controls')); if (a) a.hidden = !open;
    });
  });

  /* ---- 完了画面：どのフォームから来たかで案内を切り替える ---- */
  var guides = d.querySelectorAll('.thanks-box__guide');
  if (guides.length) {
    var f = (new URLSearchParams(location.search).get('form') || '');
    var kind = /^recruit/.test(f) ? 'recruit' : (/^community/.test(f) ? 'consult' : 'contact');
    guides.forEach(function (g) { g.hidden = g.getAttribute('data-form') !== kind; });
  }

  /* ---- フォーム：入力チェックとプレビュー環境の扱い ---- */
  var isPreview = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname) || location.protocol === 'file:';
  window.addEventListener('pageshow', function () { d.querySelectorAll('.wv-form__submit[disabled]').forEach(function (b) { b.disabled = false; b.textContent = b.getAttribute('data-label') || b.textContent; }); });
  d.querySelectorAll('form.wv-form').forEach(function (form) {
    if (isPreview) {
      var note = d.createElement('p');
      note.className = 'form-preview-note';
      note.textContent = 'プレビュー環境です。送信ボタンを押しても実際には送信されず、完了画面の確認のみ行えます（公開時は Netlify Forms で院内のメールアドレスへ届きます）。';
      form.parentNode.insertBefore(note, form);
    }
    var errBox = form.querySelector('.wv-form__error');
    form.addEventListener('submit', function (e) {
      form.classList.remove('has-error');
      form.querySelectorAll('.is-invalid').forEach(function (el) { el.classList.remove('is-invalid'); });
      form.querySelectorAll('.wv-form__fielderror').forEach(function (el) { el.remove(); });
      form.querySelectorAll('[data-either-missing]').forEach(function (el) { el.removeAttribute('data-either-missing'); });
      form.querySelectorAll('[aria-invalid]').forEach(function (el) { el.removeAttribute('aria-invalid'); el.removeAttribute('aria-describedby'); });
      var bad = [];
      form.querySelectorAll('[required]').forEach(function (el) {
        var ok;
        if (el.type === 'checkbox') ok = el.checked;
        else if (el.type === 'radio') ok = !!form.querySelector('input[type="radio"][name="' + el.name + '"]:checked');
        else ok = el.value.trim() !== '';
        if (ok && el.type === 'email') ok = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(el.value.trim());
        if (ok && el.type === 'tel') ok = /^[0-9０-９()（）\-－ー\s+]{8,}$/.test(el.value.trim());
        if (!ok) bad.push(el);
      });
      var groups = {};
      form.querySelectorAll('[data-require-one]').forEach(function (el) { (groups[el.getAttribute('data-require-one')] = groups[el.getAttribute('data-require-one')] || []).push(el); });
      Object.keys(groups).forEach(function (g) {
        var els = groups[g], filled = els.filter(function (el) { return el.value.trim() !== ''; });
        if (!filled.length) { bad.push(els[0]); els[0].setAttribute('data-either-missing', '1'); }
        filled.forEach(function (el) {
          var ok = el.type === 'email' ? /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(el.value.trim()) : /^[0-9０-９()（）\-－ー\s+]{8,}$/.test(el.value.trim());
          if (!ok) bad.push(el);
        });
      });
      if (bad.length) {
        e.preventDefault();
        form.classList.add('has-error');
        var seen = {};
        bad.forEach(function (el) {
          if (el.type === 'radio') { if (seen[el.name]) return; seen[el.name] = true; }
          var group = el.type === 'radio' ? el.closest('.wv-form__choices') : el;
          if (group) group.classList.add('is-invalid');
          var m = d.createElement('span'); m.className = 'wv-form__fielderror';
          m.id = 'err-' + (el.id || el.name).replace(/[^\w\u3040-\u9fff-]/g, '');
          el.setAttribute('aria-invalid', 'true'); el.setAttribute('aria-describedby', m.id);
          m.textContent = el.getAttribute('data-either-missing') ? 'お電話番号かメールアドレスのどちらかをご入力ください。' : el.type === 'checkbox' ? '確認のチェックを入れてください。' : el.type === 'radio' ? 'いずれかを選んでください。' : (el.type === 'email' ? 'メールアドレスの形式をご確認ください。' : (el.type === 'tel' ? '電話番号の形式をご確認ください。' : '必須項目です。'));
          (el.closest('.wv-form__field') || el.parentNode).appendChild(m);
        });
        if (errBox) { errBox.textContent = '入力内容に不足があります。赤字の項目をご確認ください。'; }
        bad[0].focus();
        return;
      }
      var btn = form.querySelector('.wv-form__submit');
      if (btn) { btn.setAttribute('data-label', btn.textContent); btn.disabled = true; btn.textContent = '送信中…'; }
      if (isPreview) { e.preventDefault(); location.href = form.getAttribute('action') || '/thanks/'; }
    });
  });
})();
