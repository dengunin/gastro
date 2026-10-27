(function () {
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var root = document.documentElement;

  /* тема */
  $('#theme-btn').addEventListener('click', function () {
    var t = root.dataset.theme === 'dark' ? 'light' : 'dark';
    root.dataset.theme = t;
    try { localStorage.setItem('theme', t); } catch (e) {}
    var lb = $('#lightbox');
    if (lb && !lb.hidden) openViewer(viewerBtn);   // картинка в просмотре должна сменить версию
  });

  /* полоса прогресса чтения */
  var bar = $('#progress');
  function onScroll() {
    var h = document.documentElement.scrollHeight - innerHeight;
    bar.style.width = (h > 0 ? Math.min(100, scrollY / h * 100) : 0) + '%';
  }
  addEventListener('scroll', onScroll, { passive: true }); onScroll();

  /* Делегирование сохраняется при замене материала. */
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-fold]');
    if (b) { var open = b.dataset.fold === 'open'; $$('.sec > details').forEach(function (d) { d.open = open; }); }
    if (e.target.closest('#print-btn')) window.print();
  });
  var hashTimer;
  function openForHash() {
    clearTimeout(hashTimer);
    if (!location.hash) return;
    var el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (!el) return;
    var d = el.closest('details');
    while (d) { d.open = true; d = d.parentElement && d.parentElement.closest('details'); }
    hashTimer = setTimeout(function () { if (el.isConnected) el.scrollIntoView(); }, 30);
  }
  addEventListener('hashchange', openForHash); openForHash();

  /* левое меню: на телефоне — выезжающая панель; под активным разделом — его навигация со слежением за прокруткой */
  var side = $('#side'), scrim = $('#side-scrim');
  function openSide() { side.classList.add('open'); scrim.classList.add('on'); }
  function closeSide() { side.classList.remove('open'); scrim.classList.remove('on'); }
  var mb = $('#menu-btn'); if (mb) mb.addEventListener('click', openSide);
  var mf = $('#menu-fab');
  if (mf) mf.addEventListener('click', function () { openSide(); var c = $('.side-sub a.is-current', side); if (c) c.scrollIntoView({ block: 'center' }); });
  scrim.addEventListener('click', closeSide);
  $('.side-close', side).addEventListener('click', closeSide);
  side.addEventListener('click', function (e) {
    var a = e.target.closest('.side-sub a');
    if (!a) return;
    var d = document.getElementById(new URL(a.href).hash.slice(1));
    var det = d && d.closest('details'); if (det) det.open = true;
    closeSide();
  });
  /* просмотр схемы: масштаб колесом, щипком и кнопками; перемещение перетаскиванием */
  var lb = $('#lightbox'), stage = $('#lb-stage'), vimg = $('img', stage);
  var vs = { s: 1, tx: 0, ty: 0, fit: 1, w: 0, h: 0 };
  var viewerBtn = null;
  function apply() { vimg.style.transform = 'translate(' + vs.tx + 'px,' + vs.ty + 'px) scale(' + vs.s + ')'; }
  function clamp() {
    var r = stage.getBoundingClientRect(), iw = vs.w * vs.s, ih = vs.h * vs.s;
    vs.tx = iw <= r.width ? (r.width - iw) / 2 : Math.min(0, Math.max(r.width - iw, vs.tx));
    vs.ty = ih <= r.height ? (r.height - ih) / 2 : Math.min(0, Math.max(r.height - ih, vs.ty));
  }
  function fitView() {
    var r = stage.getBoundingClientRect();
    vs.w = vimg.naturalWidth; vs.h = vimg.naturalHeight;
    if (!vs.w) return;
    vs.fit = Math.min(r.width / vs.w, r.height / vs.h);
    vs.s = vs.fit; vs.tx = 0; vs.ty = 0; clamp(); apply();
  }
  function zoomAt(f, cx, cy) {
    var ns = Math.max(vs.fit, Math.min(vs.fit * 8, vs.s * f)), k = ns / vs.s;
    vs.tx = cx - (cx - vs.tx) * k; vs.ty = cy - (cy - vs.ty) * k; vs.s = ns; clamp(); apply();
  }
  function openViewer(btn) {
    if (!btn) return;
    viewerBtn = btn;
    var dark = root.dataset.theme === 'dark';
    var src = dark ? btn.dataset.fullDark : btn.dataset.fullLight;
    lb.hidden = false;
    document.body.style.overflow = 'hidden';
    vimg.onload = fitView;
    vimg.src = src;
    if (vimg.complete) fitView();
  }
  function closeViewer() { lb.hidden = true; document.body.style.overflow = ''; }
  document.addEventListener('click', function (e) {
    var b = e.target.closest('.fig-btn');
    if (b) { openViewer(b); return; }
    if (e.target.closest('.lb-close')) { closeViewer(); return; }
    var z = e.target.closest('[data-z]');
    if (z) {
      var r = stage.getBoundingClientRect();
      if (z.dataset.z === 'reset') fitView();
      else zoomAt(z.dataset.z === 'in' ? 1.4 : 1 / 1.4, r.width / 2, r.height / 2);
    }
  });
  var ptr = {}, drag = null, pinch = null;
  stage.addEventListener('pointerdown', function (e) {
    stage.setPointerCapture(e.pointerId);
    ptr[e.pointerId] = { x: e.clientX, y: e.clientY };
    var ids = Object.keys(ptr);
    if (ids.length === 1) { drag = { x: e.clientX, y: e.clientY, tx: vs.tx, ty: vs.ty }; stage.classList.add('dragging'); }
    if (ids.length === 2) {
      var a = ptr[ids[0]], b = ptr[ids[1]];
      pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), s: vs.s }; drag = null;
    }
  });
  stage.addEventListener('pointermove', function (e) {
    if (!ptr[e.pointerId]) return;
    ptr[e.pointerId] = { x: e.clientX, y: e.clientY };
    var ids = Object.keys(ptr);
    if (ids.length === 2 && pinch) {
      var a = ptr[ids[0]], b = ptr[ids[1]], r = stage.getBoundingClientRect();
      var d = Math.hypot(a.x - b.x, a.y - b.y);
      zoomAt((pinch.s * d / pinch.d) / vs.s, (a.x + b.x) / 2 - r.left, (a.y + b.y) / 2 - r.top);
    } else if (drag) {
      vs.tx = drag.tx + e.clientX - drag.x; vs.ty = drag.ty + e.clientY - drag.y; clamp(); apply();
    }
  });
  function endPtr(e) {
    delete ptr[e.pointerId];
    if (!Object.keys(ptr).length) { drag = null; pinch = null; stage.classList.remove('dragging'); }
    else if (Object.keys(ptr).length === 1) { var k = Object.keys(ptr)[0]; drag = { x: ptr[k].x, y: ptr[k].y, tx: vs.tx, ty: vs.ty }; pinch = null; }
  }
  stage.addEventListener('pointerup', endPtr);
  stage.addEventListener('pointercancel', endPtr);
  stage.addEventListener('wheel', function (e) {
    e.preventDefault();
    var r = stage.getBoundingClientRect();
    zoomAt(e.deltaY < 0 ? 1.2 : 1 / 1.2, e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });
  stage.addEventListener('dblclick', function (e) {
    var r = stage.getBoundingClientRect();
    if (vs.s > vs.fit * 1.05) fitView(); else zoomAt(2.5, e.clientX - r.left, e.clientY - r.top);
  });
  addEventListener('resize', function () { if (!lb.hidden) fitView(); });

  /* печать: раскрыть сокращения и свёрнутые блоки, чтобы они попали на бумагу */
  addEventListener('beforeprint', function () {
    $$('details').forEach(function (d) { if (!d.open) { d.dataset.wasClosed = '1'; d.open = true; } });
  });
  addEventListener('afterprint', function () {
    $$('details[data-was-closed]').forEach(function (d) { d.open = false; delete d.dataset.wasClosed; });
  });

  /* поиск */
  var modal = $('#search-modal'), input = $('#search-input'), results = $('#search-results');
  var loaded = false, sel = -1;
  function esc(s) { return s.replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function loadIndex(cb) {
    if (loaded || window.SEARCH_INDEX) { loaded = true; return cb(); }
    var s = document.createElement('script'); s.src = document.body.dataset.searchSrc || 'assets/search.js'; s.onload = function () { loaded = true; cb(); };
    document.head.appendChild(s);
  }
  function openSearch() { modal.hidden = false; input.value = ''; results.innerHTML = '<div class="search-empty">Введите слово: название шкалы, препарата, метода…</div>'; input.focus(); loadIndex(function () {}); }
  function closeSearch() { modal.hidden = true; }
  function run() {
    var q = input.value.trim().toLowerCase();
    if (q.length < 2) { results.innerHTML = '<div class="search-empty">Введите минимум 2 символа.</div>'; return; }
    var words = q.split(/\s+/);
    var hits = [];
    (window.SEARCH_INDEX || []).forEach(function (e) {
      var t = (e.t + ' ' + e.x).toLowerCase(), ok = true, score = 0;
      words.forEach(function (w) { var i = t.indexOf(w); if (i < 0) ok = false; else score += (e.t.toLowerCase().indexOf(w) >= 0 ? 5 : 1); });
      if (ok) hits.push({ e: e, s: score, p: t.indexOf(words[0]) });
    });
    hits.sort(function (a, b) { return b.s - a.s; });
    if (!hits.length) { results.innerHTML = '<div class="search-empty">Ничего не найдено. Попробуйте корень слова: «эластаз», «колоноскоп».</div>'; return; }
    results.innerHTML = hits.slice(0, 30).map(function (h) {
      var e = h.e, txt = e.x, i = txt.toLowerCase().indexOf(words[0]);
      var sn = i < 0 ? txt.slice(0, 140) : (i > 50 ? '…' : '') + txt.slice(Math.max(0, i - 50), i + 110);
      sn = esc(sn);
      words.forEach(function (w) { sn = sn.replace(new RegExp('(' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig'), '<em>$1</em>'); });
      return '<a class="sr" href="' + e.p + (e.a ? '#' + e.a : '') + '"><span class="sr-tag">' + e.l + '</span><b>' + esc(e.t) + '</b><small>' + sn + '</small></a>';
    }).join('');
    sel = -1;
  }
  $('#search-btn').addEventListener('click', openSearch);
  input.addEventListener('input', function () { loadIndex(run); });
  modal.addEventListener('click', function (e) { if (e.target === modal) closeSearch(); });
  results.addEventListener('click', function (e) { var a = e.target.closest('a'); if (a) closeSearch(); });
  addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); openSearch(); }
    else if (e.key === 'Escape') { closeSearch(); closeViewer(); closeSide(); }
    else if (!lb.hidden && (e.key === '+' || e.key === '=' || e.key === '-' || e.key === '0')) {
      var r = stage.getBoundingClientRect();
      if (e.key === '0') fitView(); else zoomAt(e.key === '-' ? 1 / 1.3 : 1.3, r.width / 2, r.height / 2);
    }
    else if (!lb.hidden && e.key.indexOf('Arrow') === 0) {
      var st = 60; if (e.key === 'ArrowLeft') vs.tx += st; if (e.key === 'ArrowRight') vs.tx -= st;
      if (e.key === 'ArrowUp') vs.ty += st; if (e.key === 'ArrowDown') vs.ty -= st; clamp(); apply(); e.preventDefault();
    }
    else if (!modal.hidden && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      var items = $$('.sr', results); if (!items.length) return; e.preventDefault();
      sel = (sel + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      items.forEach(function (x, i) { x.classList.toggle('sel', i === sel); }); items[sel].scrollIntoView({ block: 'nearest' });
    } else if (!modal.hidden && e.key === 'Enter') { var s = $('.sr.sel', results) || $('.sr', results); if (s) s.click(); }
  });
  var pageEvents;
  function mountPage() {
    if (pageEvents) pageEvents.abort();
    pageEvents = new AbortController();
    var subs = {};
    $$('.side-item.is-active .side-sub a', side).forEach(function (a) { subs[new URL(a.href).hash.slice(1)] = a; });
    var heads = Object.keys(subs).map(function (id) { return document.getElementById(id); }).filter(Boolean);
    if (heads.length) {
      // Список в меню не меняет высоту при прокрутке; внизу страницы текущим считается последний раздел;
      // меню подкручивается только если пункт вышел из видимости.
      var current = null;
      var spy = function () {
        var visibleHeads = heads.filter(function (h) { return h.getClientRects().length; });
        if (!visibleHeads.length) return;
        var found = null;
        var atBottom = innerHeight + scrollY >= document.documentElement.scrollHeight - 4;
        if (atBottom) found = visibleHeads[visibleHeads.length - 1];
        else visibleHeads.forEach(function (h) { if (h.getBoundingClientRect().top <= 140) found = h; });
        if (!found) found = visibleHeads[0];
        if (found === current) return;
        current = found;
        $$('.is-current', side).forEach(function (a) { a.classList.remove('is-current'); });
        var a = subs[found.id];
        a.classList.add('is-current');
        if (innerWidth > 1100) {
          var r = a.getBoundingClientRect(), tr = side.getBoundingClientRect();
          if (r.top < tr.top + 40) side.scrollTop -= tr.top + 40 - r.top;
          else if (r.bottom > tr.bottom - 20) side.scrollTop += r.bottom - tr.bottom + 20;
        }
      };
      addEventListener('scroll', spy, { passive: true, signal: pageEvents.signal }); addEventListener('resize', spy, { signal: pageEvents.signal }); spy();
    }

    /* клинические задачи: список слева, выбранный случай справа; шаги открываются по мере прохождения */
    var cl = $('.cases-layout');
    if (cl) {
      cl.classList.add('cases-on');
      var cases = $$('.case', cl), clinks = $$('.cases-list a', cl);
      var showCase = function () {
        var id = decodeURIComponent((location.hash || '').slice(1));
        var c = cases.filter(function (x) { return x.id === id; })[0] || cases[0];
        cases.forEach(function (x) { x.classList.toggle('active', x === c); });
        clinks.forEach(function (a) { a.classList.toggle('on', a.getAttribute('href') === '#' + c.id); });
        if (heads.length) spy();
      };
      addEventListener('hashchange', showCase, { signal: pageEvents.signal }); showCase();
      var showPane = function (c, k) {
        $$('.pane', c).forEach(function (p) { p.classList.toggle('on', +p.dataset.pane === k); });
        $$('.cs', c).forEach(function (b) { b.classList.toggle('on', +b.dataset.go === k); });
        var top = c.getBoundingClientRect().top + scrollY - 90;
        if (scrollY > top) scrollTo({ top: top, behavior: 'smooth' });
      };
      var unlock = function (c, k) { var b = $('.cs[data-go="' + k + '"]', c); if (b) b.classList.remove('locked'); };
      cl.addEventListener('click', function (e) {
        var c = e.target.closest('.case'); if (!c) return;
        var go = e.target.closest('[data-go]');
        if (go) {
          if (go.classList.contains('locked')) return;
          var k = +go.dataset.go;
          if (go.classList.contains('go-next')) unlock(c, k);
          showPane(c, k); return;
        }
        if (e.target.closest('.reveal')) {
          var pane = e.target.closest('.pane');
          $('.answer', pane).hidden = false; $('.reveal-row', pane).hidden = true;
          unlock(c, +pane.dataset.pane + 1);
          return;
        }
        if (e.target.closest('.restart')) {
          $$('.answer', c).forEach(function (a) { a.hidden = true; });
          $$('.reveal-row', c).forEach(function (r) { r.hidden = false; });
          $$('textarea', c).forEach(function (t) { t.value = ''; });
          $$('.cs', c).forEach(function (b, i) { b.classList.toggle('locked', i > 0); });
          showPane(c, 1);
        }
      });
    }

    /* фильтры по статусу на странице источников */
    $$('[data-filter]').forEach(function (box) {
      var sel = box.dataset.filter;
      $$('[data-st]', box).forEach(function (b) {
        b.addEventListener('click', function () {
          $$('.chip', box).forEach(function (c) { c.classList.toggle('on', c === b); });
          $$(sel).forEach(function (el) { el.hidden = b.dataset.st !== 'all' && el.dataset.st !== b.dataset.st; });
        });
      });
    });

    openForHash(); onScroll();
  }
  window.SitePage = {
    mount: mountPage,
    dispose: function () {
      clearTimeout(hashTimer);
      if (pageEvents) pageEvents.abort();
      closeSearch(); closeViewer(); closeSide();
      if (window.SiteQuiz) window.SiteQuiz.unmount();
    }
  };
  mountPage();
})();
