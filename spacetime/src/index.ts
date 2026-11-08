// Facade backend: SpacetimeDB module.
//
// This module knows NOTHING about any specific website. It stores whatever the
// Nemotron agents (Explorer + Operator) discover, keyed by `site` (the URL that
// was explored), so many sites can live side by side without colliding.
// Anything shaped by the website (fields, records, operations) is a JSON string.
//
// Plan reference: FACADE-PLAN-v4.md, Section 7.5 (+ a `site` column on every table).
//
// Calling from Python (HTTP):
//   POST {host}/v1/database/facade/call/<reducer_name>   body: JSON array of args
//   POST {host}/v1/database/facade/sql                    body: SQL text
// Use "" for any argument you don't have (no nulls needed).

import { schema, table, t, SenderError } from 'spacetimedb/server';

// ---------- Tables ----------

// One row per explored site. Written by the Explorer.
const site = table(
  { name: 'site', public: true },
  {
    url: t.string().primaryKey(),
    site_map_json: t.string(),
    model_json: t.string(),
    ops_json: t.string(),
    docs_md: t.string(),
    updated_at: t.timestamp(),
  }
);

// One row per (site, entity). Written by the Explorer.
const entity_schema = table(
  { name: 'entity_schema', public: true },
  {
    key: t.string().primaryKey(), // `${site}|${name}`
    site: t.string().index('btree'),
    name: t.string(),
    fields_json: t.string(),
    rules_json: t.string(),
  }
);

// Extracted data. One row per legacy record. Written by the Operator.
const record = table(
  { name: 'record', public: true },
  {
    id: t.u64().primaryKey().autoInc(),
    record_key: t.string().unique(), // `${site}|${entity}|${legacy_id}`
    site: t.string().index('btree'),
    entity: t.string(),
    legacy_id: t.string(),
    data_json: t.string(),
    hash: t.string(),
    extracted_at: t.timestamp(),
  }
);

// Write requests from the API, executed on the legacy site by the Operator.
// status: pending -> running -> done | failed
const op_request = table(
  { name: 'op_request', public: true },
  {
    id: t.u64().primaryKey().autoInc(),
    request_key: t.string().unique(), // caller-generated (e.g. a UUID) so the API can find its own request
    site: t.string().index('btree'),
    operation: t.string(),
    inputs_json: t.string(),
    status: t.string(),
    result_json: t.string(),
    error: t.string(),
    created_at: t.timestamp(),
    updated_at: t.timestamp(),
  }
);

// Progress of explore / extract runs.
// status: running | done | failed
const job = table(
  { name: 'job', public: true },
  {
    id: t.u64().primaryKey().autoInc(),
    job_key: t.string().unique(), // caller-generated so the caller can find its own job
    site: t.string().index('btree'),
    kind: t.string(), // explore | extract
    entity: t.string(),
    status: t.string(),
    done: t.u32(),
    total: t.u32(),
    started_at: t.timestamp(),
    updated_at: t.timestamp(),
  }
);

// Live activity log for the Console (and proof of every Nemotron call).
const event = table(
  { name: 'event', public: true },
  {
    id: t.u64().primaryKey().autoInc(),
    site: t.string().index('btree'),
    ts: t.timestamp(),
    actor: t.string(), // explorer | operator | api
    level: t.string(), // info | warn | error
    message: t.string(),
    data_json: t.string(),
  }
);

const spacetimedb = schema({ site, entity_schema, record, op_request, job, event });
export default spacetimedb;

// ---------- Helpers ----------

function requireText(value: string, name: string) {
  if (!value || value.trim() === '') throw new SenderError(`${name} is required`);
}

const JOB_STATUSES = ['running', 'done', 'failed'];

// ---------- Explorer ----------

export const save_site = spacetimedb.reducer(
  {
    url: t.string(),
    site_map_json: t.string(),
    model_json: t.string(),
    ops_json: t.string(),
    docs_md: t.string(),
  },
  (ctx, { url, site_map_json, model_json, ops_json, docs_md }) => {
    requireText(url, 'url');
    const row = { url, site_map_json, model_json, ops_json, docs_md, updated_at: ctx.timestamp };
    if (ctx.db.site.url.find(url)) ctx.db.site.url.update(row);
    else ctx.db.site.insert(row);
  }
);

export const upsert_schema = spacetimedb.reducer(
  { site: t.string(), name: t.string(), fields_json: t.string(), rules_json: t.string() },
  (ctx, { site, name, fields_json, rules_json }) => {
    requireText(site, 'site');
    requireText(name, 'name');
    const key = `${site}|${name}`;
    const row = { key, site, name, fields_json, rules_json };
    if (ctx.db.entity_schema.key.find(key)) ctx.db.entity_schema.key.update(row);
    else ctx.db.entity_schema.insert(row);
  }
);

// ---------- Operator: extraction ----------

export const upsert_record = spacetimedb.reducer(
  {
    site: t.string(),
    entity: t.string(),
    legacy_id: t.string(),
    data_json: t.string(),
    hash: t.string(),
  },
  (ctx, { site, entity, legacy_id, data_json, hash }) => {
    requireText(site, 'site');
    requireText(entity, 'entity');
    requireText(legacy_id, 'legacy_id');
    const record_key = `${site}|${entity}|${legacy_id}`;
    const existing = ctx.db.record.record_key.find(record_key);
    if (existing) {
      // Skip the write when nothing changed (same content hash).
      if (existing.hash === hash && hash !== '') return;
      ctx.db.record.id.update({ ...existing, data_json, hash, extracted_at: ctx.timestamp });
    } else {
      ctx.db.record.insert({
        id: 0n,
        record_key,
        site,
        entity,
        legacy_id,
        data_json,
        hash,
        extracted_at: ctx.timestamp,
      });
    }
  }
);

// ---------- API -> Operator: write operations ----------

export const request_op = spacetimedb.reducer(
  { request_key: t.string(), site: t.string(), operation: t.string(), inputs_json: t.string() },
  (ctx, { request_key, site, operation, inputs_json }) => {
    requireText(request_key, 'request_key');
    requireText(site, 'site');
    requireText(operation, 'operation');
    if (ctx.db.op_request.request_key.find(request_key)) {
      throw new SenderError(`op request ${request_key} already exists`);
    }
    ctx.db.op_request.insert({
      id: 0n,
      request_key,
      site,
      operation,
      inputs_json,
      status: 'pending',
      result_json: '',
      error: '',
      created_at: ctx.timestamp,
      updated_at: ctx.timestamp,
    });
  }
);

// Moves pending -> running. Fails if someone else already claimed it,
// so two Operator workers can never run the same request.
export const claim_op = spacetimedb.reducer({ id: t.u64() }, (ctx, { id }) => {
  const op = ctx.db.op_request.id.find(id);
  if (!op) throw new SenderError(`op request ${id} not found`);
  if (op.status !== 'pending') throw new SenderError(`op request ${id} is ${op.status}, not pending`);
  ctx.db.op_request.id.update({ ...op, status: 'running', updated_at: ctx.timestamp });
});

export const finish_op = spacetimedb.reducer(
  { id: t.u64(), ok: t.bool(), result_json: t.string(), error: t.string() },
  (ctx, { id, ok, result_json, error }) => {
    const op = ctx.db.op_request.id.find(id);
    if (!op) throw new SenderError(`op request ${id} not found`);
    ctx.db.op_request.id.update({
      ...op,
      status: ok ? 'done' : 'failed',
      result_json,
      error,
      updated_at: ctx.timestamp,
    });
  }
);

// ---------- Jobs (progress bars) ----------

export const start_job = spacetimedb.reducer(
  { job_key: t.string(), site: t.string(), kind: t.string(), entity: t.string(), total: t.u32() },
  (ctx, { job_key, site, kind, entity, total }) => {
    requireText(job_key, 'job_key');
    requireText(site, 'site');
    requireText(kind, 'kind');
    if (ctx.db.job.job_key.find(job_key)) throw new SenderError(`job ${job_key} already exists`);
    ctx.db.job.insert({
      id: 0n,
      job_key,
      site,
      kind,
      entity,
      status: 'running',
      done: 0,
      total,
      started_at: ctx.timestamp,
      updated_at: ctx.timestamp,
    });
  }
);

export const update_job = spacetimedb.reducer(
  { job_key: t.string(), done: t.u32(), total: t.u32(), status: t.string() },
  (ctx, { job_key, done, total, status }) => {
    const j = ctx.db.job.job_key.find(job_key);
    if (!j) throw new SenderError(`job ${job_key} not found`);
    if (!JOB_STATUSES.includes(status)) throw new SenderError(`status must be one of ${JOB_STATUSES.join(', ')}`);
    ctx.db.job.id.update({ ...j, done, total, status, updated_at: ctx.timestamp });
  }
);

// ---------- Activity log ----------

export const log_event = spacetimedb.reducer(
  { site: t.string(), actor: t.string(), level: t.string(), message: t.string(), data_json: t.string() },
  (ctx, { site, actor, level, message, data_json }) => {
    ctx.db.event.insert({
      id: 0n,
      site,
      ts: ctx.timestamp,
      actor,
      level: level || 'info',
      message,
      data_json,
    });
  }
);

// ---------- Maintenance ----------

// Removes everything stored for one site (handy for reloading mock data or re-exploring).
export const clear_site = spacetimedb.reducer({ site: t.string() }, (ctx, { site }) => {
  requireText(site, 'site');
  for (const r of [...ctx.db.record.site.filter(site)]) ctx.db.record.delete(r);
  for (const r of [...ctx.db.entity_schema.site.filter(site)]) ctx.db.entity_schema.delete(r);
  for (const r of [...ctx.db.op_request.site.filter(site)]) ctx.db.op_request.delete(r);
  for (const r of [...ctx.db.job.site.filter(site)]) ctx.db.job.delete(r);
  for (const r of [...ctx.db.event.site.filter(site)]) ctx.db.event.delete(r);
  const s = ctx.db.site.url.find(site);
  if (s) ctx.db.site.delete(s);
});

