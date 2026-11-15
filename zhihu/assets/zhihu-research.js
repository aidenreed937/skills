(() => {
  const sources = [...document.querySelectorAll('.source-detail')];
  const contents = document.querySelector('details.contents');
  const narrow = window.matchMedia('(max-width: 760px)');
  function fitNavigation() { if (contents) contents.open = !narrow.matches; }
  fitNavigation();
  narrow.addEventListener('change', fitNavigation);
  function revealHash() {
    let target;
    try { target = document.getElementById(decodeURIComponent(location.hash.slice(1))); } catch (_) { return; }
    if (target?.classList.contains('source-detail')) target.open = true;
  }
  document.querySelectorAll('.citations a').forEach(link => link.addEventListener('click', () => {
    const target = document.querySelector(link.getAttribute('href'));
    if (target) target.open = true;
  }));
  window.addEventListener('hashchange', revealHash);
  revealHash();
  const links = [...document.querySelectorAll('.contents a')];
  const sections = links.map(link => document.querySelector(link.getAttribute('href'))).filter(Boolean);
  let ticking = false;
  function markSection() {
    ticking = false;
    let current = sections[0];
    for (const section of sections) {
      if (section.getBoundingClientRect().top <= 110) current = section;
    }
    links.forEach(link => {
      if (current && link.getAttribute('href') === '#' + current.id) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    });
  }
  window.addEventListener('scroll', () => {
    if (!ticking) { ticking = true; requestAnimationFrame(markSection); }
  }, { passive: true });
  markSection();
  let beforePrint;
  window.addEventListener('beforeprint', () => {
    beforePrint = sources.map(detail => detail.open);
    sources.forEach(detail => { detail.open = true; });
  });
  window.addEventListener('afterprint', () => {
    if (beforePrint) sources.forEach((detail, n) => { detail.open = beforePrint[n]; });
  });
  document.querySelector('.print-button')?.addEventListener('click', () => window.print());
})();

/* Local article navigation. Links and native mobile details work without JS. */
(() => {
  for (const link of document.querySelectorAll('.article-prose a')) {
    if (link.href.startsWith('https:') || link.href.startsWith('http:')) {
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
    }
  }

  const links = [...document.querySelectorAll('[data-article-nav] a[href^="#"]')];
  const sections = [...document.querySelectorAll('.article-prose > h2[id]')];
  const mobile = document.querySelector('details.article-contents');
  const position = document.querySelector('.article-nav-position');
  if (!links.length || !sections.length) return;

  function markCurrent(section) {
    if (!section) return;
    links.forEach(link => {
      if (link.getAttribute('href') === '#' + section.id) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
    if (position) position.textContent = (sections.indexOf(section) + 1) + ' / ' + sections.length;
  }

  let pending = false;
  function updatePosition() {
    pending = false;
    let current = sections[0];
    for (const section of sections) {
      if (section.getBoundingClientRect().top <= 88) current = section;
    }
    if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 3) current = sections[sections.length - 1];
    markCurrent(current);
  }
  function schedulePosition() {
    if (!pending) {
      pending = true;
      requestAnimationFrame(updatePosition);
    }
  }
  links.forEach(link => link.addEventListener('click', () => {
    const section = document.getElementById(link.getAttribute('href').slice(1));
    markCurrent(section);
    if (mobile?.contains(link)) mobile.open = false;
    // Preserve the native hash jump; moving focus makes keyboard reading resume
    // at the selected section rather than inside a now closed mobile menu.
    section?.focus({ preventScroll: true });
  }));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && mobile?.open) {
      mobile.open = false;
      mobile.querySelector('summary')?.focus();
    }
  });
  document.addEventListener('pointerdown', event => {
    if (mobile?.open && !mobile.contains(event.target)) mobile.open = false;
  });
  window.addEventListener('scroll', schedulePosition, { passive: true });
  window.addEventListener('resize', schedulePosition);
  window.addEventListener('hashchange', schedulePosition);
  updatePosition();
})();

/* Local collection search; native links/details remain useful without JavaScript. */
(() => {
  const tools = document.querySelector('.browse-tools');
  const input = document.querySelector('#collection-search');
  const clear = document.querySelector('.clear-search');
  const count = document.querySelector('.result-count');
  const empty = document.querySelector('.search-empty');
  const groups = [...document.querySelectorAll('.topic-group')];
  const items = groups.length ? groups.flatMap(g => [...g.querySelectorAll('.source-card')]) : [...document.querySelectorAll('.update-item')];
  const texts = new Map(items.map(item => [item, item.textContent.normalize('NFKC').toLocaleLowerCase()]));
  const details = [...document.querySelectorAll('.update-details,.progress-disclosure')];
  const progress = document.querySelector('.progress-disclosure');
  const narrow = window.matchMedia('(max-width: 760px)');
  function fitProgress() { if (progress) progress.open = !narrow.matches; }
  fitProgress();
  narrow.addEventListener('change', fitProgress);
  const normalize = value => value.normalize('NFKC').toLocaleLowerCase().trim();
  function filter() {
    const terms = normalize(input.value).split(/\s+/).filter(Boolean);
    let visible = 0;
    for (const item of items) {
      const topic = normalize(item.closest('.topic-group')?.dataset.topic || '');
      const text = texts.get(item) + ' ' + topic;
      item.hidden = !terms.every(term => text.includes(term));
      if (!item.hidden) visible += 1;
    }
    groups.forEach(group => { group.hidden = [...group.querySelectorAll('.source-card')].every(item => item.hidden); });
    count.textContent = terms.length ? `${visible} / ${items.length} ${count.dataset.noun}` : `${items.length} ${count.dataset.noun}`;
    empty.hidden = !terms.length || visible > 0;
    clear.hidden = !input.value;
  }
  if (!tools || !input || !items.length) return;
  tools.hidden = false;
  input.addEventListener('input', filter);
  clear.addEventListener('click', () => { input.value = ''; filter(); input.focus(); });
  input.addEventListener('keydown', event => {
    if (event.key === 'Escape') { input.value = ''; filter(); }
  });
  document.querySelectorAll('.contents a').forEach(link => link.addEventListener('click', () => {
    input.value = ''; filter();
  }));
  let saved;
  window.addEventListener('beforeprint', () => {
    saved = {query: input.value, open: details.map(detail => detail.open)};
    input.value = ''; filter();
    details.forEach(detail => { detail.open = true; });
  });
  window.addEventListener('afterprint', () => {
    if (!saved) return;
    input.value = saved.query; filter();
    details.forEach((detail, index) => { detail.open = saved.open[index]; });
    saved = undefined;
  });
})();
