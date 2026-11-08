# Operator agent (agent 2): data -> API design

```
Explorer + Extractor: website -> data + a description of it      (data_model.json, site_map.json, records/)
Operator (this):      data -> an API design                       (operations.json, api_docs.md)
SpacetimeDB person:   API design -> a working API and MCP
Frontend:             shows all of it live
```

## Run

```bash
cd core && source .venv/bin/activate
python -m operator_agent.run operator_agent/examples/news      # mock input, Nemotron designs
python -m operator_agent.run operator_agent/examples/clinic
python -m operator_agent.run <any run folder> --offline        # code-only design, no API key
python -m mock_sites.run clinic                                 # whole chain: website -> ... -> API design
```

Nemotron (`MODEL_AGENT`, default `nvidia/nemotron-3.5-super-vl-120b-a12b`) is used when `NVIDIA_API_KEY` is in
`core/.env`.

## Input (one folder)

| File | What |
|---|---|
| `data_model.json` | entities, typed fields (`string`, `integer`, `number`, `date`, `enum`, `ref`), relations, and the **forms** seen (fields, required, options) |
| `site_map.json` | page types (list / detail / form) |
| `records/<Entity>.jsonl` | `{"legacy_id", "hash", "extracted_at", "data": {...}}` per line |

`examples/news` (read-only, no forms) and `examples/clinic` (create + edit forms) are ready-made inputs.
To hand-make one, copy an example and edit the JSON.

## What it does

1. **Profiles the real values** (code): per field the type, distinct count, min/max/median, common values.
2. **Nemotron designs** the endpoints: list, get-one, search; filters chosen from the values
   (numbers/dates -> `min_`/`max_`, few distinct values -> exact match, names -> contains, references -> `<x>_id`);
   write endpoints **only from forms it saw** (create form -> `POST`, edit form -> `PATCH`, required fields copied).
3. **Code checks** every field exists, every path and name is unique, filters fit the field types, and writes
   match a real form. Problems go back to Nemotron, which **fixes them once**. Anything still invalid is dropped;
   every entity keeps at least list + get. If Nemotron is unreachable, the code-only design is used and labelled.
4. **Real examples**: every read endpoint is run against the records (`query.py`) to make the example.

## Output (same folder)

**`operations.json`**: `designed_by` (Nemotron model, attempts, problems found/fixed) and `operations[]`:

```json
{"name": "list_posts", "method": "GET", "path": "/posts", "entity": "Post", "kind": "list",
 "source": "database",
 "inputs": [{"name": "min_points", "in": "query", "type": "integer", "field": "points", "match": "gte"}],
 "output": {"type": "list", "entity": "Post"},
 "example": {"request": "/posts?min_points=161&limit=3", "response": {"total": 13, "items": [...]}}}
```

- `source: "database"`: answer from SpacetimeDB. `match`: `eq`, `contains` (case-insensitive), `gte`, `lte`,
  `search` (over `fields`), `limit`, `offset`, `sort` (`-field` = descending).
  `query.py` is a reference implementation of exactly these semantics.
- `source: "legacy"`: create an `op_request`; the Operator fills `legacy.form_page` on the old site, submits,
  verifies, and returns `{status, result, error}`. Body inputs are the form's fields (`in: "body"`).

**`api_docs.md`**: every endpoint with its inputs and a real example request/response.

## Handoff to SpacetimeDB: `core/cache/latest/`

Every command-line run (`mock_sites.run`, `extract.run`, `operator_agent.run`) replaces this folder with the
newest run's outputs, so the SpacetimeDB server always reads the same path. Skip with `--no-publish`; move it
with `FACADE_HANDOFF_DIR=/some/path`.

| File | Use it for |
|---|---|
| `manifest.json` | which run, when, record counts, endpoint count, files present |
| `data_model.json` | `upsert_schema` per entity |
| `records/<Entity>.jsonl` | `upsert_record` per line (`legacy_id`, `hash`, `extracted_at`, `data`) |
| `operations.json` | the endpoints + MCP tools to create |
| `site_map.json` | `save_site` |
| `spacetime/<table>.json` | the same data as ready-made rows for every table (plan 7.5) |
| `schema.json`, `api_docs.md`, `recipes.json` | JSON Schema per entity, docs, read/fill recipes |

The folder is replaced as a whole (never a mix of two runs). `core/cache/` is git-ignored, so on another machine
use the tracked `operator_agent/examples/<name>/` folders, which have the same layout.
