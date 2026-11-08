"""Capture a real web page -> page model (Screen Snapshot, source "dom") for the explorer.

Works on any OS (Mac included). Reads only: never clicks, types or submits.

Usage (from core/):
    python -m explore.capture_web https://example.com
    python -m explore.capture_web http://localhost:5005/patients --label      # + Nemotron labels
    python -m explore.capture_web http://localhost:5005 --headed --login     # you log in by hand first;
                                                                             # the session is saved for reuse
Output: cache/web/<snapshot_id>.json + .png   (open them in: python -m ingest.inspect)

What a page model contains (on top of the normal snapshot fields):
    nodes[]         every meaningful element with an ARIA role, accessible name, value, rect, locator
    web.forms[]     each form: action, method, fields (label, name, type, required, options, pattern, maxlength)
    web.tables[]    headers, first rows, row count, which column links to a detail page
    web.links[]     visible links (text, href, same_site)
    web.pagination  "next"/"prev" links if any
    web.alerts[]    visible error/notice messages (often reveal business rules)
    web.aria_yaml   Playwright's compact ARIA tree (great context for Nemotron)
"""
import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from ingest.paths import CACHE_DIR

WEB_DIR = CACHE_DIR / "web"
AUTH_FILE = WEB_DIR / "auth_state.json"
VIEWPORT = {"width": 1280, "height": 900}
MAX_NODES = 400

# Runs inside the page. Collects elements with role, accessible name, state and a locator.
EXTRACT_JS = r"""
(maxNodes) => {
  const vis = el => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0';
  };
  const txt = s => (s || '').replace(/\s+/g, ' ').trim();
  const clean = s => txt(s).replace(/[\s:*]+$/, '').replace(/^[\s*]+/, '');
  const starred = el => /\*/.test(rawLabel(el));
  const labelFor = el => clean(rawLabel(el));
  const rawLabel = el => {
    if (el.getAttribute('aria-label')) return txt(el.getAttribute('aria-label'));
    const lb = el.getAttribute('aria-labelledby');
    if (lb) return txt(lb.split(/\s+/).map(i => document.getElementById(i)?.innerText || '').join(' '));
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return txt(l.innerText); }
    const wrap = el.closest('label'); if (wrap) return txt(wrap.innerText);
    // legacy layouts: label in the previous table cell or previous sibling text
    const td = el.closest('td');
    if (td && td.previousElementSibling) { const t = txt(td.previousElementSibling.innerText); if (t && t.length < 60) return t; }
    let p = el.previousSibling;
    while (p && p.nodeType === 3 && !txt(p.textContent)) p = p.previousSibling;
    if (p) { const t = txt(p.textContent || p.innerText); if (t && t.length < 60) return t; }
    return txt(el.getAttribute('placeholder') || el.getAttribute('title') || el.getAttribute('name') || '');
  };
  const roleOf = el => {
    const r = el.getAttribute('role'); if (r) return r;
    const t = el.tagName.toLowerCase(), ty = (el.getAttribute('type') || '').toLowerCase();
    if (t === 'a' && el.hasAttribute('href')) return 'link';
    if (t === 'button' || (t === 'input' && ['submit','button','reset','image'].includes(ty))) return 'button';
    if (t === 'input' && ty === 'checkbox') return 'checkbox';
    if (t === 'input' && ty === 'radio') return 'radio';
    if (t === 'input' && ty === 'hidden') return null;
    if (t === 'input' && ty === 'number') return 'spinbutton';
    if (t === 'input' || t === 'textarea') return 'textbox';
    if (t === 'select') return el.multiple ? 'listbox' : 'combobox';
    if (t === 'table') return 'table';
    if (/^h[1-6]$/.test(t)) return 'heading';
    if (t === 'form') return 'form';
    if (t === 'nav') return 'navigation';
    if (t === 'img') return 'img';
    if (t === 'label') return 'label';
    if (t === 'fieldset') return 'group';
    return null;
  };
  const cssFor = el => {
    if (el.id) return '#' + CSS.escape(el.id);
    const n = el.getAttribute('name'); if (n) return `${el.tagName.toLowerCase()}[name="${n}"]`;
    const parts = []; let e = el;
    while (e && e.nodeType === 1 && parts.length < 5) {
      let i = 1, s = e; while ((s = s.previousElementSibling)) if (s.tagName === e.tagName) i++;
      parts.unshift(`${e.tagName.toLowerCase()}:nth-of-type(${i})`); e = e.parentElement;
    }
    return parts.join(' > ');
  };
  const nameOf = (el, role) => {
    if (['textbox','combobox','listbox','checkbox','radio','spinbutton'].includes(role)) return labelFor(el);
    if (role === 'img') return txt(el.getAttribute('alt') || el.getAttribute('title'));
    if (['form', 'table', 'group', 'navigation'].includes(role))   // containers: only an explicit name, not all their text
      return txt(el.getAttribute('aria-label') || el.querySelector(':scope > caption, :scope > legend')?.innerText || el.getAttribute('title') || '').slice(0, 80);
    if (el.tagName === 'INPUT') return txt(el.value || el.getAttribute('aria-label') || el.getAttribute('title'));
    return txt(el.getAttribute('aria-label') || el.innerText || el.getAttribute('title')).slice(0, 120);
  };

  const nodes = [], ids = new Map();
  const all = document.body ? document.body.querySelectorAll('*') : [];
  for (const el of all) {
    if (nodes.length >= maxNodes) break;
    const role = roleOf(el); if (!role || !vis(el)) continue;
    // skip table cells' inner links duplicates? keep links: they drive navigation
    const r = el.getBoundingClientRect();
    let parent = null, p = el.parentElement;
    while (p) { if (ids.has(p)) { parent = ids.get(p); break; } p = p.parentElement; }
    const id = nodes.length; ids.set(el, id);
    const t = el.tagName.toLowerCase();
    const n = {
      id, parent, role, name: nameOf(el, role),
      automation_id: el.id || el.getAttribute('name') || '',
      class_name: t + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : ''),
      rect: { x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height) },
      value: null, enabled: !el.disabled, actions: [], css: cssFor(el),
    };
    if (role === 'textbox' || role === 'spinbutton') { n.value = el.value ?? ''; n.actions = ['set_value', 'focus']; }
    if (role === 'combobox' || role === 'listbox') {
      n.value = el.options && el.selectedIndex >= 0 ? txt(el.options[el.selectedIndex].text) : '';
      n.options = Array.from(el.options || []).map(o => txt(o.text)).slice(0, 50); n.actions = ['select'];
    }
    if (role === 'checkbox' || role === 'radio') { n.toggle_state = el.checked ? 1 : 0; n.actions = ['toggle']; }
    if (role === 'button' || role === 'link') n.actions = ['invoke'];
    if (role === 'link') n.href = el.href;
    if (el.required || el.getAttribute('aria-required') === 'true' ||
        (['textbox','combobox','spinbutton'].includes(role) && starred(el))) n.required = true;
    if (el.readOnly) n.readonly = true;
    if (el.type === 'password') n.password = true;
    if (el.getAttribute('title')) n.help_text = txt(el.getAttribute('title')).slice(0, 160);
    if (el.getAttribute('accesskey')) n.hotkey = 'Alt+' + el.getAttribute('accesskey').toUpperCase();
    if (role === 'heading') n.level = +t[1];
    nodes.push(n);
  }

  const forms = Array.from(document.forms).filter(vis).map((f, i) => ({
    index: i, action: f.getAttribute('action') || location.pathname, method: (f.method || 'get').toUpperCase(),
    fields: Array.from(f.elements).filter(e => e.name && e.type !== 'hidden' && vis(e)).map(e => ({
      label: labelFor(e), name: e.name, tag: e.tagName.toLowerCase(), type: (e.type || '').toLowerCase(),
      required: !!(e.required || e.getAttribute('aria-required') === 'true' || starred(e)),
      pattern: e.getAttribute('pattern') || null, maxlength: e.maxLength > 0 ? e.maxLength : null,
      options: e.options ? Array.from(e.options).map(o => txt(o.text)).slice(0, 50) : null,
      value: e.type === 'password' ? null : (e.value ?? null), css: cssFor(e),
    })),
    submit: Array.from(f.querySelectorAll('button, input[type=submit]')).filter(vis).map(b => txt(b.innerText || b.value)),
  }));

  // Data tables. Handles legacy layouts: no header row, and records spread over several rows
  // (e.g. a title row + a details row + a spacer row, repeating).
  const ACTION = /vote|hide|flag|delete|remove|logout|log out|[?&](how|action|act|op|do|cmd)=/i;
  const tables = Array.from(document.querySelectorAll('table')).filter(vis).map((t, i) => {
    if (t.querySelector('input, select, textarea, table')) return null;     // forms / layout wrappers
    const rows = Array.from(t.rows).filter(r => vis(r));
    if (rows.length < 2) return null;
    const headRow = t.tHead ? t.tHead.rows[0] : (rows[0].querySelector('th') ? rows[0] : null);
    const data = rows.filter(r => r !== headRow);
    if (!data.length) return null;
    // find how many rows make up one record (1, 2 or 3) from the repeating cell-count pattern
    // row "shape" = cell count + which cells have text + class; a record repeats the same shapes
    const counts = data.map(r => r.cells.length + ':' + Array.from(r.cells).map(c => txt(c.innerText) ? 1 : 0).join('') + ':' + r.className);
    const size = data.map(r => Array.from(r.cells).filter(c => txt(c.innerText)).length);
    let period = 1;
    for (const p of (headRow ? [1] : [1, 2, 3])) {   // tables with a header row = one row per record
      let ok = 0, tot = 0;
      for (let k = p; k < counts.length; k++) { tot++; if (counts[k] === counts[k - p]) ok++; }
      if (tot && ok / tot >= 0.85) { period = p; break; }
    }
    let startAt = 0;                        // a record starts at the row with the most cells
    for (let k = 1; k < Math.min(period, data.length); k++) if (size[k] > size[startAt]) startAt = k;
    const groups = [];
    for (let k = startAt; k + period <= data.length; k += period) groups.push(data.slice(k, k + period));
    const recCells = g => g.flatMap(r => Array.from(r.cells)).map(c => txt(c.innerText).slice(0, 200));
    const recLinks = g => g.flatMap(r => Array.from(r.querySelectorAll('a[href]')))
      .map(a => [txt(a.innerText).slice(0, 60), a.href]).filter(([tx, h]) => tx && !h.startsWith('javascript:') && !ACTION.test(h + ' ' + tx)).slice(0, 10);
    const records = groups.map(g => ({ cells: recCells(g), links: recLinks(g) })).filter(r => r.cells.some(Boolean));
    if (!records.length) return null;
    const width = Math.max(...records.slice(0, 20).map(r => r.cells.length));
    let headers;
    if (headRow && period === 1) headers = Array.from(headRow.cells).map((c, k) => txt(c.innerText) || `col${k + 1}`);
    else headers = Array.from({ length: width }, (_, k) => `col${k + 1}`);
    if (width < 2 && !records.some(r => r.links.length)) return null;
    if (headRow && headers.filter(h => !/^col\d+$/.test(h)).length < headers.length * 0.6) return null;
    return {
      index: i, css: cssFor(t), headers, has_header: !!headRow, rows_per_record: period, row_count: records.length,
      sample_rows: records.slice(0, 5).map(r => r.cells.map(c => c.slice(0, 80))),
      sample_links: records.slice(0, 3).map(r => r.links),
      rows: records.slice(0, 500).map(r => r.cells),
      row_links: records.slice(0, 500).map(r => r.links),
      link_column: null,
    };
  }).filter(Boolean);

  const sameSite = h => { try { return new URL(h).host === location.host; } catch { return false; } };
  const allLinks = Array.from(document.querySelectorAll('a[href]')).filter(vis)
    .map(a => ({ text: txt(a.innerText || a.title).slice(0, 80), href: a.href, same_site: sameSite(a.href) }))
    .filter(l => l.text && !l.href.startsWith('javascript:'));
  const links = allLinks.slice(0, 150);
  // pagination is usually at the very bottom, so search ALL links (busy pages have hundreds)
  const pag = re => allLinks.filter(l => l.same_site).reverse().find(l => re.test(l.text));
  const pagination = { next: pag(/^(next|more|older|›|»|>>|next\s*>+|next page|more\s*»?|load more|older posts)$/i) || pag(/\bnext\b/i) || null,
                       prev: pag(/^(prev|previous|‹|«|<<)/i) || null };

  // label/value pairs (detail pages): 2-cell table rows and <dl> lists
  const label_values = [];
  for (const tr of document.querySelectorAll('tr')) {
    if (tr.cells.length !== 2 || !vis(tr) || tr.querySelector('th')) continue;
    if (tr.cells[1].querySelector('input, select, textarea, table')) continue;
    const k = clean(tr.cells[0].innerText), v = txt(tr.cells[1].innerText);
    if (k && k.length <= 40) label_values.push([k, v.slice(0, 300)]);
  }
  for (const dt of document.querySelectorAll('dt')) {
    const dd = dt.nextElementSibling;
    if (dd && dd.tagName === 'DD' && vis(dt)) label_values.push([clean(dt.innerText), txt(dd.innerText).slice(0, 300)]);
  }
  const alertSel = '[role=alert], .error, .errors, .alert, .warning, .notice, .message, font[color=red], font[color="#FF0000"], .msg';
  const alerts = Array.from(document.querySelectorAll(alertSel)).filter(vis).map(e => txt(e.innerText)).filter(t => t.length > 2).slice(0, 10);

  return { nodes, forms, tables, links, pagination, alerts, label_values: label_values.slice(0, 150),
           title: document.title, page_w: document.documentElement.scrollWidth, page_h: document.documentElement.scrollHeight };
}
"""


def url_pattern(url):
    """/patients/42/edit?x=1 -> /patients/{id}/edit  (so the same page type gets the same fingerprint)."""
    p = urlparse(url)
    path = re.sub(r"/\d+(?=[/.]|$)", "/{id}", p.path) or "/"
    path = re.sub(r"/[0-9a-f]{8,}(?=/|$)", "/{id}", path)
    keys = sorted(k.split("=")[0] for k in p.query.split("&") if k)
    return path + (("?" + "&".join(f"{k}=" for k in keys)) if keys else "")


def capture_page(page, out_dir=WEB_DIR, full_page=False):
    """Capture the CURRENT page of a Playwright page object. Returns the page-model dict."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    data = page.evaluate(EXTRACT_JS, MAX_NODES)
    try:
        aria = page.locator("body").aria_snapshot()
    except Exception:
        aria = ""
    snap_id = f"web_{int(time.time() * 1000)}"
    png = out_dir / f"{snap_id}.png"
    page.screenshot(path=str(png), full_page=full_page)
    vw = page.viewport_size or VIEWPORT
    w = data["page_w"] if full_page else vw["width"]
    h = data["page_h"] if full_page else vw["height"]
    if not full_page:  # keep only nodes visible in the screenshot for rect-based views
        for n in data["nodes"]:
            n["in_view"] = n["rect"]["y"] < h and n["rect"]["x"] < w

    host = urlparse(page.url).netloc or "local"
    skeleton = "|".join(f'{n["role"]}:{n["automation_id"]}' for n in data["nodes"] if n["role"] != "link")
    snapshot = {
        "snapshot_id": snap_id,
        "source": "dom",
        "app": {"process": host, "window_title": data["title"] or page.url, "hwnd": 0, "url": page.url},
        "window_rect": {"x": 0, "y": 0, "w": w, "h": h},
        "dpi_scale": 1.0,
        "fingerprint": f"{host}|{url_pattern(page.url)}|{hashlib.sha1(skeleton.encode()).hexdigest()[:10]}",
        "screenshot_path": str(png.resolve()),
        "window_kind": "main",
        "window_parent": None,
        "menus": [],
        "nodes": data["nodes"],
        "node_count": len(data["nodes"]),
        "truncated": len(data["nodes"]) >= MAX_NODES,
        "walk_ms": int((time.time() - t0) * 1000),
        "web": {
            "url": page.url,
            "url_pattern": url_pattern(page.url),
            "title": data["title"],
            "forms": data["forms"],
            "tables": data["tables"],
            "links": data["links"],
            "pagination": data["pagination"],
            "alerts": data["alerts"],
            "label_values": data["label_values"],
            "aria_yaml": aria[:20000],
        },
    }
    (out_dir / f"{snap_id}.json").write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    return snapshot


def open_browser(p, headed=False):
    browser = p.chromium.launch(headless=not headed)
    kwargs = {"viewport": VIEWPORT}
    if AUTH_FILE.is_file():
        kwargs["storage_state"] = str(AUTH_FILE)
    ctx = browser.new_context(**kwargs)
    return browser, ctx


def summarize(s):
    w = s["web"]
    roles = {}
    for n in s["nodes"]:
        roles[n["role"]] = roles.get(n["role"], 0) + 1
    print(f"Captured: {w['title']!r}  {w['url']}")
    print(f"  pattern={w['url_pattern']}  nodes={s['node_count']}{' (truncated)' if s['truncated'] else ''}  {s['walk_ms']}ms")
    print("  roles:", dict(sorted(roles.items(), key=lambda kv: -kv[1])[:10]))
    for f in w["forms"]:
        req = [x["label"] or x["name"] for x in f["fields"] if x["required"]]
        print(f"  form {f['method']} {f['action']}: {len(f['fields'])} fields"
              f"{', required: ' + ', '.join(req) if req else ''}  submit={f['submit']}")
    for t in w["tables"]:
        print(f"  table: {t['headers']} records={t['row_count']} rows_per_record={t.get('rows_per_record', 1)}")
    if w["pagination"]["next"]:
        print(f"  pagination: next -> {w['pagination']['next']['href']}")
    if w["alerts"]:
        print(f"  alerts: {w['alerts']}")
    same = sum(1 for l in w["links"] if l["same_site"])
    print(f"  links: {len(w['links'])} ({same} same-site)")
    print(f"  saved {s['screenshot_path']} (+ .json)")


def main(argv=None):
    from playwright.sync_api import sync_playwright

    ap = argparse.ArgumentParser(description="Capture a web page into a RESTore page model (read-only).")
    ap.add_argument("url")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    ap.add_argument("--login", action="store_true",
                    help="pause so YOU can log in by hand; the session is saved to cache/web/auth_state.json")
    ap.add_argument("--full-page", action="store_true")
    ap.add_argument("--label", action="store_true", help="also run Nemotron labeling + build the Screen Model")
    args = ap.parse_args(argv)

    with sync_playwright() as p:
        browser, ctx = open_browser(p, headed=args.headed or args.login)
        page = ctx.new_page()
        page.goto(args.url, wait_until="domcontentloaded")
        if args.login:
            input("Log in in the browser window, go to the page you want, then press Enter here... ")
            WEB_DIR.mkdir(parents=True, exist_ok=True)
            ctx.storage_state(path=str(AUTH_FILE))
            print(f"session saved to {AUTH_FILE}")
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        snap = capture_page(page, full_page=args.full_page)
        browser.close()
    summarize(snap)

    if args.label:
        from ingest import screen_model
        from ingest.label import label_screen
        labels = label_screen(snap, use_cache=False)
        out_dir = CACHE_DIR / "screens" / snap["snapshot_id"]
        model = screen_model.build(snap, labels, None, out_dir=out_dir, screenshot_path=snap["screenshot_path"])
        (out_dir / "screen.json").write_text(json.dumps(model, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nLABELS  {labels['screen_type']} | mode={labels['mode']} | confidence={labels['confidence']} | "
              f"{len(labels['controls'])} controls | {labels.get('model_ms')} ms")
        print(f"        {labels['purpose']}")
        if labels.get("error"):
            print("        ERROR:", labels["error"], file=sys.stderr)
        print(f"MODEL   {out_dir / 'screen.json'}   (view: python -m ingest.inspect)")


if __name__ == "__main__":
    main()
