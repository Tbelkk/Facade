# Mock websites: test the agents end to end

Put a data file in `mock_sites/data/`. It becomes a 2005-style legacy website (server-rendered tables,
paging, detail pages, edit forms, no API, no export). Then one command runs the whole pipeline on it:

```
mock data -> mock website -> Explorer (site map + recipes) -> Extractor -> SpacetimeDB-shaped JSON -> check vs. the data
```

```bash
cd core && source .venv/bin/activate
python -m mock_sites.run clinic              # login, session timeout, duplicates, references
python -m mock_sites.run inventory           # no login, money / integer / enum / reference fields
python -m mock_sites.run clinic --nemotron   # Nemotron reads + plans the pages (needs NVIDIA_API_KEY)
python -m mock_sites.run my_site --headed    # watch the browser
python -m mock_sites.server clinic           # just serve it: http://127.0.0.1:5060
```

The run prints how many records and fields came out right (it knows the answer: your data file), and
fails if anything is wrong or if any write reached the site.

## Where the next agent finds it

Every run also replaces **`core/cache/latest/`**, a fixed folder for the SpacetimeDB server:
`data_model.json`, `records/<Entity>.jsonl`, `operations.json`, `site_map.json`, `spacetime/*.json`,
`manifest.json`. See `operator_agent/README.md`. Use `--no-publish` to leave it alone.

## See the output as a web page

```bash
python -m extract.view          # newest run -> http://127.0.0.1:5070
python -m mock_sites.run clinic --serve   # run, then serve that run's page
```

One tab per SpacetimeDB table (`record`, `entity_schema`, `site`, `job`, `event`) with the exact rows and
column types, JSON columns formatted (or "as stored" strings), entity filter, search, copy and download.
The same page is also saved as `extract/index.html` on every run.

## Output: `core/cache/mock/<site>_<time>/extract/`

| File | What it is |
|---|---|
| `spacetime/site.json` | rows of the `site` table: `url, site_map_json, model_json, ops_json, docs_md, updated_at` |
| `spacetime/entity_schema.json` | `name, fields_json, rules_json` per entity |
| `spacetime/record.json` | `id, entity, legacy_id, data_json, hash, extracted_at` per record |
| `spacetime/job.json`, `event.json` | extraction progress and the agent log |
| `schema.json` | JSON Schema per entity: what the API returns for one record |
| `data.json` | `{Entity: [records]}`: what `GET /<entity>` would answer |
| `model.json` | data model + rules (format 7.3) |
| `records.jsonl`, `duplicates.json`, `check.json` | hashes/changes, flagged duplicates, the ground-truth check |

Every row in `spacetime/*.json` is one reducer call once the module is live (`record` -> `upsert_record`, ...).
Values are typed: dates `YYYY-MM-DD`, money and counts as numbers, references as `<field>_id` = the other
record's `legacy_id` (plus `<field>` with the text the site shows).

The extractor also works on real explored sites: `python -m extract.run <explorer run folder> --login env`.

## Data file format

Store values **clean**; the site prints them the legacy way (dates `MM/DD/YYYY`, money `$1,234.50`).

```json
{
  "name": "Sunrise Dental", "brand": "ClinicPro 2005",
  "login": {"username": "admin", "password": "mock-only-password"},   // or null for no login
  "page_size": 10,                 // rows per list page
  "session_max_requests": 60,      // session expires after N requests (0 = never)
  "entities": [
    {
      "name": "Patient", "path": "patients", "title": "Patients",
      "display": "{last_name}, {first_name}",          // how other pages show a link to this record
      "fields": [
        {"key": "last_name", "label": "Last Name", "required": true},
        {"key": "dob", "label": "DOB", "type": "date"},          // string | date | money | number | text
        {"key": "provider", "label": "Provider", "options": ["Dr. Lee", "Dr. Patel"]},   // dropdown
        {"key": "patient_id", "label": "Patient", "ref": "Patient"}                       // link to a record
      ],
      "list_columns": [                                   // optional; first column links to the detail page
        {"header": "Name", "template": "{last_name}, {first_name}"},
        {"header": "DOB", "field": "dob"}
      ],
      "records": [{"id": "1", "last_name": "Smith", "dob": "1950-01-31"}]
    }
  ]
}
```

Comments above are for reading only; JSON files can't contain them. Copy `data/clinic.json` to start.
The check compares fields by the **label** the site shows (`"Last Name"` -> `last_name`), because that is
all the agents can see.
