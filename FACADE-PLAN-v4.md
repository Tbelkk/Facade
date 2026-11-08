# FACADE: Legacy Website → Database + API + MCP, built by Nemotron agents
**HackUTD 2026 · Primary: NVIDIA Nemotron Prize Track · Also: 8090.AI Legacy Modernization, SpacetimeDB**
**Plan v4 (replaces v3). Written 10:30 PM Saturday.**

> Single source of truth. If you change a format in Section 7, update this file and tell the team.

---

## Contents
1. [The pitch](#1-the-pitch)
2. [The problem](#2-the-problem)
3. [Scope: what we build and what we cut](#3-scope-what-we-build-and-what-we-cut)
4. [Walkthrough: a mock example](#4-walkthrough-a-mock-example)
5. [How it meets each track](#5-how-it-meets-each-track)
6. [Architecture](#6-architecture)
7. [Shared formats between components](#7-shared-formats-between-components)
8. [Demo target: ClinicPro 2005](#8-demo-target-clinicpro-2005)
9. [Roles and tasks](#9-roles-and-tasks)
10. [Repo, setup, environment](#10-repo-setup-environment)
11. [Timeline, checkpoints, cut list](#11-timeline-checkpoints-cut-list)
12. [Demo script](#12-demo-script)
13. [Judge Q&A](#13-judge-qa)
14. [Risks and team rules](#14-risks-and-team-rules)

---

## 1. The pitch

> **Point RESTore at a legacy website. Nemotron agents explore the whole system, extract its data into a modern database, and generate an API and an MCP server for it. Your data is free and usable, and you never touch the old system's code.**

**Outputs, from just a URL:**
1. **A modern database** (SpacetimeDB) holding the system's data, with a typed schema the agents discovered
2. **A REST API**: fast reads from the database, plus write operations the agent performs live on the old system and verifies
3. **An MCP server**: the same operations as tools any AI assistant can use
4. **Docs**: data dictionary, observed rules, API reference, generated from what the agents found

**Our edge vs. existing browser-agent tools** (Skyvern, Integuru, Browser Use): those need you to describe each task one at a time. RESTore **discovers the entire system on its own** and turns it into a database, API and MCP in one go.

---

## 2. The problem

- Businesses run on **old web systems with no API and no export**: practice-management portals, vendor systems, internal admin tools, government portals.
- Their data is **trapped behind screens**. Nothing new can connect to it, so **people become the integration**: retyping, copying, checking pages by hand.
- Getting the data out or replacing the system is slow and risky, mostly because nobody knows exactly what's in it.

**Who it's for:** a clinic or small business stuck on legacy web software; the IT team or agency that has to integrate with it or migrate off it.

---

## 3. Scope: what we build and what we cut

### ✅ Build
| # | Piece | What it does |
|---|---|---|
| 1 | **Explore** | Agent navigates the site on its own (read-only) and builds a site map |
| 2 | **Understand** | Nemotron infers the data model (entities, fields, types, required, allowed values, relations), observed rules, and operations |
| 3 | **Extract** | Operator pulls every record into SpacetimeDB: paging, detail pages, re-login, duplicate flags, content hashes |
| 4 | **API** | Reads from the database; 2–3 write operations performed live on the old site by the agent, verified |
| 5 | **MCP** | Same operations as AI tools |
| 6 | **Docs** | Generated from the data model and operations |
| 7 | **Console** | Watch it all happen live: site map, model, progress, data browser, API playground, agent log |

### ❌ Cut (don't build these)
- A generated "modern app" that recreates the old site
- Two-way sync / background change detection
- UI restyling, overlays, Windows desktop capture

### Honest limits (say these in the pitch)
- RESTore sees **what's visible** in the system. Hidden server logic (billing formulas, nightly jobs, permissions) isn't visible; RESTore lists what it couldn't see.
- Use only on systems you own or are authorized to automate. No CAPTCHA bypassing. Credentials are entered by a person.

---

## 4. Walkthrough: a mock example

**Sunrise Dental** has used **ClinicPro 2005** for 18 years: 6,000 patients, 40,000 appointments, no export, no API.

| Step | What happens |
|---|---|
| **Start** | Office manager pastes the ClinicPro URL into the RESTore Console and logs in herself |
| **1. Explore (~2 min)** | The agent opens the menu → Patients (search + table, 25/page, "Next") → a patient's detail page → the Edit form (reads it, never saves) → Schedule → an appointment. The site map grows live |
| **2. Understand (~1 min)** | `Patient {last_name* , first_name, dob MM/DD/YYYY, phone, insurance_id}` · `Appointment {date, time, provider ∈ {Dr. Lee, Dr. Patel, Hyg. Kim}, patient → Patient, status}` · Rules: "Last name required", "No Sunday appointments" · Not visible: billing logic |
| **3. Extract** | Progress bars: Patients 1,250 / 6,000. A session timeout is recovered automatically. Two "John Smith, 1971-03-02" records are flagged as possible duplicates |
| **4. API + MCP** | `GET /patients?name=smith` returns JSON from the database. `POST /appointments` makes the agent book it in ClinicPro, verify it, and return the result. A Sunday booking gets rejected with the old system's own rule message |
| **Result** | Their data in a database they own, an API their booking website can use today, AI assistants that can work with the system, and documentation of what's inside it |

---

## 5. How it meets each track

### NVIDIA: "Use Nemotron Beyond a Chatbot"
| Requirement | How RESTore meets it |
|---|---|
| **Beyond a chatbot** | Input is a URL, not a conversation. Agents explore, extract and execute on their own |
| **Multi-step workflows** | Exploring an unknown system (plan → navigate → interpret → decide next); extracting thousands of records with recovery; write operations (navigate → fill → submit → verify → report) |
| **Tool integration** | Real browser (Playwright), SpacetimeDB (HTTP + live subscriptions), the generated API and MCP. The agent chooses the right action per step and verifies results |
| **Real-world applicability** | Trapped data and missing APIs are real, expensive problems, with a concrete clinic story and measurable output |

**Models (NVIDIA NIM, `https://integrate.api.nvidia.com/v1`):**
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`: reads each page (ARIA tree + screenshot) and labels it
- `nvidia/nemotron-3-super-120b-a12b`: plans exploration, infers the data model, rules and operations, handles recovery

**Design principle: Nemotron learns once, code runs fast.** Nemotron works out *how* to read and write each page type (field mappings, recipes). The Operator runs those quickly for thousands of records and calls Nemotron again only when something unexpected happens.

### 8090: understand / improve / replace
- **Understand:** site map, data dictionary, observed rules, docs
- **Improve:** API + MCP, so the system can finally connect to modern tools
- **Replace:** the data is out in a modern database, the first and hardest step of moving off

### SpacetimeDB
The backend: extracted data, schema, operation queue, job progress and the live activity stream that the Console subscribes to.

---

## 6. Architecture

```
            ┌──────────────── Legacy web system (demo: ClinicPro 2005 on localhost:5005) ───────────────┐
            │  server-rendered HTML · login session · pagination · rules · NO API · NO export           │
            └───────────▲──────────────────────────────────────────────────▲────────────────────────────┘
                        │ Playwright, read-only                             │ Playwright, read + write
┌───────────────────────┴──────────────────┐            ┌───────────────────┴──────────────────────────────┐
│ EXPLORER + UNDERSTAND (Daniel)            │ data model │ OPERATOR (agent person)                           │
│ capture_web → page model (ARIA)           │ operations │ extract(entity): list → pages → details → records │
│ explorer loop (Nemotron picks next step)  │ field maps │ execute(op): fill → submit → verify → result      │
│ understand → model + rules + ops + docs   │──────────▶ │ recovery: re-login, retries, Nemotron fallback    │
└───────────────────────┬──────────────────┘            └───────────────────┬──────────────────────────────┘
                        │ HTTP reducers                                       │ HTTP reducers + SQL
                        ▼                                                     ▼
          ┌──────────────────────────────── SpacetimeDB (Maincloud) ──────────────────────────────────┐
          │ site · entity_schema · record · op_request · job · event                                  │
          └───────────────▲──────────────────────────────────────────────────▲─────────────────────────┘
                          │ TS SDK, live subscriptions                       │ HTTP SQL + reducers
          ┌───────────────┴───────────────────────┐            ┌─────────────┴─────────────────────────┐
          │ FACADE CONSOLE (frontend)             │   calls    │ API (FastAPI) + MCP server            │
          │ URL in · live site map · data model · │ ─────────▶ │ (SpacetimeDB person)                   │
          │ progress · data browser · API         │            │ reads: from SpacetimeDB                │
          │ playground · MCP info · agent log     │            │ writes: op_request → Operator → result │
          └───────────────────────────────────────┘            └───────────────────────────────────────┘
                                   NVIDIA NIM (Nemotron) ◀── Explorer + Operator
```

### Stack
| Part | Tech |
|---|---|
| Agents | Python 3.9+, `openai`, `playwright`, `pillow`, `python-dotenv`, `requests` |
| AI | Nemotron via NVIDIA NIM |
| Database / backend | SpacetimeDB on Maincloud (module in TypeScript); Python uses the HTTP API |
| API / MCP | FastAPI + the official Python `mcp` SDK |
| Console | React + TypeScript + Vite + SpacetimeDB TS SDK |
| Demo target | Flask + SQLite (ClinicPro 2005) |

**Everything runs on Mac.** Windows is no longer needed.

---

## 7. Shared formats between components

> These are the **shapes of the data passed between components**, so four people can build at once. Daniel posts one example of each early so teammates can code against it; real explorer output replaces the examples as soon as it runs.

### 7.1 Page model (Explorer internal)
The existing Screen Model (`schema_version: 1`) with `screen.source = "dom"`: ARIA roles, values, `ai` labels, `locator`. Web locators:
```json
"locator": { "role": "textbox", "name": "Last Name", "label": "Last Name", "css": "#lname" }
```
(Use Playwright `get_by_role` / `get_by_label` first, `css` as backup.)

### 7.2 Site map (Explorer → Console, Operator)
```json
{
  "site": "http://localhost:5005",
  "pages": [
    { "id": "patient_list", "url_pattern": "/patients?page={n}&q={q}", "purpose": "Search and browse patients",
      "entity": "Patient", "kind": "list",
      "pagination": { "next": { "role": "link", "name": "Next >>" }, "page_size": 25 },
      "row_link": { "column": "Name", "goes_to": "patient_detail" } },
    { "id": "patient_detail", "url_pattern": "/patients/{id}", "entity": "Patient", "kind": "detail" },
    { "id": "patient_edit", "url_pattern": "/patients/{id}/edit", "entity": "Patient", "kind": "form" },
    { "id": "appt_new", "url_pattern": "/appointments/new?patient_id={id}", "entity": "Appointment", "kind": "form" }
  ],
  "edges": [ { "from": "patient_list", "to": "patient_detail", "via": "row link" } ],
  "unexplored": [ "Billing", "Reports" ],
  "notes": [ "Session expires after ~10 minutes" ]
}
```

### 7.3 Data model + rules (Explorer → Operator, Backend, Console)
```json
{
  "entities": [
    { "name": "Patient", "key": "legacy_id",
      "fields": [
        { "name": "last_name", "label": "Last Name", "type": "string", "required": true,
          "read":  { "page": "patient_detail", "label": "Last Name" },
          "write": { "page": "patient_edit",   "label": "Last Name" } },
        { "name": "dob", "label": "Date of Birth", "type": "date", "format": "MM/DD/YYYY",
          "read": { "page": "patient_detail", "label": "DOB" } }
      ] },
    { "name": "Appointment", "key": "legacy_id",
      "relations": [ { "field": "patient_id", "to": "Patient" } ],
      "fields": [
        { "name": "provider", "type": "enum", "values": ["Dr. Lee", "Dr. Patel", "Hyg. Kim"],
          "read": { "page": "appt_detail", "label": "Provider" }, "write": { "page": "appt_new", "label": "Provider" } }
      ] }
  ],
  "rules": [
    { "id": "r1", "entity": "Patient", "text": "Last name is required", "source": "required marker on edit form" },
    { "id": "r2", "entity": "Appointment", "text": "No appointments on Sundays", "source": "error message seen" }
  ],
  "not_visible": [ "Billing calculations", "Permissions" ]
}
```

### 7.4 Operations (Explorer → Operator, API/MCP)
```json
{
  "operations": [
    { "name": "search_patients", "kind": "list", "entity": "Patient", "source": "database",
      "inputs": { "name": "string?" } },
    { "name": "get_patient", "kind": "get", "entity": "Patient", "source": "database",
      "inputs": { "legacy_id": "string" } },
    { "name": "update_patient_phone", "kind": "update", "entity": "Patient", "source": "legacy", "risk": "write",
      "inputs": { "legacy_id": "string", "phone": "string" },
      "steps": [ "goto patient_edit(legacy_id)", "fill Phone", "click Save",
                 "verify: patient_detail shows new phone" ] },
    { "name": "create_appointment", "kind": "create", "entity": "Appointment", "source": "legacy", "risk": "write",
      "inputs": { "patient_id": "string", "date": "date", "time": "string", "provider": "enum", "reason": "string?" },
      "steps": [ "goto appt_new(patient_id)", "fill date/time/provider/reason", "click Book",
                 "verify: success message, else return the error text" ] }
  ]
}
```
`source: "database"` = answered from SpacetimeDB (fast). `source: "legacy"` = performed live by the Operator on the old system.

### 7.5 SpacetimeDB tables
| Table | Fields | Written by |
|---|---|---|
| `site` | `url (pk)`, `site_map_json`, `model_json`, `ops_json`, `docs_md`, `updated_at` | Explorer |
| `entity_schema` | `name (pk)`, `fields_json`, `rules_json` | Explorer |
| `record` | `id (pk, auto)`, `entity`, `legacy_id`, `data_json`, `hash`, `extracted_at` | Operator |
| `op_request` | `id (pk, auto)`, `operation`, `inputs_json`, `status` (pending/running/done/failed), `result_json?`, `error?`, `created_at` | API creates; Operator updates |
| `job` | `id (pk, auto)`, `kind` (explore/extract), `entity?`, `status`, `done`, `total`, `started_at` | Explorer / Operator |
| `event` | `id (pk, auto)`, `ts`, `actor` (explorer/operator/api), `level`, `message`, `data_json` | Everyone |

**Reducers:** `save_site`, `upsert_schema`, `upsert_record` (by entity + legacy_id), `request_op`, `claim_op`, `finish_op`, `start_job`, `update_job`, `log_event`.
**Python access:** `POST /v1/database/facade/call/<reducer>` (JSON array of args), `POST /v1/database/facade/sql`. Short timeouts; agents never block on the database.

### 7.6 Events (the Console's live log)
Human-readable `message` + `data_json`, e.g.
`{"page":"patient_list","action":"navigate","nemotron_ms":2140}` · `{"entity":"Patient","legacy_id":"P0042","result":"extracted"}` · `{"op_request":7,"result":"failed","error":"Old system rule: no Sunday appointments"}`

---

## 8. Demo target: ClinicPro 2005

**Why we build it:** the agents work on any site (develop the Explorer against real websites, read-only). For the demo we need a legacy system we're **allowed to extract from and write into**, with no real patients' data, that won't break on stage. Say this openly in the pitch.

**Owner: SpacetimeDB person, first task (by +2h).**
- 2005 look: gray `#D4D0C8`, navy table headers, Verdana 11px, table layouts, beveled buttons, top nav bar
- **Server-rendered HTML only, no JSON API, no export**
- `/login`, session **expires after ~10 minutes** (shows re-login recovery)
- `/patients?page=&q=`: search + table, 25 per page, `<< Prev | Next >>`
- `/patients/<id>`: detail (label: value table) · `/patients/<id>/edit`: form; **Last Name required** (red asterisk + server error); DOB `MM/DD/YYYY` validated
- `/schedule?date=`: day table · `/appointments/<id>`: detail
- `/appointments/new?patient_id=`: date, time, provider `<select>`, reason; **rejects Sundays** and double-booked slots with an error message
- Seed with Faker: ~300 patients, ~1,500 appointments, 2 deliberate near-duplicate patients
- `python app.py` → `localhost:5005`, SQLite

---

## 9. Roles and tasks

### 👤 Daniel: Explorer + Understand (NVIDIA core)
**Owns:** `core/ingest/` (existing) + `core/explore/` (new)

| # | Task | Done when |
|---|---|---|
| 1 | Post one example each of 7.2–7.4 in `shared/formats/` | Teammates know the exact shapes (**~15 min**) |
| 2 | `pip install playwright && playwright install chromium` | Browser launches |
| 3 | `capture_web.py`: real page → ARIA snapshot, screenshot, links, forms (labels, inputs, required, options), tables (headers + rows) → page model (`source: "dom"`) → existing `label.py` | Works on real websites |
| 4 | Explorer loop: Nemotron Super chooses {follow link, open row, next page, open form (read only), back, stop}; page budget ~25; **never submits forms** | Maps a real site and ClinicPro into a site map |
| 5 | Understand: Nemotron over captured pages → data model + rules + operations; validate (labels must exist on the pages) | Correct Patient/Appointment model; rules found |
| 6 | Field mappings per entity (how to read each field on detail pages; how to fill it on forms) | Operator extracts without Nemotron per record |
| 7 | Write to SpacetimeDB (`save_site`, `upsert_schema`, `log_event`) | Console shows the map live |
| 8 | Docs: data dictionary + rules + not-visible + operations as Markdown | Shown in Console / API docs |
| 9 | Cache the explored model for a demo-safe fallback | Demo can skip a slow re-explore |

### 👤 Agent person: Operator (extraction + live operations)
**Owns:** `core/operator/`

| # | Task | Done when |
|---|---|---|
| 1 | Playwright session: login (credentials from `.env`, entered by a person), detect logged-out pages, re-login, resume | Survives the 10-minute timeout |
| 2 | Generic extractor driven by the data model's `read` mappings: list → paging → detail pages → field values | Extracts all ClinicPro patients |
| 3 | Extraction job: `upsert_record`, progress via `update_job`, `log_event`, content hash per record, resumable | Database fills live in the Console |
| 4 | Duplicate check (same name + DOB) → event flag, never merge | Planted duplicates flagged |
| 5 | Op worker: poll `op_request` (pending) → `claim_op` → run the operation's steps (fill by label, submit) → **verify** by re-reading → `finish_op` with result or the old system's error text; update the record in the database on success | `POST /appointments` works end to end |
| 6 | Nemotron fallback: if a step fails (element missing, unexpected page), send the page model to Nemotron, retry once, else fail clearly | Recovers from one deliberate surprise |

### 👤 SpacetimeDB person: Demo target + backend + API/MCP
**Owns:** `legacy/clinicpro/`, `spacetime/`, `core/store/`, `api/`, pitch

| # | Task | Done when |
|---|---|---|
| 1 | **Build ClinicPro 2005** (Section 8) | Running on :5005 with data (**by +2h**) |
| 2 | SpacetimeDB module: tables + reducers (7.5); publish to Maincloud (redeem the HackUTD credit) | Reducers callable |
| 3 | `core/store/spacetime.py`: token, `call(reducer, args)`, `sql(query)`, short timeouts | Explorer + Operator use it |
| 4 | **API (FastAPI)**, generated from `ops_json`: database-backed reads; legacy-backed writes create an `op_request` and wait for done/failed (with timeout) | `/docs` works; reads and writes succeed |
| 5 | **MCP server** (Python `mcp` SDK): the same operations as tools | An MCP client lists and calls the tools |
| 6 | Pitch slides, before/after framing, backup video at freeze | 3-minute run-through |

### 👤 Frontend person: RESTore Console
**Owns:** `web/` (React + TS + Vite + SpacetimeDB TS SDK)

| # | Task | Done when |
|---|---|---|
| 1 | Scaffold + SpacetimeDB bindings (`spacetime generate --lang typescript`) | Subscribes to tables |
| 2 | **Start panel:** paste URL → start exploration (small endpoint on the API, or create a `job` row the Explorer watches) | One click starts the run |
| 3 | **Live site map** graph from `site.site_map_json` + **agent log** from `event` | Exploration is watchable live |
| 4 | **Data model view:** entities, fields, types, rules, "not visible" | Clear at a glance |
| 5 | **Extraction progress** from `job` + **data browser**: browse the extracted tables (search, sort, open a record). A database viewer, not a recreated app | Data visibly fills live |
| 6 | **API playground:** list operations, fill inputs, call the API, show JSON + the op status (pending → done/failed with the old system's message) | Write moment works on stage |
| 7 | **MCP panel:** server address + tool list + copy-paste config | Easy to show the AI connection |

---

## 10. Repo, setup, environment

```
RESTore/
├── FACADE-PLAN-v4.md
├── core/
│   ├── .env.example / .env (git-ignored)
│   ├── ingest/        # existing: Nemotron client, label, screen_model, inspector, selftest (Daniel)
│   ├── explore/       # NEW: capture_web, explorer loop, understand, docs (Daniel)
│   ├── operator/      # NEW: session, extractor, op worker (agent person)
│   └── store/         # spacetime.py (SpacetimeDB person)
├── legacy/clinicpro/  # demo target (SpacetimeDB person)
├── spacetime/         # SpacetimeDB module (SpacetimeDB person)
├── api/               # FastAPI + MCP (SpacetimeDB person)
├── web/               # RESTore Console (frontend)
└── shared/
    ├── formats/       # one example of each format (7.2–7.4)
    └── prompts/       # Nemotron prompts (versioned)
```

### `.env` additions
```
CLINICPRO_URL=http://localhost:5005
CLINICPRO_USER=admin            # typed in by a person
CLINICPRO_PASS=
SPACETIME_HOST=https://maincloud.spacetimedb.com
SPACETIME_DB=facade
SPACETIME_TOKEN=
EXPLORE_PAGE_BUDGET=25
API_PORT=8000
```
**Never commit `.env`, keys, `core/cache/`, or `_to_delete/`.** Everyone on their own branch; merge to `main` at checkpoints after an end-to-end check.

### Setup
```bash
cd core && source .venv/bin/activate
pip install -r requirements.txt playwright fastapi uvicorn mcp
playwright install chromium
python -m ingest.selftest
```

---

## 11. Timeline, checkpoints, cut list
*(Hours from 10:30 PM. Adjust to the real submission deadline.)*

| When | Must work | Who |
|---|---|---|
| **+0:30** | Formats agreed; one example of each posted | All |
| **+2h** | ClinicPro running; `capture_web` turns real pages into page models | SpacetimeDB person, Daniel |
| **+3h** | SpacetimeDB module live; Console subscribes; Operator logs in and extracts one record | SpacetimeDB, frontend, agent |
| **+5h** | Explorer maps ClinicPro on its own; data model + rules + operations correct | Daniel |
| **+7h** | Full extraction into SpacetimeDB; data browser fills live | Agent, frontend |
| **+8.5h** | API reads + one write op end to end (verified; Sunday rule rejection shown) | SpacetimeDB person, agent |
| **+10h** | MCP + docs; API playground in the Console | SpacetimeDB person, Daniel, frontend |
| **+11h** | 🔒 **Feature freeze**: cache the model, rehearse 3×, record backup video | All |

### Cut list (in this order if behind)
1. MCP (keep the API)
2. Second write operation (keep one)
3. Appointments extraction (keep Patients)
4. Docs page (keep the data model view)

**Never cut:** live exploration with the site map growing, the database filling live, one verified write through the API, and the Nemotron activity log.

---

## 12. Demo script (3 minutes)

| Time | Beat |
|---|---|
| 0:00–0:20 | **Problem:** "This clinic's 18 years of data is trapped in software with no export and no API." Show ClinicPro 2005 |
| 0:20–1:00 | **Explore:** paste the URL. The site map builds itself; Nemotron's reasoning in the log |
| 1:00–1:20 | **Understand:** data model + rules appear, plus "Not visible: billing logic" (honesty) |
| 1:20–1:55 | **Extract:** progress bars; the database fills live; a session timeout recovered; duplicates flagged |
| 1:55–2:35 | **API:** `GET /patients?name=smith` returns JSON from the database. `POST /appointments`, and **on the screen next to it ClinicPro books itself**, verified ✓. Try a Sunday → "Old system rule: no Sunday appointments" |
| 2:35–2:50 | **MCP:** an AI assistant answers "which patients have no phone number?" through the generated tools |
| 2:50–3:00 | **Close:** "From a URL to a database, an API and AI tools, for a system that had none. Built on Nemotron agents, self-hostable as NIM." |

---

## 13. Judge Q&A

| Question | Answer |
|---|---|
| "How is this different from Skyvern / Integuru / browser agents?" | They automate tasks you describe, one at a time. RESTore **discovers the whole system on its own** and produces a typed database, API and MCP for all of it, with verified writes |
| "Doesn't it miss hidden logic?" | Yes, and it says so: it lists what isn't visible. Writes go through the old system, so its own rules still apply (the Sunday rejection) |
| "Is it fast enough?" | Nemotron learns each page type once; extraction then runs as fast browser code; Nemotron only for surprises |
| "Is this legal?" | For systems you own or are authorized to automate (your own data). No CAPTCHA bypassing; credentials entered by a person |
| "How do you know the data is right?" | Field mappings are validated against the pages; every write is verified by re-reading; duplicates are flagged, never merged |
| "Privacy?" | Hackathon uses hosted NIM; production runs Nemotron as a self-hosted NIM so data stays on premises |
| "Why Nemotron?" | Nano Omni reads pages (ARIA + screenshot) quickly; Super handles planning, the data model and recovery; NIM gives a cloud-to-on-prem path |

---

## 14. Risks and team rules

| Risk | Mitigation | Owner |
|---|---|---|
| Live exploration slow or wrong on stage | Page budget, cached model fallback, warm-up run | Daniel |
| Nemotron JSON errors | Existing validation + repair retry + fallback | Daniel |
| Extraction too slow | Field mappings, no Nemotron per record, modest seed size | Agent |
| Writes fail silently | Always verify by re-reading; return the old system's error | Agent |
| SpacetimeDB hiccup | Agents never block on it; local JSON cache | SpacetimeDB person |
| Scope creep | Cut list; freeze at +11h | All |

### Team rules
1. **NVIDIA first.** Anything that makes the agent demo fragile gets cut.
2. **No site-specific code** in Explorer/Operator. They work from the site map, data model and operations, not from hardcoded ClinicPro knowledge.
3. **Formats are law.** Change Section 7 only after telling the team.
4. **Explorer never submits forms.** Only the Operator writes, only for API operations, always verified.
5. **Log every Nemotron call** to `event`. It's our proof for judges.
6. **Never commit `.env`**, keys, `core/cache/`, or `_to_delete/`.
7. **Status in chat every ~2 hours:** done / doing / blocked.
