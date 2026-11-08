"""Results page: the extracted data exactly as it goes into SpacetimeDB.

Every extraction writes <run>/extract/index.html (self-contained). To serve the newest one:

    python -m extract.view                     # newest run under core/cache/  -> http://127.0.0.1:5070
    python -m extract.view <extract folder> 5070
"""
import json
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent
TABLES = ["record", "entity_schema", "site", "job", "event"]  # + "operations" when operations.json exists
REDUCERS = {"record": "upsert_record", "entity_schema": "upsert_schema", "site": "save_site",
            "job": "start_job / update_job", "event": "log_event", "operations": "API endpoint"}

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RESTore Extract Output</title>
<style>
:root{--bg:#f6f7f9;--panel:#fff;--text:#16181d;--muted:#5d6472;--line:#dfe2e8;--accent:#3b5bdb;--accent-soft:#e7ecff;
--code:#f1f3f6;--ok:#2b8a3e;--warn:#b35c00;--key:#1c5d99;--str:#2b7a3d;--num:#a8460c;--null:#8a8f99}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#111317;--panel:#181b21;--text:#e6e8ec;
--muted:#9aa1ad;--line:#2b3039;--accent:#7c95ff;--accent-soft:#232b45;--code:#1f232b;--ok:#69db7c;--warn:#ffa94d;
--key:#8cc4ff;--str:#8ce99a;--num:#ffc078;--null:#868e96}}
:root[data-theme="dark"]{--bg:#111317;--panel:#181b21;--text:#e6e8ec;--muted:#9aa1ad;--line:#2b3039;--accent:#7c95ff;
--accent-soft:#232b45;--code:#1f232b;--ok:#69db7c;--warn:#ffa94d;--key:#8cc4ff;--str:#8ce99a;--num:#ffc078;--null:#868e96}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1200px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:20px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 16px;word-break:break-all}
.stats{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 12px}
.stat b{display:block;font-size:18px}.stat span{color:var(--muted);font-size:12px}
.tabs{display:flex;flex-wrap:wrap;gap:4px;border-bottom:1px solid var(--line);margin-bottom:12px}
.tab{background:none;border:0;border-bottom:2px solid transparent;padding:8px 12px;color:var(--muted);cursor:pointer;font:inherit}
.tab[aria-selected=true]{color:var(--text);border-color:var(--accent);font-weight:600}
.tab small{color:var(--muted);font-weight:400}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}
.bar .note{color:var(--muted);font-size:13px;flex:1 1 260px}
code{background:var(--code);padding:1px 5px;border-radius:4px;font:12px ui-monospace,SFMono-Regular,Menlo,monospace}
select,input,button.btn{font:inherit;border:1px solid var(--line);background:var(--panel);color:var(--text);border-radius:6px;padding:6px 10px}
button.btn{cursor:pointer}button.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.wrap{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;min-width:900px}td pre{min-width:300px}
th,td{text-align:left;vertical-align:top;padding:8px 10px;border-bottom:1px solid var(--line)}
th{font-size:12px;color:var(--muted);font-weight:600;background:var(--panel);position:sticky;top:0}
th .t{display:block;font-weight:400;font-size:11px}
td.mono{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;white-space:nowrap}
pre{margin:0;font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap;word-break:break-word;
background:var(--code);padding:8px;border-radius:6px;max-height:320px;overflow:auto}
.k{color:var(--key)}.s{color:var(--str)}.n{color:var(--num)}.z{color:var(--null)}
.empty{padding:24px;color:var(--muted);text-align:center}
.toast{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:var(--text);color:var(--bg);padding:8px 14px;
border-radius:6px;opacity:0;transition:opacity .2s;pointer-events:none}.toast.on{opacity:1}
.more{color:var(--muted);padding:10px;text-align:center}
</style></head><body><main>
<h1>Extract output: ready for SpacetimeDB</h1>
<p class="sub" id="sub"></p>
<div class="stats" id="stats"></div>
<div class="tabs" role="tablist" id="tabs"></div>
<div class="bar">
  <span class="note" id="note"></span>
  <select id="entity" aria-label="Entity"></select>
  <input id="q" type="search" placeholder="Search rows" aria-label="Search rows">
  <button class="btn" id="mode" title="Show JSON columns as stored (string) or formatted">JSON: formatted</button>
  <button class="btn" id="copy">Copy table JSON</button>
  <button class="btn primary" id="dl">Download</button>
</div>
<div class="wrap"><table id="grid"></table></div>
<div class="more" id="more"></div>
<div class="toast" id="toast"></div>
</main>
<script type="application/json" id="payload">__PAYLOAD__</script>
<script>
const P = JSON.parse(document.getElementById('payload').textContent);
const TYPES = {record:{id:'u64 (auto)',entity:'string',legacy_id:'string',data_json:'string (JSON)',hash:'string',extracted_at:'timestamp'},
  entity_schema:{name:'string (pk)',fields_json:'string (JSON)',rules_json:'string (JSON)'},
  site:{url:'string (pk)',site_map_json:'string (JSON)',model_json:'string (JSON)',ops_json:'string (JSON)',docs_md:'string',updated_at:'timestamp'},
  job:{id:'u64 (auto)',kind:'string',entity:'string?',status:'string',done:'u32',total:'u32',started_at:'timestamp'},
  event:{id:'u64 (auto)',ts:'timestamp',actor:'string',level:'string',message:'string',data_json:'string (JSON)'},
  operations:{method:'HTTP',path:'route',source:'database | legacy',name:'operation',inputs_json:'inputs',example_json:'real example'}};
let tab = 'record', raw = false, limit = 200;
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function hl(v){ const s = JSON.stringify(v, null, 2), re = /"(?:\\.|[^"\\])*"(?:\s*:)?|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g;
  let out = '', last = 0, m;
  while ((m = re.exec(s))) { const t = m[0];
    const c = t.endsWith(':') ? 'k' : t[0] === '"' ? 's' : /^[tfn]/.test(t) ? 'z' : 'n';
    out += esc(s.slice(last, m.index)) + `<span class="${c}">${esc(t)}</span>`; last = m.index + t.length; }
  return out + esc(s.slice(last)); }
function rows(){ let r = P.tables[tab] || [];
  const e = $('entity').value; if (e && (tab==='record'||tab==='job'||tab==='operations')) r = r.filter(x => x.entity === e);
  if (tab==='entity_schema' && e) r = r.filter(x => x.name === e);
  const q = $('q').value.trim().toLowerCase(); if (q) r = r.filter(x => JSON.stringify(x).toLowerCase().includes(q));
  return r; }
function cell(k, v){
  if (k.endsWith('_json') && typeof v === 'string' && v) {
    if (raw) return `<td><pre>${esc(v)}</pre></td>`;
    try { return `<td><pre>${hl(JSON.parse(v))}</pre></td>`; } catch { return `<td><pre>${esc(v)}</pre></td>`; } }
  if (k === 'docs_md') return `<td>${v ? '<pre>'+esc(v)+'</pre>' : '<span class="z">""</span>'}</td>`;
  return `<td class="mono">${v === null || v === undefined ? '<span class="z">null</span>' : esc(v)}</td>`; }
function render(){
  document.querySelectorAll('.tab').forEach(b => b.setAttribute('aria-selected', b.dataset.t === tab));
  const r = rows(), cols = Object.keys(TYPES[tab]);
  $('note').innerHTML = tab === 'operations'
    ? `<b>${r.length}</b> endpoint(s) from <code>operations.json</code>, designed by ${esc(P.designed_by || '?')}.`
    : `<b>${r.length}</b> row(s) for table <code>${tab}</code>, each one a <code>${P.reducers[tab]}</code> call.`;
  $('entity').style.display = ['record','job','entity_schema','operations'].includes(tab) ? '' : 'none';
  $('grid').innerHTML = '<thead><tr>' + cols.map(c => `<th>${c}<span class="t">${TYPES[tab][c]}</span></th>`).join('') + '</tr></thead><tbody>' +
    (r.length ? r.slice(0, limit).map(x => '<tr>' + cols.map(c => cell(c, x[c])).join('') + '</tr>').join('')
              : `<tr><td class="empty" colspan="${cols.length}">No rows</td></tr>`) + '</tbody>';
  $('more').textContent = r.length > limit ? `Showing ${limit} of ${r.length}. Search or filter to narrow, or download the full table.` : ''; }
function toast(t){ const el = $('toast'); el.textContent = t; el.classList.add('on'); setTimeout(() => el.classList.remove('on'), 1400); }
$('sub').textContent = `${P.site}  ·  extracted ${P.generated}  ·  ${P.out_dir}`;
const ents = [...new Set((P.tables.record||[]).map(r => r.entity))];
$('stats').innerHTML = ents.map(e => `<div class="stat"><b>${P.tables.record.filter(r=>r.entity===e).length}</b><span>${esc(e)} records</span></div>`).join('')
  + `<div class="stat"><b>${(P.tables.event||[]).length}</b><span>events</span></div>`
  + `<div class="stat"><b>${P.duplicates}</b><span>possible duplicate groups</span></div>`
  + (P.check ? `<div class="stat"><b style="color:var(--${P.check.ok?'ok':'warn'})">${P.check.text}</b><span>matches the mock data</span></div>` : '');
$('entity').innerHTML = '<option value="">All entities</option>' + ents.map(e => `<option>${esc(e)}</option>`).join('');
$('tabs').innerHTML = P.order.map(t => `<button class="tab" role="tab" data-t="${t}">${t} <small>${(P.tables[t]||[]).length}</small></button>`).join('');
$('tabs').onclick = e => { const b = e.target.closest('.tab'); if (b) { tab = b.dataset.t; limit = 200; render(); } };
$('entity').onchange = render; $('q').oninput = render;
$('mode').onclick = () => { raw = !raw; $('mode').textContent = 'JSON: ' + (raw ? 'as stored' : 'formatted'); render(); };
$('copy').onclick = async () => { try { await navigator.clipboard.writeText(JSON.stringify(rows(), null, 2)); toast('Copied ' + rows().length + ' rows'); }
  catch { toast('Copy blocked by the browser: use Download'); } };
$('dl').onclick = () => { const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(rows(), null, 2)], {type:'application/json'}));
  a.download = tab + '.json'; a.click(); URL.revokeObjectURL(a.href); };
render();
</script></body></html>"""


def render(extract_dir):
    """Write <extract_dir>/index.html from spacetime/*.json (+ check.json if present)."""
    d = Path(extract_dir)
    tables = {}
    for t in TABLES:
        p = d / "spacetime" / f"{t}.json"
        tables[t] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    order, designed_by = list(TABLES), None
    op_path = d.parent / "operations.json"
    if op_path.exists():
        doc = json.loads(op_path.read_text(encoding="utf-8"))
        m = doc.get("designed_by", {})
        designed_by = f"Nemotron ({m.get('model')})" if m.get("by") == "nemotron" else "code-only rules"
        tables["operations"] = [{"method": o["method"], "path": o["path"], "source": o["source"], "name": o["name"],
                                 "entity": o["entity"], "inputs_json": json.dumps(o.get("inputs", [])),
                                 "example_json": json.dumps(o.get("example", {}))} for o in doc["operations"]]
        order.insert(1, "operations")
    check = None
    cp = d / "check.json"
    if cp.exists():
        rep = json.loads(cp.read_text(encoding="utf-8"))
        right = sum(c["fields_checked"] - c["fields_wrong"] for c in rep.values())
        total = sum(c["fields_checked"] for c in rep.values())
        ok = all(c["accuracy"] == 100.0 and not c["extra"] and not c["missing"] for c in rep.values())
        check = {"ok": ok, "text": f"{right}/{total}"}
    dups = d / "duplicates.json"
    site = tables["site"][0]["url"] if tables["site"] else ""
    generated = max((r["extracted_at"] for r in tables["record"]), default="")
    payload = {"site": site, "generated": generated, "out_dir": str(d), "order": order, "tables": tables,
               "designed_by": designed_by,
               "reducers": REDUCERS, "check": check,
               "duplicates": len(json.loads(dups.read_text())) if dups.exists() else 0}
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    out = d / "index.html"
    out.write_text(PAGE.replace("__PAYLOAD__", blob), encoding="utf-8")
    return out


def newest_extract_dir():
    found = [p for p in (CORE / "cache").glob("*/*/extract") if (p / "spacetime").is_dir()]
    if not found:
        raise SystemExit("No extract output yet. Run: python -m mock_sites.run clinic")
    return max(found, key=lambda p: p.stat().st_mtime)


def serve(extract_dir=None, port=5070):
    d = Path(extract_dir) if extract_dir else newest_extract_dir()
    render(d)
    handler = partial(SimpleHTTPRequestHandler, directory=str(d))
    handler.log_message = lambda *a: None
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"Extract output for {d}\n  http://127.0.0.1:{port}/   (Ctrl+C to stop)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    serve(argv[0] if argv else None, int(argv[1]) if len(argv) > 1 else 5070)


if __name__ == "__main__":
    main()
