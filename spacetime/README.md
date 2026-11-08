# RESTore SpacetimeDB module

Site-agnostic storage for whatever the Nemotron agents discover. Every table has a `site` column, so any number of explored URLs can live side by side.

## Publish (Windows, from this `spacetime` folder)
```
npm install
spacetime publish facade --server maincloud
```
While the schema is still changing, add `--delete-data` to wipe old rows.

## Tables
`site`, `entity_schema`, `record`, `op_request`, `job`, `event` (see `src/index.ts`).

## Reducers
`save_site`, `upsert_schema`, `upsert_record`, `request_op`, `claim_op`, `finish_op`, `start_job`, `update_job`, `log_event`, `clear_site`.
Pass `""` for anything you don't have.
