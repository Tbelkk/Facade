// API page: lists the generated endpoints (Swagger-style) and shows mock responses.
window.apiView = (function () {
  const root = document.getElementById('apiList');
  const api = window.mockApi;

  function h(tag, props, ...kids) {
    const el = document.createElement(tag);
    if (props) for (const [k, v] of Object.entries(props)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) el.append(kid instanceof Node ? kid : String(kid));
    return el;
  }
  const svg = (d, cls) => { const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('aria-hidden', 'true'); if (cls) s.setAttribute('class', cls); s.innerHTML = d; return s; };
  const CHEVRON = '<path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>';
  const LOCK = '<rect x="5" y="11" width="14" height="10" rx="2" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 11V8a4 4 0 0 1 8 0v3" fill="none" stroke="currentColor" stroke-width="1.5"/>';

  // "/astra/{date}/{building}" → path text with dimmed {params}
  function pathEl(path) {
    return h('span', { class: 'ep-path' }, path.split(/(\{\w+\})/).filter(Boolean).map((part) => (part.startsWith('{') ? h('i', null, part) : part)));
  }

  // pretty JSON with tinted tokens, built from text nodes (never innerHTML)
  function jsonEl(value) {
    const text = JSON.stringify(value, null, 2);
    const pre = h('pre', { class: 'json' });
    const re = /("(?:\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(?:true|false)\b|\bnull\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;
    let last = 0, m;
    while ((m = re.exec(text))) {
      if (m.index > last) pre.append(text.slice(last, m.index));
      const tok = m[0];
      const cls = /^"/.test(tok) ? (m[2] ? 'j-key' : 'j-str') : /true|false/.test(tok) ? 'j-bool' : tok === 'null' ? 'j-null' : 'j-num';
      pre.append(h('span', { class: cls }, tok));
      last = re.lastIndex;
    }
    pre.append(text.slice(last));
    return pre;
  }

  function fill(path, params) {
    return path.replace(/\{(\w+)\}/g, (_, k) => encodeURIComponent(params[k] ?? `{${k}}`));
  }

  async function copy(text, btn) {
    const was = btn.textContent;
    try { await navigator.clipboard.writeText(text); btn.textContent = 'Copied'; } catch { btn.textContent = 'Failed'; }
    setTimeout(() => { btn.textContent = was; }, 1200);
  }

  function endpointEl(ep) {
    const inputs = {};
    let ran = false, body = null;

    const panel = h('div', { class: 'ep-body', hidden: true });
    const toggle = h('button', { type: 'button', class: 'ep-row', 'aria-expanded': 'false' },
      h('span', { class: 'verb' }, ep.method), pathEl(ep.path), h('span', { class: 'ep-sum' }, ep.summary),
      svg(CHEVRON, 'chev'), svg(LOCK, 'lock'));
    const el = h('div', { class: 'ep' }, toggle, panel);

    const urlLine = h('code', { class: 'req-url' });
    const out = h('div', { class: 'resp' });
    const runBtn = h('button', { type: 'button', class: 'btn primary small' }, 'Run');
    const curlBtn = h('button', { type: 'button', class: 'mini' }, 'Copy curl');
    const jsonBtn = h('button', { type: 'button', class: 'mini', disabled: true }, 'Copy JSON');

    const values = () => Object.fromEntries(ep.params.map((p) => [p.name, inputs[p.name].value.trim()]));
    const updateUrl = () => { urlLine.textContent = `${ep.method} ${api.base}${fill(ep.path, values())}`; };

    async function run() {
      updateUrl();
      runBtn.disabled = true;
      out.replaceChildren(h('div', { class: 'loading' }, h('span', { class: 'dots' }, h('i'), h('i'), h('i'), h('i'), h('i')), 'Calling mock API…'));
      const res = await api.call(ep, values());
      body = res.body;
      jsonBtn.disabled = false;
      const ok = res.status < 400;
      out.replaceChildren(
        h('div', { class: 'resp-head' },
          h('span', { class: `code ${ok ? 'ok' : 'bad'}` }, `${res.status} ${ok ? 'OK' : res.status === 404 ? 'Not Found' : 'Bad Request'}`),
          h('span', null, `${res.ms} ms`), h('span', null, 'application/json'), h('span', { class: 'mock-tag' }, 'mock data'), jsonBtn),
        jsonEl(res.body));
      runBtn.disabled = false;
    }

    const paramRows = ep.params.length
      ? h('div', { class: 'params' }, ep.params.map((p) => {
          const input = h('input', { type: 'text', spellcheck: 'false', value: p.example(), 'aria-label': p.name });
          input.addEventListener('input', updateUrl);
          input.addEventListener('keydown', (e) => { if (e.key === 'Enter') run(); });
          inputs[p.name] = input;
          return h('label', { class: 'param' },
            h('span', { class: 'p-name' }, p.name, h('em', null, '*')),
            h('span', { class: 'p-meta' }, 'path · string'),
            input,
            h('span', { class: 'p-desc' }, p.description));
        }))
      : h('p', { class: 'no-params' }, 'No parameters.');

    panel.append(
      h('div', { class: 'ep-sec' }, 'Parameters'), paramRows,
      h('div', { class: 'req' }, urlLine, h('div', { class: 'req-btns' }, curlBtn, runBtn)),
      h('div', { class: 'ep-sec' }, 'Response'), out);

    runBtn.addEventListener('click', run);
    curlBtn.addEventListener('click', () => copy(`curl -H "Authorization: Bearer $FACADE_TOKEN" "${api.base}${fill(ep.path, values())}"`, curlBtn));
    jsonBtn.addEventListener('click', () => body && copy(JSON.stringify(body, null, 2), jsonBtn));

    toggle.addEventListener('click', () => {
      const open = panel.hidden;
      panel.hidden = !open;
      el.classList.toggle('open', open);
      toggle.setAttribute('aria-expanded', String(open));
      if (open && !ran) { ran = true; run(); }   // first open shows mock data right away
    });
    updateUrl();
    return el;
  }

  function render() {
    let total = 0;
    root.replaceChildren(...api.spec.map((group) => {
      total += group.endpoints.length;
      const list = h('div', { class: 'tag-list' }, group.endpoints.map(endpointEl));
      const head = h('button', { type: 'button', class: 'tag-head', 'aria-expanded': 'true' },
        h('h3', null, group.tag), h('span', { class: 'tag-desc' }, group.description),
        h('span', { class: 'tag-count' }, `${group.endpoints.length}`), svg(CHEVRON, 'chev'));
      const sec = h('section', { class: 'tag-sec open' }, head, list);
      head.addEventListener('click', () => {
        const open = !sec.classList.contains('open');
        sec.classList.toggle('open', open);
        head.setAttribute('aria-expanded', String(open));
      });
      return sec;
    }));
    document.getElementById('apiBase').textContent = api.base;
    document.getElementById('apiCount').textContent = `${total} endpoints`;
  }

  render();

  return {
    setSource(host) {
      document.getElementById('apiSource').textContent = host
        ? `Generated for ${host}. Showing mock data until the back end is connected.`
        : 'Run the agents on a site to generate its API. Showing mock data for now.';
    },
  };
})();
