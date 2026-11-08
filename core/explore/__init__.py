"""Facade Explorer: point it at a website, it maps the whole system on its own (read-only).

Modules
-------
urlpattern   URL -> url_pattern ("/patients/42" -> "/patients/{id}") so the explorer visits each page TYPE once
capture_web  Playwright page -> page model (schema_version 1, screen.source = "dom"): links, forms, tables, ARIA
policy       The two Nemotron roles: PageReader (Nano Omni labels a page) and Planner (Super picks the next step).
             Each has a heuristic twin, so everything runs offline with no API key.
sink         Where results go: local JSON files (always) and SpacetimeDB (optional, never blocks)
explorer     The agent loop: capture -> read -> plan -> navigate, with a hard write-guard and a page budget
run          CLI:  python -m explore.run http://localhost:5005 --budget 25
nat_plugin   NVIDIA NeMo Agent Toolkit plugin: the explorer as a NAT function / workflow (`nat run ...`)

Safety: the explorer NEVER submits forms. A browser-level guard blocks every POST/PUT/PATCH/DELETE
request (except the one login submit, when login is enabled), and links that look destructive
(logout, delete, remove, ...) are never followed.

Run everything from the `core/` folder.
"""
