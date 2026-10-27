/* Persistent topic navigation. Header, sidebar, its links and mobile tabs retain DOM identity. */
(function () {
  'use strict';
  if (!document.body.dataset.topic || !/^https?:$/.test(location.protocol) || !window.fetch) return;
  var directory = new URL('.', location.href).pathname;
  var pages = ['index', 'short', 'full', 'card', 'test', 'cases', 'images', 'sources'];
  var main = document.getElementById('main');
  var side = document.getElementById('side');
  var cache = new Map();
  var request, revision = 0, renderedURL = new URL(location.href), quizLoading;
  cache.set(location.pathname, document.documentElement.outerHTML);
  history.scrollRestoration = 'manual';

  function savePosition() {
    history.replaceState(Object.assign({}, history.state, { topicPage: true, x: scrollX, y: scrollY }), '', location.href);
  }
  savePosition();

  function eligible(url) {
    return url.origin === location.origin && new URL('.', url).pathname === directory &&
      pages.indexOf(url.pathname.split('/').pop().replace(/\.html$/, '')) >= 0 && /\.html$/.test(url.pathname);
  }

  function quizReady(doc) {
    if (!doc.getElementById('quiz-data') || window.SiteQuiz) return Promise.resolve();
    if (!quizLoading) quizLoading = new Promise(function (resolve, reject) {
      var source = doc.querySelector('script[src*="/quiz.js"]');
      var script = document.createElement('script');
      script.src = new URL(source.getAttribute('src'), location.href).href;
      script.onload = resolve;
      script.onerror = function () { script.remove(); quizLoading = null; reject(new Error('Quiz unavailable')); };
      document.head.appendChild(script);
    });
    return quizLoading;
  }

  function updateMenu(page) {
    side.querySelectorAll('.side-item[data-page]').forEach(function (item) {
      var active = item.dataset.page === page;
      item.classList.toggle('is-active', active);
      var link = item.querySelector('.side-link');
      link.classList.toggle('is-on', active);
      if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
      var sub = item.querySelector('.side-sub');
      if (sub) sub.hidden = !active;
    });
    document.querySelectorAll('.tabbar a').forEach(function (link) {
      var active = link.getAttribute('href') === page + '.html';
      link.classList.toggle('is-active', active);
      if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
    });
    document.getElementById('menu-fab').hidden = !side.querySelector('.side-item.is-active .side-sub');
  }

  async function navigate(url, fromHistory, position) {
    var ticket = ++revision;
    if (request) request.abort();
    request = new AbortController();
    main.setAttribute('aria-busy', 'true');
    try {
      var source = cache.get(url.pathname);
      if (!source) {
        var response = await fetch(url.pathname, { signal: request.signal, cache: 'no-cache' });
        if (!response.ok) throw new Error('Page unavailable');
        source = await response.text();
        if (ticket !== revision) return;
        cache.set(url.pathname, source);
      }
      var doc = new DOMParser().parseFromString(source, 'text/html');
      var next = doc.getElementById('main');
      if (!next || doc.body.dataset.topic !== document.body.dataset.topic ||
          doc.querySelector('link[rel="stylesheet"]').getAttribute('href') !==
          document.querySelector('link[rel="stylesheet"]').getAttribute('href')) throw new Error('Different shell');
      await quizReady(doc);
      if (ticket !== revision) return;
      window.SitePage.dispose();
      if (!fromHistory) {
        savePosition();
        history.pushState({ topicPage: true, x: 0, y: 0 }, '', url.href);
      }
      var quizData = doc.getElementById('quiz-data');
      if (quizData && !next.contains(quizData)) next.appendChild(quizData);
      var oldQuizData = document.getElementById('quiz-data');
      if (oldQuizData) oldQuizData.remove();
      // Moving only main children is deliberate: sidebar DOM is never replaced.
      main.replaceChildren.apply(main, Array.from(next.childNodes));
      document.body.className = doc.body.className;
      document.body.dataset.page = doc.body.dataset.page;
      document.title = doc.title;
      document.querySelector('meta[name="description"]').content = doc.querySelector('meta[name="description"]').content;
      updateMenu(doc.body.dataset.page);
      renderedURL = new URL(url.href);
      window.SitePage.mount();
      if (quizData) window.SiteQuiz.mount();
      main.setAttribute('tabindex', '-1');
      main.focus({ preventScroll: true });
      if (position) requestAnimationFrame(function () { if (ticket === revision) scrollTo({ left: position.x || 0, top: position.y || 0, behavior: 'instant' }); });
      else if (!url.hash) scrollTo({ left: 0, top: 0, behavior: 'instant' });
      document.dispatchEvent(new CustomEvent('site:navigated', { detail: { page: doc.body.dataset.page } }));
    } catch (error) {
      if (ticket === revision && error.name !== 'AbortError') location.assign(url.href);
    } finally {
      if (ticket === revision) main.removeAttribute('aria-busy');
    }
  }

  document.addEventListener('click', function (event) {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    var link = event.target.closest('a[href]');
    if (!link || link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
    var url = new URL(link.href, location.href);
    if (!eligible(url)) return;
    if (url.pathname === renderedURL.pathname && url.search === renderedURL.search && url.hash) {
      ++revision;
      if (request) request.abort();
      main.removeAttribute('aria-busy');
      return;
    }
    event.preventDefault();
    navigate(url, false);
  });
  addEventListener('popstate', function (event) {
    var url = new URL(location.href);
    if (!eligible(url)) return;
    if (url.pathname === renderedURL.pathname && url.search === renderedURL.search) {
      ++revision;
      if (request) request.abort();
      main.removeAttribute('aria-busy');
      if (!url.hash && event.state && event.state.topicPage) scrollTo({ top: event.state.y || 0, left: event.state.x || 0, behavior: 'instant' });
      return;
    }
    navigate(url, true, event.state && event.state.topicPage && !url.hash ? event.state : null);
  });
})();
