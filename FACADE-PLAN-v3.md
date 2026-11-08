# FACADE: Agentic Migration Off Legacy Web Systems
**HackUTD 2026 · Primary: NVIDIA Nemotron Prize Track · Also: 8090.AI Legacy Modernization, SpacetimeDB**
**Plan v3 (replaces the earlier "modern UI overlay" plan). Written 10:15 PM Saturday.**

> This is the single source of truth. If you change a format in Section 7, update this file and tell the team.

---

## Contents
1. [The pitch in one breath](#1-the-pitch-in-one-breath)
2. [The problem](#2-the-problem)
3. [What Facade is (and honestly is not)](#3-what-facade-is-and-honestly-is-not)
4. [Walkthrough: a mock example](#4-walkthrough-a-mock-example)
5. [How it meets each track](#5-how-it-meets-each-track)
6. [Architecture](#6-architecture)
7. [Shared formats (contracts)](#7-shared-formats-contracts)
8. [The demo legacy app: ClinicPro 2005](#8-the-demo-legacy-app-clinicpro-2005)
9. [Roles and tasks](#9-roles-and-tasks)
10. [Repo, setup, environment](#10-repo-setup-environment)
11. [Timeline, checkpoints, cut list](#11-timeline-checkpoints-cut-list)
12. [Demo script](#12-demo-script)
13. [Judge Q&A](#13-judge-qa)
14. [Risks and rules](#14-risks-and-rules)

---

## 1. The pitch in one breath

> **Facade does the first and hardest part of leaving legacy software, automatically. Point it at an old web system and Nemotron agents explore it, work out what data and rules it holds, move that data into a modern database you own, and keep the old and new systems in sync while you switch over. It also gives the old system an API and MCP it never had.**

It doesn't clone the old website. It takes the **contents and structure** out of the old system and puts them into a modern one.

---

## 2. The problem

- Businesses run on **old web systems with no API and no export**: practice-management portals, vendor systems, internal admin tools, government portals.
- Getting off them is a **multi-year, high-risk project**, mostly because nobody fully knows what's inside, the data is trapped behind screens, and both systems must run side by side during the switch.
- Meanwhile **people act as the integration**: retyping data between systems, copying records, checking pages by hand.
- Data lock-in is real: the vendor won't export, charges for it, or has stopped supporting the product.

**Who it's for:** a clinic, a small business, or an IT team stuck on legacy web software, and the agencies they hire to migrate them.

---

## 3. What Facade is (and honestly is not)

### What it does
1. **Explore:** an agent clicks through the old system like a new employee and maps every page, form, table and link.
2. **Understand:** Nemotron works out the **data model** (entities, fields, types, required fields, allowed values, relationships), **rules** it observed, and the **operations** (list, get, create, update).
3. **Build the modern side:** schema plus records in **SpacetimeDB**, a clean **modern app** generated from the schema, and an **API + MCP**.
4. **Migrate the data:** the Operator agent extracts every record into the new database, handling paging, timeouts, re-login and duplicates.
5. **Keep in sync:** an edit in the modern app is written into the old system by the Operator, then verified. The old system's rules still apply.
6. **Document:** site map, data dictionary and rules, which serve as the spec for the eventual full replacement.

### What it honestly does NOT do
- It **cannot see hidden server logic** (billing formulas, nightly jobs, integrations, permissions). Facade maps what's visible and flags what it can't see.
- The modern app is a **working starting point plus a safety net**, not a guaranteed full replacement.
- Use only on systems you own or are authorized to automate. No CAPTCHA bypassing. Credentials are entered by the user.

Being upfront about this builds trust with judges, especially 8090.

---

## 4. Walkthrough: a mock example

**Sunrise Dental** has used **ClinicPro 2005** for 18 years: 6,000 patients, 40,000 appointments, no export, no API.

| Step | What happens |
|---|---|
| **Start** | Office manager opens the Facade Console, pastes the ClinicPro URL, logs in herself |
| **1. Explore (~2 min)** | Agent: home menu → Patients (search + table, 25/page, "Next") → a patient detail → Edit form (looks, never saves) → Schedule (day calendar) → appointment detail. The site map grows live in the Console |
| **2. Understand (~1 min)** | `Patient {name* text, dob date MM/DD/YYYY, phone, insurance_id}`, `Appointment {date, time, provider ∈ {Dr. Lee, Dr. Patel, Hyg. Kim}, patient → Patient, status ∈ {Scheduled, Confirmed, No-show}}`. Rules: "Name required", "Delete asks for confirmation", "No Sunday appointments" |
| **3. Build** | SpacetimeDB schema, modern app (patient list, patient page, calendar), API docs page. Empty so far |
| **4. Migrate** | Progress bar: Patients 1,250 / 6,000. Handles a session timeout (re-login, resume), flags two "John Smith, 1971-03-02" as possible duplicates |
| **5. Sync** | Receptionist books in the modern app → agent books it in ClinicPro → verifies → ✓. Try a Sunday → ClinicPro rejects it → the modern app shows "Old system rule: no Sunday appointments" |
| **Result** | Data in a database they own · docs/spec for the vendor · API for their booking site · a modern app staff can use now, with the old system as a safety net |

---

## 5. How it meets each track

### NVIDIA: "Use Nemotron Beyond a Chatbot"
| Requirement | How Facade meets it |
|---|---|
| **Beyond a chatbot** | Input is a URL, not a conversation. Agents explore, build, migrate and sync on their own; sync runs continuously with no prompts |
| **Multi-step workflows** | Exploring an unknown site (plan → navigate → interpret → decide next); migrating thousands of records (paging, detail pages, recovery); write-through (navigate → fill → submit → verify → report) |
| **Tool integration** | Browser (Playwright), the legacy site's own pages and requests, SpacetimeDB (HTTP + live subscriptions), generated API + MCP. The agent picks the right tool per step and verifies results |
| **Real-world applicability** | Data lock-in and risky migrations are real, expensive problems; a concrete clinic story with measurable output (records migrated, rules found) |

**Nemotron models (NVIDIA NIM, `https://integrate.api.nvidia.com/v1`):**
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`: reads each page (ARIA tree + screenshot), labels it, maps fields
- `nvidia/nemotron-3-super-120b-a12b`: plans exploration, infers the data model, rules and operations, handles recovery decisions

**Key design principle: Nemotron learns once, code runs fast.** Nemotron works out *how* to read and write each page type (field-to-element mappings, recipes). The Operator then runs those recipes quickly for thousands of records, and calls Nemotron again only when something unexpected happens. This makes it fast, cheap and reliable, and it's a strong technical point for judges.

### 8090: understand / improve / replace
- **Understand:** site map, data dictionary, observed rules, docs
- **Improve:** API + MCP + a modern app usable immediately
- **Replace:** data migrated, plus a spec and side-by-side sync for a gradual switch (the strangler-fig pattern)

### SpacetimeDB
It **is** the modern system's backend: the migrated data, the schema, the sync queue and the live activity stream. The modern app and Console update in real time through subscriptions.

---

## 6. Architecture

```
                    ┌──────────────────────── ClinicPro 2005 (old web app, Flask, localhost:5005) ─┐
                    │  server-rendered HTML · sessions · pagination · rules · NO API              │
                    └──────────▲───────────────────────────────────────────▲──────────────────────┘
                               │ Playwright (read-only)                     │ Playwright (read + write)
┌──────────────────────────────┴───────────────┐        ┌────────────────────┴───────────────────────────┐
│ EXPLORER + UNDERSTAND (Daniel, Python)        │        │ OPERATOR (agent person, Python)                 │
│ capture_web → Screen Model (source "dom")     │ model, │ migrate: list → detail → extract → upsert       │
│ label (Nemotron) → explorer loop (Nemotron)   │ ops,   │ write-through: change_request → fill → submit   │
│ → site map → data model + rules + ops + docs  │──────▶ │   → verify → done/failed                        │
└──────────────────────────────┬───────────────┘ recipes└────────────────────┬───────────────────────────┘
                               │ HTTP (reducers)                            │ HTTP (reducers + SQL)
                               ▼                                            ▼
                ┌──────────────────────────── SpacetimeDB (Maincloud) ─────────────────────────────┐
                │ site · entity_schema · record · change_request · job · event                     │
                └──────────▲──────────────────────────────▲──────────────────────────▲─────────────┘
                           │ TS SDK (live subscriptions)  │ TS SDK                    │ HTTP SQL / reducers
              ┌────────────┴─────────────┐   ┌────────────┴───────────┐   ┌───────────┴──────────────┐
              │ FACADE CONSOLE (frontend)│   │ MODERN APP (frontend)  │   │ API + MCP (Spacetime     │
              │ URL in · live site map · │   │ generic list/detail/   │   │ person) FastAPI + MCP    │
              │ model · progress · log   │   │ edit from entity_schema│   │ tools, docs page         │
              └──────────────────────────┘   └────────────────────────┘   └──────────────────────────┘
                                     NVIDIA NIM (Nemotron) ◀── Explorer + Operator
```

### Stack
| Part | Tech |
|---|---|
| Agents / pipeline | Python 3.9+ (Daniel's Mac has 3.9), `openai`, `playwright`, `pillow`, `python-dotenv`, `requests` |
| AI | Nemotron via NVIDIA NIM (build.nvidia.com key) |
| Legacy target | Flask + Jinja + SQLite (ClinicPro 2005) |
| Modern backend | SpacetimeDB on Maincloud, module in TypeScript; Python uses the HTTP API (no Python SDK) |
| Console + modern app | React + TypeScript + Vite, SpacetimeDB TS SDK |
| API / MCP | FastAPI + the official Python `mcp` SDK |

**Everything runs on Mac.** No Windows needed anymore.

---

## 7. Shared formats (contracts)

> **Daniel publishes fake versions of 7.2–7.4 in `shared/fixtures/` within the first hour** so the Operator and frontend can build before the explorer works.

### 7.1 Page snapshot → Screen Model (already built)
The existing Screen Model (`schema_version: 1`) with `screen.source = "dom"`. Nodes have ARIA roles, rects, values, `ai` labels, and `locator`. For web, the locator becomes:
```json
"locator": { "css": "#lname", "label": "Last Name", "role": "textbox", "name": "Last Name" }
```
(Prefer `label`/`role`+`name` via Playwright's `get_by_role` / `get_by_label`; `css` as backup.)

### 7.2 Site Map (Explorer → everyone)
```json
{
  "site": "http://localhost:5005",
  "explored_at": "2026-11-07T23:40:00Z",
  "pages": [
    { "id": "patient_list", "url_pattern": "/patients?page={n}&q={q}", "screen_type": "patient_search",
      "purpose": "Search and browse patients", "entity": "Patient", "kind": "list",
      "pagination": { "next": { "role": "link", "name": "Next >>" }, "page_size": 25 },
      "row_link": { "role": "link", "column": "Name", "goes_to": "patient_detail" } },
    { "id": "patient_detail", "url_pattern": "/patients/{id}", "entity": "Patient", "kind": "detail" },
    { "id": "patient_edit", "url_pattern": "/patients/{id}/edit", "entity": "Patient", "kind": "form" },
    { "id": "appt_new", "url_pattern": "/appointments/new?patient_id={id}", "entity": "Appointment", "kind": "form" }
  ],
  "edges": [ { "from": "patient_list", "to": "patient_detail", "via": "row link" } ],
  "unexplored": [ "Billing", "Reports" ],
  "notes": [ "Session expires after ~10 minutes" ]
}
```

### 7.3 Data Model + Rules (Understand → Operator, Spacetime, frontend)
```json
{
  "entities": [
    { "name": "Patient", "key": "legacy_id", "source_pages": ["patient_detail", "patient_edit"],
      "fields": [
        { "name": "last_name", "label": "Last Name", "type": "string", "required": true,
          "read": { "page": "patient_detail", "label": "Last Name" },
          "write": { "page": "patient_edit", "label": "Last Name" } },
        { "name": "dob", "label": "Date of Birth", "type": "date", "format": "MM/DD/YYYY",
          "read": { "page": "patient_detail", "label": "DOB" } },
        { "name": "provider", "label": "Provider", "type": "enum",
          "values": ["Dr. Lee", "Dr. Patel", "Hyg. Kim"] }
      ] },
    { "name": "Appointment", "key": "legacy_id",
      "relations": [ { "field": "patient_id", "to": "Patient" } ], "fields": [] }
  ],
  "rules": [
    { "id": "r1", "entity": "Patient", "text": "Last name is required", "source": "required marker on edit form" },
    { "id": "r2", "entity": "Appointment", "text": "No appointments on Sundays", "source": "error message seen" }
  ],
  "not_visible": [ "Billing calculations", "Permissions" ]
}
```

### 7.4 Operations (Understand → Operator, API/MCP)
```json
{
  "operations": [
    { "name": "list_patients", "kind": "list", "entity": "Patient", "inputs": { "q": "string?" },
      "steps": [ "goto patient_list", "for each page: read rows, follow Next" ] },
    { "name": "get_patient", "kind": "get", "entity": "Patient", "inputs": { "legacy_id": "string" },
      "steps": [ "goto patient_detail(legacy_id)", "read fields by label" ] },
    { "name": "update_patient", "kind": "update", "entity": "Patient", "risk": "write",
      "steps": [ "goto patient_edit(legacy_id)", "fill fields by label", "click Save",
                 "verify: patient_detail shows new values" ] },
    { "name": "create_appointment", "kind": "create", "entity": "Appointment", "risk": "write",
      "steps": [ "goto appt_new(patient_id)", "fill date/time/provider/reason", "click Book",
                 "verify: success message or read error text" ] }
  ]
}
```

### 7.5 SpacetimeDB tables (generic, so no per-app code generation)
| Table | Fields | Written by |
|---|---|---|
| `site` | `url (pk)`, `site_map_json`, `model_json`, `ops_json`, `updated_at` | Explorer |
| `entity_schema` | `name (pk)`, `fields_json`, `rules_json` | Explorer |
| `record` | `id (pk, auto)`, `entity`, `legacy_id`, `data_json`, `hash`, `origin` (legacy/modern), `synced_at` | Operator |
| `change_request` | `id (pk, auto)`, `entity`, `legacy_id?`, `op` (create/update), `data_json`, `status` (pending/running/done/failed), `error?`, `created_at` | Modern app / API create; Operator updates |
| `job` | `id (pk, auto)`, `kind` (explore/migrate/sync), `status`, `done`, `total`, `started_at` | Explorer / Operator |
| `event` | `id (pk, auto)`, `ts`, `actor` (explorer/operator/user), `level`, `message`, `data_json` | Everyone |

**Reducers:** `save_site`, `upsert_schema`, `upsert_record` (by entity + legacy_id), `request_change`, `claim_change`, `finish_change`, `start_job`, `update_job`, `log_event`.
**Python access:** `POST /v1/database/facade/call/<reducer>` (JSON array of args) and `POST /v1/database/facade/sql`. Short timeouts; never block the agent on SpacetimeDB.

### 7.6 Event messages (for the Console's live log)
`event.message` is human-readable; `data_json` carries details: `{"page":"patient_list","action":"navigate","nemotron_ms":2140}`, `{"entity":"Patient","legacy_id":"P0042","result":"upserted"}`, `{"change_id":7,"result":"failed","error":"Old system rule: no Sunday appointments"}`.

---

## 8. The demo legacy app: ClinicPro 2005

Owner: **SpacetimeDB person, first task.** Fully fake data, built by us, honest in the pitch.

**Must look and behave like 2005:**
- Gray `#D4D0C8` background, navy table headers, Verdana 11px, table layouts, beveled buttons, a top nav bar
- **Server-rendered HTML only, no JSON API**
- `/login` with a session that **expires after ~10 minutes** (lets us show re-login recovery)
- `/patients?page=&q=`: search + table, 25 per page, `<< Prev | Next >>`
- `/patients/<id>`: detail (label: value table)
- `/patients/<id>/edit` and `/patients/new`: form, **Last Name required** (red asterisk + server error), DOB `MM/DD/YYYY` validated
- `/schedule?date=`: day view table of appointments
- `/appointments/new?patient_id=`: date, time, provider `<select>`, reason. **Rejects Sundays** and double-booked slots with an error message
- `/appointments/<id>`: detail + status change
- Seed with Faker: **~300 patients, ~1,500 appointments**, plus 2 deliberate near-duplicate patients
- Runs on `localhost:5005`, SQLite file, one `python app.py`

Stretch: point the explorer at a real open-source app (e.g., OpenEMR in Docker) to show generality.

---

## 9. Roles and tasks

### 👤 Daniel: Explorer + Understand (NVIDIA core)
**Owns:** `core/ingest/` (existing) + `core/explore/` (new)

| # | Task | Done when |
|---|---|---|
| 1 | Publish fake `site_map.json`, `data_model.json`, `operations.json` in `shared/fixtures/` | Operator + frontend unblocked (**first hour**) |
| 2 | `pip install playwright && playwright install chromium` | Browser launches |
| 3 | `capture_web.py`: page → ARIA tree (`locator("body").aria_snapshot()` and/or role queries), screenshot, links, forms (labels, inputs, required, options), tables (headers + rows) → Screen Model `source: "dom"` | Works on any page; existing `label.py` labels it |
| 4 | Explorer loop: Nemotron Super picks the next action from {follow link, open row, next page, open form (look only), go back, stop} with a page budget (~25) and **no submits during exploration** | Maps ClinicPro on its own into a site map |
| 5 | Understand: one Nemotron call over the captured forms/tables/pages → data model + rules + operations (formats 7.3, 7.4) with validation (labels must exist on pages) | Correct Patient/Appointment model, rules r1/r2 found |
| 6 | Field mappings for fast extraction: for each entity field, how to read it on the detail page (label → value cell) | Operator can extract without calling Nemotron |
| 7 | Write results to SpacetimeDB (`save_site`, `upsert_schema`) + `log_event` for each step | Console shows the live map |
| 8 | Docs: site map + data dictionary + rules + "not visible" list as Markdown/HTML | Viewable in Console/API docs |
| 9 | Caching: save the explored model so the demo can reuse it if live exploration is slow | Demo-safe |

### 👤 Agent person: Operator (migration + sync)
**Owns:** `core/operator/`

| # | Task | Done when |
|---|---|---|
| 1 | Playwright session manager: login (credentials from `.env`, entered by the user), detect logged-out pages, re-login, resume | Survives the 10-min session timeout |
| 2 | Generic extractor driven by the data model's `read` mappings: list page → paging → detail pages → field values | Extracts all ClinicPro patients into Python dicts |
| 3 | Migration job: upsert records to SpacetimeDB (`upsert_record`), progress via `update_job`, events via `log_event`, content hash per record | Modern app fills live; resumable |
| 4 | Duplicate check (same name + DOB) → flag in `event`, don't merge | The planted duplicates are flagged |
| 5 | Write-through worker: poll `change_request` (pending) via SQL → `claim_change` → run operation recipe (fill by label, submit) → **verify** by re-reading → `finish_change` (done/failed with the old system's error text) | Edit in the modern app shows up in ClinicPro, verified |
| 6 | Nemotron fallback: if a recipe step fails (element not found, unexpected page), send the page snapshot to Nemotron to choose a fix, retry once, else fail clearly | Recovers from one deliberate change |
| 7 | Stretch: old → new change detection (re-scan list pages, compare hashes) | An edit made in ClinicPro appears in the modern app |

### 👤 Frontend person: Console + Modern App
**Owns:** `web/` (React + TS + Vite, SpacetimeDB TS SDK)

| # | Task | Done when |
|---|---|---|
| 1 | Scaffold + SpacetimeDB bindings (`spacetime generate --lang typescript`) | Subscribes to tables |
| 2 | **Console:** URL input + "Explore" (starts a job via a small backend call or a `job` row), **live site map graph** from `site.site_map_json`, **data model view** (entities, fields, rules, "not visible"), **progress bars** from `job`, **live event log** from `event` | Watching exploration live is compelling |
| 3 | **Modern app (generic):** from `entity_schema`, render list (search, sort), detail, edit/create forms with field types, required markers, enum dropdowns | Works for Patient and Appointment with no entity-specific code |
| 4 | Edits create `change_request` rows; show status pending → done ✓ / failed with the old system's error | Write-through moment works on stage |
| 5 | Polish: clean modern design; optional "keeps the old app's identity" accent color (from the old style profile) | Looks great on a projector |

### 👤 SpacetimeDB person: ClinicPro + Modern Backend + API/MCP
**Owns:** `legacy/clinicpro/`, `spacetime/`, `core/store/`, `api/`, pitch

| # | Task | Done when |
|---|---|---|
| 1 | **Build ClinicPro 2005** (Section 8) | Running on :5005 with seeded data (**by +2h**) |
| 2 | SpacetimeDB module (TypeScript): tables + reducers (7.5); publish to Maincloud (redeem the HackUTD credit) | Reducers callable |
| 3 | `core/store/spacetime.py`: identity token, `call(reducer, args)`, `sql(query)`, short timeouts | Explorer + Operator use it |
| 4 | API (FastAPI): `GET /patients`, `GET /patients/{id}`, `POST /appointments`, `PATCH /patients/{id}`. Reads from SpacetimeDB; writes create a `change_request` and wait for done/failed | Docs page at `/docs` works |
| 5 | MCP server (Python `mcp` SDK): the same operations as tools | An MCP client can call `search_patients` |
| 6 | Pitch slides, timing, backup video at freeze | 3-minute run-through |

---

## 10. Repo, setup, environment

```
Facade/
├── FACADE-PLAN-v3.md
├── core/
│   ├── .env.example / .env (git-ignored)
│   ├── ingest/        # existing: nemotron client, label, style, screen_model, inspector, selftest (Daniel)
│   ├── explore/       # NEW: capture_web, explorer loop, understand, docs (Daniel)
│   ├── operator/      # NEW: session, extractor, migration, write-through (agent person)
│   └── store/         # spacetime.py HTTP helper (Spacetime person)
├── legacy/clinicpro/  # Flask legacy app (Spacetime person)
├── spacetime/         # SpacetimeDB module, TypeScript (Spacetime person)
├── api/               # FastAPI + MCP (Spacetime person)
├── web/               # Console + modern app (frontend)
└── shared/
    ├── fixtures/      # fake site_map / data_model / operations + existing screen fixtures
    └── prompts/       # Nemotron prompts (versioned)
```

### `.env` additions
```
CLINICPRO_URL=http://localhost:5005
CLINICPRO_USER=admin          # demo app credentials, typed in by a human
CLINICPRO_PASS=
SPACETIME_HOST=https://maincloud.spacetimedb.com
SPACETIME_DB=facade
SPACETIME_TOKEN=
EXPLORE_PAGE_BUDGET=25
```
**Never commit `.env`, `core/cache/`, or `_to_delete/`.** Each person works on their own branch; merge to `main` at checkpoints after an end-to-end check.

### Setup
```bash
cd core && source .venv/bin/activate          # Mac (Windows: .venv\Scripts\activate)
pip install -r requirements.txt playwright fastapi uvicorn mcp
playwright install chromium
python -m ingest.selftest                     # still passes
```

---

## 11. Timeline, checkpoints, cut list
*(Hours from 10:15 PM. Adjust to the actual submission deadline.)*

| When | Must work | Who |
|---|---|---|
| **+1h** | Formats agreed; fake site map / model / operations published; everyone building | All |
| **+2h** | ClinicPro running with data; `capture_web` produces Screen Models of its pages | Spacetime, Daniel |
| **+3h** | SpacetimeDB module live; Console subscribes; Operator logs in + extracts one patient | Spacetime, frontend, agent |
| **+5h** | Explorer maps ClinicPro on its own; data model + rules correct | Daniel |
| **+7h** | Full migration: all patients (+ appointments) in SpacetimeDB; modern app shows them live | Agent, frontend |
| **+9h** | Write-through: edit in the modern app → ClinicPro updates → verified; Sunday rule rejection shown | Agent, frontend |
| **+10h** | API docs + MCP; generated docs page | Spacetime, Daniel |
| **+11h** | 🔒 **Feature freeze**: cache the explored model, rehearse 3×, record backup video | All |

### Cut list (in this order if behind)
1. MCP (keep the API)
2. Old → new change detection (keep new → old write-through)
3. Real open-source second app (keep ClinicPro only)
4. Generated docs page (keep the data model view in the Console)
5. Appointments migration (keep Patients)

**Never cut:** live exploration with the site map growing, migration filling the modern app, the write-through moment, and the Nemotron activity log.

---

## 12. Demo script (3 minutes)

| Time | Beat |
|---|---|
| 0:00–0:20 | **Problem:** "This clinic has 18 years of data trapped in software with no export and no API. Leaving it normally takes years." Show ClinicPro 2005 |
| 0:20–1:00 | **Explore:** paste the URL. The site map builds itself live; Nemotron's notes in the log ("patient search page, 25 per page, row opens details") |
| 1:00–1:25 | **Understand:** the data model + rules appear: "Last name required", "No Sundays", plus "Not visible: billing logic" (honesty) |
| 1:25–2:00 | **Migrate:** progress bar; the modern app fills live; a session timeout is recovered; duplicates flagged |
| 2:00–2:35 | **Sync:** edit a patient's phone in the modern app → on the screen next to it, **ClinicPro updates itself** → ✓ verified. Book a Sunday → "Old system rule: no Sunday appointments" |
| 2:35–2:50 | **API/MCP:** the docs page; one call returns real migrated data |
| 2:50–3:00 | **Close:** "Facade turns years of migration groundwork into minutes: map it, move it, keep it in sync, and switch over safely. Built on Nemotron agents, self-hostable as NIM." |

---

## 13. Judge Q&A

| Question | Answer |
|---|---|
| "How is this different from Skyvern / Integuru / browser agents?" | Those help you **use** a legacy system (automate tasks, build integrations). Facade gets you **off** it: whole-system discovery, a data model and rules, data migration into a database you own, and side-by-side sync for a safe switch |
| "Doesn't it miss hidden business logic?" | Yes, and it says so. It maps what's visible, lists what isn't, and keeps the old system as the source of truth during the switch, so its rules still apply (e.g. the Sunday rejection) |
| "Is it fast enough for real data?" | Nemotron learns each page type once; extraction then runs as fast browser code, with Nemotron only for surprises |
| "Is this legal?" | For systems you own or are authorized to automate (your own data). No CAPTCHA bypassing; credentials entered by the user |
| "How do you know the data is right?" | Every write is verified by re-reading the old system; records carry hashes; duplicates are flagged, not merged |
| "Privacy?" | Hackathon uses hosted NIM; production runs Nemotron as a self-hosted NIM so data never leaves the premises |
| "Why Nemotron?" | Nano Omni reads pages (ARIA + screenshot) quickly; Super handles planning, the data model and recovery; NIM gives a cloud-to-on-prem path |

---

## 14. Risks and rules

| Risk | Mitigation | Owner |
|---|---|---|
| Live exploration slow or wrong on stage | Page budget, cached model fallback, warm run before judging | Daniel |
| Nemotron JSON errors | Existing validation + repair retry + fallback | Daniel |
| Extraction too slow | Field mappings, no Nemotron per record, page_size 25, modest seed size | Agent |
| Write-through fails silently | Always verify by re-reading; show failed status with the old system's error | Agent |
| SpacetimeDB hiccup | Python never blocks on it; local JSON cache for the model | Spacetime |
| Scope creep | Cut list; feature freeze at +11h | All |

### Team rules
1. **NVIDIA first.** Anything that makes the agent demo fragile gets cut.
2. **No app-specific code** in Explorer/Operator. ClinicPro-only logic is not allowed; it must work from the site map, data model and operations.
3. **Formats are law.** Change Section 7 only after telling the team; update fixtures the same minute.
4. **Build against fixtures first**, real data second.
5. **Explorer never submits forms.** Only the Operator writes, and only from change requests or the migration job, always verified.
6. **Log every Nemotron call** to `event`. It's our proof for judges.
7. **Never commit `.env`**, keys, `core/cache/`, or `_to_delete/`.
8. **Post status in chat every ~2 hours:** done / doing / blocked.
