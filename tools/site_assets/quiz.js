/* Тест: банк вопросов, в каждую попытку берутся PER случайных; один вопрос на экране, справа — навигация.
   Номера вопросов в попытке всегда идут с 1 (это позиция в попытке, а не номер в банке).
   Ход попытки хранится в sessionStorage, история и список ошибок — в localStorage (id вопросов банка). */
(function () {
  var cleanup = function () {};
  function mount() {
  cleanup();
  if (!document.getElementById('quiz-data')) return;
  var events = new AbortController();

  var data = JSON.parse(document.getElementById('quiz-data').textContent);
  var Q = data.questions, PER = data.perSession || 20, KEY = 'quiz-' + data.topic;
  var HK = KEY + '-hist', WK = KEY + '-wrong', SK = KEY + '-session', PK = KEY + '-pref', OFF = KEY + '-offset';
  var EXAM_SEC = 10 * 60;
  var byN = {};
  Q.forEach(function (q) { byN[q.n] = q; });

  function lget(k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function lset(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  function sget() { try { return JSON.parse(sessionStorage.getItem(SK) || 'null'); } catch (e) { return null; } }
  function sset(s) { try { if (s) sessionStorage.setItem(SK, JSON.stringify(s)); else sessionStorage.removeItem(SK); } catch (e) {} }
  function $(id) { return document.getElementById(id); }
  function shuffle(a) {
    a = a.slice();
    for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  }
  function fmt(sec) { sec = Math.max(0, Math.round(sec)); return Math.floor(sec / 60) + ':' + ('0' + (sec % 60)).slice(-2); }
  function plural(n, one, few, many) {
    var m = n % 100, d = n % 10;
    return n + ' ' + (m > 10 && m < 20 ? many : d === 1 ? one : d >= 2 && d <= 4 ? few : many);
  }

  var MODE_NAME = { learn: 'Обучение', exam: 'Экзамен', errors: 'Повтор ошибок' };
  var MODE_HINT = {
    learn: 'Ответ и разбор — после проверки',
    exam: 'Без подсказок, таймер 10 минут; разбор — после завершения',
    errors: 'Вопросы, на которые вы ошибались; верный ответ убирает вопрос из списка'
  };
  var S = sget();
  var timer = null;
  var pref = lget(PK, { shuffle: true });

  function wrongList() { return lget(WK, []).filter(function (n) { return byN[n]; }); }
  function isFinal(n) { return S.done || (S.mode === 'exam' ? false : !!S.checked[n]); }
  function isGood(n) { return S.ans[n] !== undefined && S.ans[n] === byN[n].a; }

  /* ---------- новая попытка: тасуется весь банк, берутся PER вопросов ---------- */
  function draw(mode) {
    if (mode === 'errors') return shuffle(wrongList()).slice(0, PER);
    var all = Q.map(function (q) { return q.n; }).sort(function (a, b) { return a - b; });
    if (pref.shuffle) return shuffle(all).slice(0, PER);
    var off = (lget(OFF, 0) || 0) % all.length, out = [];     // без перемешивания — по порядку банка, с места, где остановились
    for (var i = 0; i < Math.min(PER, all.length); i++) out.push(all[(off + i) % all.length]);
    lset(OFF, (off + PER) % all.length);
    return out;
  }

  function startSession(mode) {
    var ids = draw(mode);
    if (!ids.length) { S = null; sset(null); render(); return; }
    var perm = {};
    ids.forEach(function (n) { perm[n] = pref.shuffle ? shuffle([0, 1, 2, 3]) : [0, 1, 2, 3]; });
    S = { mode: mode, ids: ids, perm: perm, ans: {}, checked: {}, cur: 0, t0: Date.now(), done: false, saved: false };
    sset(S);
    render();
  }

  /* ---------- подсчёт и завершение ---------- */
  function stats() {
    var done = 0, ok = 0, wrong = [];
    S.ids.forEach(function (n) {
      if (S.ans[n] !== undefined) { done++; if (isGood(n)) ok++; else wrong.push(n); } else if (S.done) wrong.push(n);
    });
    return { done: done, ok: ok, wrong: wrong, total: S.ids.length };
  }
  function secLeft() { return EXAM_SEC - (Date.now() - S.t0) / 1000; }

  function finish() {
    if (!S || S.done) return;
    S.done = true;
    S.secs = Math.min(Math.round((Date.now() - S.t0) / 1000), S.mode === 'exam' ? EXAM_SEC : 1e9);
    var st = stats(), wl = lget(WK, []);
    S.ids.forEach(function (n) {
      var i = wl.indexOf(n);
      if (!isGood(n) && i < 0) wl.push(n);
      if (isGood(n) && S.mode === 'errors' && i >= 0) wl.splice(i, 1);
    });
    lset(WK, wl);
    if (!S.saved) {
      var h = lget(HK, []);
      h.push({ ts: Date.now(), mode: S.mode, ok: st.ok, total: st.total, secs: S.secs, wrong: st.wrong });
      lset(HK, h.slice(-50));
      S.saved = true;
    }
    S.cur = 0;
    sset(S);
    clearInterval(timer);
    render();
    window.scrollTo(0, 0);
  }

  /* ---------- отрисовка ---------- */
  function renderTop() {
    var w = wrongList().length, cur = S ? S.mode : 'learn';
    $('qz-mode').innerHTML =
      '<button type="button" data-mode="learn" class="' + (cur === 'learn' ? 'on' : '') + '">Обучение</button>' +
      '<button type="button" data-mode="exam" class="' + (cur === 'exam' ? 'on' : '') + '">Экзамен</button>' +
      '<button type="button" data-mode="errors" class="' + (cur === 'errors' ? 'on' : '') + '"' + (w || cur === 'errors' ? '' : ' disabled') +
      ' title="' + (w ? 'Вопросов с ошибками: ' + w : 'Появится после первой ошибки') + '">Ошибки <small>' + w + '</small></button>';
    $('qz-hint').textContent = MODE_HINT[cur];
    $('qz-shuf').checked = !!pref.shuffle;
  }

  function renderCard() {
    var el = $('qz-card');
    if (!S) { el.innerHTML = '<p class="hist-empty">В этом режиме пока нет вопросов. Пройдите обычный тест — ошибки появятся здесь.</p>'; return; }
    var n = S.ids[S.cur], q = byN[n], perm = S.perm[n], ans = S.ans[n], total = S.ids.length;
    var learn = S.mode !== 'exam';
    var reveal = S.done || (learn && S.checked[n]);
    var locked = S.done || (learn && S.checked[n]);
    var st = stats();
    var h = '<div class="qz-meta"><span class="qz-no">Вопрос ' + (S.cur + 1) + ' из ' + total + '</span>' + (q.cat ? '<span>' + q.cat + '</span>' : '') + '</div>' +
      '<div class="qz-bar"><i style="width:' + (st.done / total * 100) + '%"></i></div><p class="qz-q">' + q.q + '</p><div class="qz-opts">';
    perm.forEach(function (orig) {
      var cls = 'qz-opt';
      if (reveal) cls += orig === q.a ? ' right' : (orig === ans ? ' wrong' : ' dim');
      else if (ans === orig) cls += ' picked';
      h += '<button type="button" class="' + cls + '" data-i="' + orig + '"' + (locked ? ' disabled' : '') + '><span class="r"></span><span>' + q.opts[orig] + '</span></button>';
    });
    h += '</div>';
    var lastExam = !learn && !S.done && S.cur === total - 1;
    h += '<div class="qz-act">';
    if (S.done) {
      h += '<button type="button" class="btn btn-primary" id="qz-prev">← Назад</button><button type="button" class="btn btn-primary" id="qz-next">Дальше →</button>';
    } else if (learn && locked) {
      h += '<button type="button" class="btn btn-primary" id="qz-next">Дальше <span aria-hidden="true">→</span></button>';
    } else if (learn) {
      h += '<button type="button" class="btn btn-primary" id="qz-check"' + (ans === undefined ? ' disabled' : '') + '>Проверить ответ <span aria-hidden="true">→</span></button>' +
        '<button type="button" class="link-btn" id="qz-skip">Пропустить</button>';
    } else {
      h += '<button type="button" class="btn btn-primary" id="qz-save"' + (ans === undefined && !lastExam ? ' disabled' : '') + '>' +
        (lastExam ? 'Завершить попытку' : 'Сохранить и дальше') + ' <span aria-hidden="true">→</span></button>' +
        (lastExam ? '' : '<button type="button" class="link-btn" id="qz-skip">Пропустить</button>');
    }
    h += '</div>';
    if (reveal) {
      var good = ans === q.a, right = q.opts[q.a];
      var verdict = ans === undefined ? 'Ответа нет. Верно: ' + right : (good ? 'Верно' : 'Неверно. Верно: ' + right);
      h += '<div class="q-expl ' + (good ? 'good' : 'bad') + '"><span class="q-verdict">' + verdict + '</span>' + q.e + '</div>';
    }
    el.innerHTML = h;
  }

  function renderNav() {
    var nums = $('qz-nums'), saved = $('qz-saved');
    if (!S) { nums.innerHTML = ''; saved.textContent = ''; return; }
    var h = '';
    S.ids.forEach(function (n, i) {
      var cls = '';
      if (S.done || (S.mode !== 'exam' && S.checked[n])) cls = S.ans[n] === undefined ? 'wrong' : (isGood(n) ? 'right' : 'wrong');
      else if (S.ans[n] !== undefined) cls = 'ans';
      if (i === S.cur) cls += ' cur';
      h += '<button type="button" data-i="' + i + '" class="' + cls + '" aria-label="Вопрос ' + (i + 1) + '">' + (i + 1) + '</button>';
    });
    nums.innerHTML = h;
    var st = stats();
    saved.textContent = S.done ? 'Попытка завершена' : (st.done ? (plural(st.done, 'ответ сохранён', 'ответа сохранено', 'ответов сохранено')) : 'Ответов пока нет');
    $('qz-finish').hidden = S.done;
    $('qz-note').textContent = S.done ? 'Нажимайте на номера, чтобы посмотреть разбор каждого вопроса.' :
      (S.mode === 'exam' ? 'В режиме экзамена разбор появится после завершения всей попытки.' : 'Разбор открывается после проверки каждого ответа.');
    var t = $('qz-timer');
    t.hidden = !(S.mode === 'exam' && !S.done);
    t.textContent = fmt(secLeft());
  }

  function renderResult() {
    var res = $('qz-result');
    if (!S || !S.done) { res.hidden = true; res.innerHTML = ''; return; }
    var st = stats(), pct = Math.round(st.ok / st.total * 100);
    res.hidden = false;
    res.className = 'qz-result';
    var wrongTxt = st.wrong.length
      ? '<p>Ошибки: ' + S.ids.map(function (n, i) { return st.wrong.indexOf(n) >= 0 ? '<a href="#" data-go="' + i + '">№' + (i + 1) + '</a>' : ''; }).filter(Boolean).join(', ') + '. Они добавлены в «Повтор ошибок».</p>'
      : '<p>Ошибок нет.</p>';
    res.innerHTML = '<div class="big">' + st.ok + ' / ' + st.total + '</div><p><b>' + pct + '%</b> · ' + MODE_NAME[S.mode].toLowerCase() + ' · ' + fmt(S.secs || 0) + '</p>' +
      '<p>' + (pct >= 70 ? 'Порог аккредитационного тестирования (70%) пройден.' : 'Ниже порога 70%: вернитесь к шпаргалке и к разделам, указанным в пояснениях.') + '</p>' + wrongTxt +
      '<div class="res-actions"><button type="button" class="btn btn-primary" id="again-err"' + (wrongList().length ? '' : ' disabled') + '>Повторить ошибки</button>' +
      '<button type="button" class="btn" id="again-all">Новая попытка</button></div>';
  }

  function renderHist() {
    var h = lget(HK, []), el = $('quiz-hist');
    var html = '<h2>История результатов</h2>';
    if (!h.length) { el.innerHTML = html + '<p class="hist-empty">Пока пусто: результаты появятся после первой завершённой попытки. История хранится только в этом браузере.</p>'; return; }
    var last = h.slice(-12);
    var best = Math.max.apply(null, h.map(function (x) { return Math.round(x.ok / x.total * 100); }));
    var avg = Math.round(h.reduce(function (s, x) { return s + x.ok / x.total * 100; }, 0) / h.length);
    html += '<div class="hist-sum"><span>Попыток: <b>' + h.length + '</b></span><span>Лучший: <b>' + best + '%</b></span><span>Средний: <b>' + avg + '%</b></span></div>';
    html += '<div class="hist-bars" aria-hidden="true">' + last.map(function (x) {
      var p = Math.round(x.ok / x.total * 100);
      return '<i class="' + (x.mode === 'exam' ? 'exam ' : '') + (p < 70 ? 'low' : '') + '" style="height:' + Math.max(6, p) + '%" title="' + p + '%"></i>';
    }).join('') + '</div>';
    html += '<div class="tbl"><table><thead><tr><th>Дата</th><th>Режим</th><th>Результат</th><th>Время</th><th>Ошибок</th></tr></thead><tbody>' +
      last.slice().reverse().map(function (x) {
        var d = new Date(x.ts);
        var ds = ('0' + d.getDate()).slice(-2) + '.' + ('0' + (d.getMonth() + 1)).slice(-2) + '.' + d.getFullYear() + ' ' + ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
        return '<tr><td>' + ds + '</td><td>' + MODE_NAME[x.mode] + '</td><td>' + x.ok + ' / ' + x.total + ' (' + Math.round(x.ok / x.total * 100) + '%)</td><td>' + fmt(x.secs || 0) + '</td><td>' + (x.wrong.length || '—') + '</td></tr>';
      }).join('') + '</tbody></table></div>';
    html += '<div class="hist-actions"><button type="button" class="btn btn-sm" id="hist-clear">Очистить историю и список ошибок</button></div>';
    el.innerHTML = html;
    $('hist-clear').onclick = function () {
      if (!confirm('Удалить историю результатов и список ошибок в этом браузере?')) return;
      lset(HK, []); lset(WK, []); render();
    };
  }

  function render() {
    renderTop(); renderCard(); renderNav(); renderResult(); renderHist();
    clearInterval(timer);
    if (S && S.mode === 'exam' && !S.done) {
      if (secLeft() <= 0) { finish(); return; }
      timer = setInterval(function () {
        var t = secLeft(), el = $('qz-timer');
        if (el) { el.textContent = fmt(t); el.classList.toggle('low', t < 120); }
        if (t <= 0) finish();
      }, 1000);
    }
  }

  /* ---------- действия ---------- */
  function go(i) { S.cur = Math.max(0, Math.min(S.ids.length - 1, i)); sset(S); render(); }
  function advance() {
    var total = S.ids.length;
    if (S.done) return go((S.cur + 1) % total);
    if (S.mode === 'exam') return go(S.cur + 1);
    for (var k = 1; k <= total; k++) {               // обучение: к следующему вопросу, на который ещё не дан проверенный ответ
      var j = (S.cur + k) % total;
      if (!S.checked[S.ids[j]]) return go(j);
    }
    finish();
  }
  function check() {
    var n = S.ids[S.cur];
    if (S.ans[n] === undefined) return;
    S.checked[n] = true;
    var wl = lget(WK, []), k = wl.indexOf(n);
    if (!isGood(n) && k < 0) wl.push(n);
    if (isGood(n) && S.mode === 'errors' && k >= 0) wl.splice(k, 1);
    lset(WK, wl);
    sset(S);
    render();
    if (S.ids.every(function (m) { return S.checked[m]; })) { var b = $('qz-next'); if (b) b.innerHTML = 'Завершить попытку <span aria-hidden="true">→</span>'; }
  }
  function begin(mode) {
    if (S && !S.done && stats().done && !confirm('Начать новую попытку? Ответы текущей не сохранятся в истории.')) return;
    startSession(mode);
  }

  $('qz-mode').addEventListener('click', function (e) {
    var b = e.target.closest('button');
    if (b && !b.disabled && b.dataset.mode !== (S && S.mode)) begin(b.dataset.mode);
  });
  $('qz-shuf').addEventListener('change', function () { pref.shuffle = this.checked; lset(PK, pref); });
  $('qz-new').addEventListener('click', function () { begin(S && S.mode ? S.mode : 'learn'); });
  $('qz-finish').addEventListener('click', function () {
    var left = S.ids.length - stats().done;
    if (left && !confirm('Без ответа осталось вопросов: ' + left + '. Завершить попытку?')) return;
    finish();
  });
  $('qz-nums').addEventListener('click', function (e) {
    var b = e.target.closest('button');
    if (b) go(+b.dataset.i);
  });
  $('qz-result').addEventListener('click', function (e) {
    var a = e.target.closest('[data-go]');
    if (a) { e.preventDefault(); go(+a.dataset.go); window.scrollTo(0, 0); return; }
    if (e.target.id === 'again-err') { S = null; sset(null); startSession('errors'); }
    if (e.target.id === 'again-all') { S = null; sset(null); startSession('learn'); }
  });
  $('qz-card').addEventListener('click', function (e) {
    var o = e.target.closest('.qz-opt');
    if (o && !o.disabled && S && !S.done) {
      S.ans[S.ids[S.cur]] = +o.dataset.i;
      sset(S);
      render();
      return;
    }
    var id = e.target.closest('button') && e.target.closest('button').id;
    if (id === 'qz-check') check();
    else if (id === 'qz-next') { if (e.target.closest('button').textContent.indexOf('Завершить') === 0) finish(); else advance(); }
    else if (id === 'qz-prev') go((S.cur - 1 + S.ids.length) % S.ids.length);
    else if (id === 'qz-skip') { if (S.mode === 'exam') go(S.cur + 1); else advance(); }
    else if (id === 'qz-save') { if (S.cur === S.ids.length - 1) $('qz-finish').click(); else go(S.cur + 1); }
  });
  document.addEventListener('keydown', function (e) {
    if (!S || e.target.closest('input,textarea') || e.ctrlKey || e.metaKey || e.altKey) return;
    if (/^[1-4]$/.test(e.key)) {
      var o = document.querySelectorAll('#qz-card .qz-opt')[+e.key - 1];
      if (o && !o.disabled) o.click();
    } else if (e.key === 'Enter') {
      var b = $('qz-check') || $('qz-save') || $('qz-next');
      if (b && !b.disabled && document.activeElement === document.body) b.click();
    }
  }, { signal: events.signal });

  /* ---------- старт ---------- */
  var requested = new URLSearchParams(location.search).get('mode');
  if (['learn', 'exam', 'errors'].indexOf(requested) >= 0 && (!S || S.mode !== requested)) {
    S = null; sset(null); startSession(requested);
  }
  if (S && S.ids && S.ids.some(function (n) { return !byN[n]; })) { S = null; sset(null); }   // банк изменился — прежняя попытка недействительна
  if (!S && requested !== 'errors') startSession('learn'); else if (S) render();
  cleanup = function () { clearInterval(timer); events.abort(); };
  }
  window.SiteQuiz = { mount: mount, unmount: function () { cleanup(); } };
  mount();
})();
