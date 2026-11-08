# Facade Explorer

Point it at a website. It maps every page type on its own, **read-only**, and writes a
site map (plan format 7.2) plus one page model per page type for the Understand step.

```
capture page (Playwright) -> PageReader names it (Nemotron 3 Nano Omni)
   -> safe candidate actions from every page seen -> Planner picks one (Nemotron 3 Super)
   -> navigate (GET only) -> repeat until the page budget is spent or nothing new is left
```

## Setup (from `core/`, Python 3.11+ for the NeMo Agent Toolkit)

```bash
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -r requirements.txt "nvidia-nat[langchain]>=1.9" -e .
playwright install chromium
cp .env.example .env   # paste NVIDIA_API_KEY
```

## Run

```bash
python -m explore.run http://localhost:5005 --offline              # no API key: heuristic reader + planner
python -m explore.run http://localhost:5005                        # Nemotron reader + planner
python -m explore.run http://localhost:5005 --login env            # FACADE_LOGIN_USER / _PASS from .env
python -m explore.run http://localhost:5005 --login manual --headed  # a person types the password
python -m explore.run http://localhost:5005 --sink spacetime       # also stream to SpacetimeDB
```

Output: `core/cache/explore/<host>_<time>/` → `site_map.json`, `pages/<page_id>.json`, `shots/`, `events.jsonl`
(also copied to `core/cache/explore/latest_site_map.json`).

### As a NeMo Agent Toolkit workflow

`pyproject.toml` registers the `facade_explorer` function under `nat.components`.

```bash
nat run --config_file explore/configs/explorer_offline.yml --input "http://localhost:5005"
nat run --config_file explore/configs/explorer.yml         --input "http://localhost:5005"
nat run --config_file explore/configs/agent.yml --input "Map the system at http://localhost:5005"  # ReAct agent + tool
nat serve --config_file explore/configs/agent.yml          # REST endpoint
```

## Test (no API key needed)

```bash
python -m pytest            # spins up tests/legacy_site.py, a small 2005-style app with traps
python tests/legacy_site.py # look at the test site yourself: http://127.0.0.1:5055
```

The tests check: every page type is found once; list pagination and row links; form labels,
required fields and dropdown options; the page budget; login + re-login after a session timeout;
**no write ever reaches the server** (only the login POST); Nemotron answers are validated, with
fallbacks; and the explorer runs as a NAT workflow.

## Safety

- A browser-level guard aborts every non-GET request (except the single login submit with `--login env`).
- Links that look destructive (log out, delete, remove, cancel, ...) are never followed.
- The explorer never clicks buttons; it only opens link URLs.

## Not done yet

- `--sink spacetime` guesses the reducer arguments from plan section 7.5. Align `_REDUCER_ARGS`
  in `sink.py` with the real SpacetimeDB module.
- The Understand step (data model + rules + operations) is next. It reads `pages/*.json`.
