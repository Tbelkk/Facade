"""RESTore explore: two explorer agents share this package (run everything from core/).

Daniel's extraction agent (one pass: explore + extract with Nemotron reading each page)
    agent         python -m explore.agent <url>          records + data model + site map (cache/extract/<run>/)
    capture_web   python -m explore.capture_web <url>    read one page into a page model (debugging)

Tyler's mapper (maps every page TYPE, writes recipes; the extract package then pulls every record)
    run           python -m explore.run <url>            site_map.json + recipes.json + pages/ (cache/explore/<run>/)
    explorer      the agent loop: capture -> read -> plan -> navigate, write-guard + page budget
    capture_dom   Playwright page -> page model (links, forms, tables, ARIA) used by explorer/recipes
    policy        Nemotron PageReader (Nano Omni) + Planner (Super), each with an offline heuristic twin
    recipes       how to read each list/detail page and fill each form (recipes.json)
    urlpattern    "/patients/42" -> "/patients/{id}" so each page TYPE is visited once
    sink          local JSON (always) + SpacetimeDB (optional, never blocks)
    nat_plugin    NVIDIA NeMo Agent Toolkit plugin (`nat run ...`)

Both feed the Operator (core/operator_agent), which designs the API (operations.json) and publishes the
handoff folder shared/output/<site>/ that the SpacetimeDB server reads.

Safety: explorers NEVER submit forms. Tyler's mapper blocks every non-GET request at the browser level
(except the one login submit) and never follows links that look destructive (logout, delete, ...).
"""
