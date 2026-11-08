"""Capture one web page -> page model (format 7.1: schema_version 1, screen.source = "dom").

Everything here is MEASURED from the DOM. Nemotron's judgment is added later under `screen.ai`.

Usage (from core/), handy for checking a single page:
    python -m explore.capture_web https://example.com
"""
import hashlib
import json
import re
import sys
import time
from pathlib import Path

from .urlpattern import entity_guess, normalize, url_pattern

SCHEMA_VERSION = 1
MAX_LINKS = 150
MAX_ROWS = 5
ARIA_MAX_CHARS = 6000

# One pass over the DOM. Returns plain JSON. Kept generic: no knowledge of any particular site.
_EXTRACT_JS = r"""
() => {
  const vis = (el) => {
    if (!el) return false;
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const txt = (el) => (el ? (el.innerText || el.textContent || '') : '').replace(/\s+/g, ' ').trim();
  const cssOf = (el) => {
    if (el.id && /^[A-Za-z][\w-]*$/.test(el.id)) return '#' + el.id;
    const name = el.getAttribute('name');
    if (name) return `${el.tagName.toLowerCase()}[name="${name.replace(/"/g, '\\"')}"]`;
    let path = [], cur = el;
    while (cur && cur.nodeType === 1 && path.length < 5) {
      let i = 1, sib = cur;
      while ((sib = sib.previousElementSibling)) if (sib.tagName === cur.tagName) i++;
      path.unshift(`${cur.tagName.toLowerCase()}:nth-of-type(${i})`);
      cur = cur.parentElement;
    }
    return path.join(' > ');
  };
  const labelOf = (el) => {
    const aria = el.getAttribute('aria-label');
    if (aria) return aria.trim();
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l && txt(l)) return txt(l);
    }
    const wrap = el.closest('label');
    if (wrap) {
      const t = txt(wrap).replace(txt(el), '').trim();
      if (t) return t;
    }
    // classic table layout: <td>Last Name:</td><td><input></td>
    const cell = el.closest('td,th');
    if (cell) {
      let prev = cell.previousElementSibling;
      while (prev && !txt(prev)) prev = prev.previousElementSibling;
      if (prev && txt(prev).length < 60) return txt(prev);
    }
    // text right before the field
    let p = el.previousSibling;
    for (let k = 0; p && k < 4; k++, p = p.previousSibling) {
      const t = (p.nodeType === 3 ? p.textContent : txt(p)).replace(/\s+/g, ' ').trim();
      if (t && t.length < 60) return t;
    }
    return el.getAttribute('placeholder') || el.getAttribute('title') || el.getAttribute('name') || '';
  };
  const roleOf = (el) => {
    const r = el.getAttribute('role');
    if (r) return r;
    const tag = el.tagName.toLowerCase(), type = (el.getAttribute('type') || '').toLowerCase();
    if (tag === 'select') return el.multiple ? 'listbox' : 'combobox';
    if (tag === 'textarea') return 'textbox';
    if (tag === 'button') return 'button';
    if (tag === 'input') {
      if (['submit', 'button', 'reset', 'image'].includes(type)) return 'button';
      if (type === 'checkbox') return 'checkbox';
      if (type === 'radio') return 'radio';
      if (type === 'number') return 'spinbutton';
      return 'textbox';
    }
    return tag;
  };

  // ---- links
  const links = [];
  for (const a of document.querySelectorAll('a[href]')) {
    if (!vis(a)) continue;
    let text = txt(a);
    if (!text) { const img = a.querySelector('img[alt]'); text = img ? img.alt.trim() : (a.getAttribute('aria-label') || a.title || ''); }
    const table = a.closest('table');
    let col = null, header = null, row_index = null;
    const cell = a.closest('td,th');
    if (table && cell) {
      const tr = cell.parentElement;
      col = Array.from(tr.children).indexOf(cell);
      const rows = Array.from(table.rows);
      row_index = rows.indexOf(tr);
      const head = table.querySelector('thead tr') || rows.find(r => r.querySelector('th'));
      if (head && head !== tr && head.children[col]) header = txt(head.children[col]);
    }
    links.push({
      text: text.slice(0, 80),
      href: a.href,
      raw_href: a.getAttribute('href'),
      in_nav: !!a.closest('nav,header,[role=navigation],[role=menu],[role=menubar],.nav,.menu,.navbar,#nav,#menu'),
      in_table: !!table && !table.closest('nav,header,[role=navigation]') && row_index !== null && row_index > 0 && !!header,
      table_index: table ? Array.from(document.querySelectorAll('table')).indexOf(table) : null,
      column: col, header, row_index,
      css: cssOf(a),
    });
  }

  // ---- forms (and loose fields outside any <form>)
  const fieldSel = 'input,select,textarea,button';
  const describeField = (el) => {
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || (tag === 'input' ? 'text' : tag)).toLowerCase();
    const label = labelOf(el).replace(/\s*[:*]+\s*$/, '').replace(/^\*\s*/, '').trim();
    const rawLabel = labelOf(el);
    const f = {
      tag, type, role: roleOf(el), name: el.getAttribute('name') || '', id: el.id || '',
      label: label.slice(0, 80),
      required: el.required || el.getAttribute('aria-required') === 'true' || /\*/.test(rawLabel),
      value: (tag === 'select') ? (el.options[el.selectedIndex] ? el.options[el.selectedIndex].text : '') :
             (type === 'password' ? '' : (el.value || '').slice(0, 80)),
      css: cssOf(el),
    };
    if (tag === 'select') f.options = Array.from(el.options).map(o => o.text.trim()).filter(Boolean).slice(0, 40);
    if (el.getAttribute('maxlength')) f.maxlength = +el.getAttribute('maxlength');
    if (el.getAttribute('pattern')) f.pattern = el.getAttribute('pattern');
    if (el.getAttribute('placeholder')) f.placeholder = el.getAttribute('placeholder');
    return f;
  };
  const forms = [];
  const formEls = Array.from(document.forms);
  formEls.forEach((form, i) => {
    if (!vis(form)) return;
    const els = Array.from(form.querySelectorAll(fieldSel)).filter(e => (e.type || '') !== 'hidden' && vis(e));
    const fields = els.filter(e => !(e.tagName === 'BUTTON' || ['submit', 'button', 'reset', 'image'].includes((e.type || '').toLowerCase())));
    const buttons = els.filter(e => !fields.includes(e)).map(b => ({ text: (txt(b) || b.value || '').slice(0, 40), type: (b.type || 'submit').toLowerCase(), css: cssOf(b) }));
    forms.push({
      index: i, action: form.action || location.href, method: (form.getAttribute('method') || 'get').toLowerCase(),
      fields: fields.map(describeField), buttons,
    });
  });
  const loose = Array.from(document.querySelectorAll(fieldSel)).filter(e => !e.form && (e.type || '') !== 'hidden' && vis(e) && e.tagName !== 'BUTTON');
  if (loose.length) forms.push({ index: -1, action: null, method: 'none', fields: loose.map(describeField), buttons: [] });

  // ---- tables
  const tables = [];
  Array.from(document.querySelectorAll('table')).forEach((t, i) => {
    if (!vis(t)) return;
    if (t.querySelector('table')) return;               // layout table wrapping other tables
    const rows = Array.from(t.rows).filter(r => vis(r));
    if (rows.length < 2) return;
    const cells = (r) => Array.from(r.children).map(c => txt(c).slice(0, 60));
    // label:value table (detail pages): 2-4 columns, first column short labels, no header row of <th> across
    const kvRows = rows.filter(r => r.children.length >= 2 && r.children.length <= 4 && txt(r.children[0]).length > 0 && txt(r.children[0]).length < 40);
    const headRow = t.querySelector('thead tr') || (rows[0].querySelectorAll('th').length >= 2 ? rows[0] : null);
    const formInside = !!t.querySelector('input,select,textarea');
    if (!headRow && kvRows.length >= Math.max(2, rows.length * 0.7) && !formInside) {
      const pairs = kvRows.map(r => [txt(r.children[0]).replace(/\s*:\s*$/, ''), txt(r.children[1])]);
      tables.push({ index: i, kind: 'key_value', pairs: pairs.slice(0, 60), row_count: pairs.length });
      return;
    }
    if (formInside) return;                              // a form laid out in a table, handled by forms
    const headers = headRow ? cells(headRow) : [];
    const body = rows.filter(r => r !== headRow);
    const linkCols = {};
    body.slice(0, 10).forEach(r => Array.from(r.children).forEach((c, k) => { if (c.querySelector('a[href]')) linkCols[k] = (linkCols[k] || 0) + 1; }));
    tables.push({
      index: i, kind: 'grid', headers, rows: body.slice(0, %MAX_ROWS%).map(cells), row_count: body.length,
      link_columns: Object.keys(linkCols).map(Number),
    });
  });

  // ---- definition lists also act as label:value detail blocks
  for (const dl of document.querySelectorAll('dl')) {
    if (!vis(dl)) continue;
    const pairs = Array.from(dl.querySelectorAll('dt')).map(dt => [txt(dt).replace(/\s*:\s*$/, ''), txt(dt.nextElementSibling)]);
    if (pairs.length >= 2) tables.push({ index: -1, kind: 'key_value', pairs: pairs.slice(0, 60), row_count: pairs.length });
  }

  // ---- visible messages (errors, notices)
  const messages = [];
  for (const el of document.querySelectorAll('[role=alert],[role=status],.error,.errors,.alert,.message,.msg,.notice,.flash,.warning,font[color]')) {
    const t = txt(el);
    if (t && vis(el) && t.length < 300 && !messages.includes(t)) messages.push(t);
  }

  const headings = Array.from(document.querySelectorAll('h1,h2,h3,caption,legend,title')).map(txt).filter(Boolean).slice(0, 12);
  return {
    url: location.href, title: document.title, headings, links, forms, tables, messages: messages.slice(0, 10),
    has_password: !!document.querySelector('input[type=password]'),
    text_excerpt: txt(document.body).slice(0, 1500),
  };
}
""".replace("%MAX_ROWS%", str(MAX_ROWS))

NEXT_TEXT = re.compile(r"^\s*(next|next page|more|older)\b|(>>|»|›|→)\s*$|^\s*(>|»|›)\s*$", re.I)
PREV_TEXT = re.compile(r"^\s*(prev|previous|back|newer)\b|^\s*(<<|«|‹|←)", re.I)


REPEAT_MIN = 5  # this many different links of ONE page type outside nav/tables = a list of records


def mark_repeated_links(dom, page_url):
    """Lists that are not <table>s (cards, <li> items): many links to different records of one page type.

    Marks those links `in_repeat` and returns the size of the biggest group. Generic: works by URL shape only.
    """
    from .urlpattern import type_key

    page_key = type_key(normalize(page_url))
    groups = {}
    for l in dom["links"]:
        if l["in_nav"] or l["in_table"] or not l.get("href", "").startswith("http"):
            continue
        key = type_key(normalize(l["href"]))
        if key == page_key or "{id}" not in key:
            continue
        groups.setdefault(key, set()).add(normalize(l["href"]))
    best = max(groups.items(), key=lambda kv: len(kv[1]), default=(None, set()))
    if len(best[1]) >= REPEAT_MIN:
        for l in dom["links"]:
            if l.get("href", "").startswith("http") and not l["in_nav"] and not l["in_table"] \
                    and type_key(normalize(l["href"])) == best[0]:
                l["in_repeat"] = True
    return len(best[1])


def classify_kind(dom, repeated=0):
    """Heuristic page kind from structure alone: login | form | list | detail | menu | other."""
    if dom.get("has_password"):
        return "login"
    grids = [t for t in dom["tables"] if t["kind"] == "grid"]
    kv = [t for t in dom["tables"] if t["kind"] == "key_value"]
    data_forms = [f for f in dom["forms"]
                  if len([x for x in f["fields"] if x["type"] not in ("search",)]) >= 2]
    if data_forms:
        return "form"
    if any(t["link_columns"] and t["row_count"] >= 2 for t in grids):
        return "list"
    if kv and max(t["row_count"] for t in kv) >= 3:
        return "detail"
    if grids or repeated >= REPEAT_MIN:
        return "list"
    if len(dom["links"]) >= 3:
        return "menu"
    return "other"


def fingerprint(pattern, dom):
    parts = [pattern]
    parts += ["|".join(t.get("headers", [])) for t in dom["tables"] if t["kind"] == "grid"]
    parts += [",".join(sorted(f["label"] for f in form["fields"])) for form in dom["forms"]]
    return hashlib.sha1("\n".join(parts).encode()).hexdigest()[:16]


def pagination_of(dom, repeated=0):
    nxt = next((l for l in dom["links"] if NEXT_TEXT.search(l["text"] or "")), None)
    prv = next((l for l in dom["links"] if PREV_TEXT.search(l["text"] or "")), None)
    if not nxt and not prv:
        return None
    grid = next((t for t in dom["tables"] if t["kind"] == "grid"), None)
    out = {}
    if nxt:
        out["next"] = {"role": "link", "name": nxt["text"]}
        out["next_url_pattern"] = url_pattern(nxt["href"])
    if prv:
        out["prev"] = {"role": "link", "name": prv["text"]}
    if grid:
        out["page_size"] = grid["row_count"]
    elif repeated >= REPEAT_MIN:
        out["page_size"] = repeated
    return out


def capture(page, shots_dir=None, aria=True):
    """Capture the page that is open in Playwright -> page model dict."""
    t0 = time.time()
    dom = page.evaluate(_EXTRACT_JS)
    url = normalize(dom["url"])
    dom["links"] = dom["links"][:MAX_LINKS]
    pattern = url_pattern(url)
    repeated = mark_repeated_links(dom, url)
    kind = classify_kind(dom, repeated)

    aria_text = ""
    if aria:
        try:
            aria_text = page.locator("body").aria_snapshot(timeout=5000)[:ARIA_MAX_CHARS]
        except Exception as e:  # older Playwright or odd pages: not fatal
            aria_text = f"(aria snapshot unavailable: {str(e)[:80]})"

    fp = fingerprint(pattern, dom)
    shot = None
    if shots_dir is not None:
        shots_dir = Path(shots_dir)
        shots_dir.mkdir(parents=True, exist_ok=True)
        shot = shots_dir / f"{fp}.png"
        try:
            page.screenshot(path=str(shot), full_page=False)
        except Exception:
            shot = None

    # Locators the Operator can use later: role + label first, css as backup (format 7.1)
    for form in dom["forms"]:
        for f in form["fields"]:
            f["locator"] = {"role": f["role"], "name": f["label"], "label": f["label"], "css": f["css"]}

    return {
        "schema_version": SCHEMA_VERSION,
        "screen": {
            "id": None,  # set by the explorer once the page type is known
            "source": "dom",
            "url": url,
            "url_pattern": pattern,
            "title": dom["title"],
            "screenshot": str(shot) if shot else None,
            "fingerprint": fp,
            "captured_at": time.time(),
            "capture_ms": int((time.time() - t0) * 1000),
            "heuristic": {"kind": kind, "entity": entity_guess(url), "pagination": pagination_of(dom, repeated)},
            "ai": {},
        },
        "dom": dom,
        "aria": aria_text,
    }


def summarize(model, max_links=25):
    """Compact text version of a page model for prompts and logs (far fewer tokens than JSON)."""
    s, d = model["screen"], model["dom"]
    lines = [f"URL: {s['url']}", f"Pattern: {s['url_pattern']}", f"Title: {s['title']}"]
    if d["headings"]:
        lines.append("Headings: " + " | ".join(d["headings"][:6]))
    if d["messages"]:
        lines.append("Messages: " + " | ".join(d["messages"][:4]))
    for t in d["tables"]:
        if t["kind"] == "grid":
            lines.append(f"Table ({t['row_count']} rows): columns = {t['headers']}; first row = "
                         f"{t['rows'][0] if t['rows'] else []}; link columns = {t['link_columns']}")
        else:
            lines.append("Label/value block: " + "; ".join(f"{k}: {v}" for k, v in t["pairs"][:15]))
    for f in d["forms"]:
        fl = ", ".join(f"{x['label'] or x['name']}{'*' if x['required'] else ''} ({x['type']}"
                       + (f": {'/'.join(x['options'][:6])}" if x.get("options") else "") + ")"
                       for x in f["fields"][:20])
        btns = ", ".join(b["text"] for b in f["buttons"])
        lines.append(f"Form [{f['method'].upper()}]: fields = {fl}; buttons = {btns}")
    links = [l for l in d["links"] if not l["in_table"]][:max_links]
    if links:
        lines.append("Links: " + " | ".join(f"{l['text'] or '(no text)'}" for l in links))
    if d["has_password"]:
        lines.append("Has a password field (login page).")
    return "\n".join(lines)


def main(argv=None):
    from playwright.sync_api import sync_playwright

    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        raise SystemExit("usage: python -m explore.capture_web URL")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(argv[0], wait_until="domcontentloaded")
        model = capture(page)
        browser.close()
    print(summarize(model))
    print(json.dumps(model["screen"], indent=2)[:2000])


if __name__ == "__main__":
    main()
