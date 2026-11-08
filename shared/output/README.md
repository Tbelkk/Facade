# shared/output: what the SpacetimeDB server reads

One folder per site, written by the agents, committed to the repo:

```
shared/output/
├── index.json               every published site; "latest" = the newest
└── <site>/                  e.g. hackernews, clinic, news
    ├── manifest.json        which run, when, record counts, endpoint count, files present
    ├── data_model.json      entities, typed fields, relations, forms        -> upsert_schema
    ├── records/<Entity>.jsonl  one record per line                          -> upsert_record
    ├── site_map.json        page types                                       -> save_site
    ├── operations.json      the API design: endpoints + MCP tools to create
    ├── api_docs.md          readable docs with real example requests/responses
    └── recipes.json, schema.json, spacetime/<table>.json   (when the run produced them)
```

## Who writes what

| Step | Command (from `core/`) | Produces |
|---|---|---|
| Explore + extract (Daniel) | `python -m explore.agent <url>` | `cache/extract/<run>/`: data_model, site_map, records |
| Map + extract (Tyler) | `python -m explore.run <url>` then `python -m extract.run <run>` | `cache/explore/<run>/`: same files + recipes, spacetime rows |
| Operator (API design) | `python -m operator_agent.run <run folder>` | operations.json + api_docs.md, then **publishes here** |
| Whole chain on a mock site | `python -m mock_sites.run clinic` | all of the above, published here |

Then commit `shared/output/` and push.

## Loading it (SpacetimeDB server)

1. Read `index.json`, pick a site (or `latest`).
2. `data_model.json` -> `upsert_schema(name, fields_json, rules_json)` per entity.
3. Each line of `records/<Entity>.jsonl` -> `upsert_record(entity, legacy_id, data_json, hash)`.
   Lines are `{"legacy_id", "hash", "extracted_at", "data": {...}}`. Records from Daniel's agent can also be flat
   (`{"_key": "<url>", field: value}`); `core/operator_agent/inputs.py` (`load`) shows how to normalise both.
4. `operations.json` -> one endpoint + one MCP tool per operation. `source: "database"` reads the records
   (filter semantics: `core/operator_agent/query.py`); `source: "legacy"` creates an `op_request`.
