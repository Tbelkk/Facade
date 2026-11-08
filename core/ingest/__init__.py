"""RESTore ingest: turn any app window into a labeled, styled screen model.

Modules
-------
capture   Windows only: accessibility tree + screenshot -> Screen Snapshot (contract 6.1)
nemotron  Shared Nemotron client (NVIDIA NIM, OpenAI-compatible)
label     Snapshot -> Screen Labels (contract 6.2) via Nemotron 3 Nano Omni
style     Screenshot -> Style Profile (contract 6.3): measured palette + Nemotron traits
pipeline  End to end: snapshot (file or live) -> labels + style
screen_model  Snapshot + labels + style -> Screen Model (the frontend's format, schema_version 1)
selftest  Offline check with a simulated Nemotron (no API key needed)
inspect   Local viewer: python -m ingest.inspect  (Original / Faithful / Enhanced / Reimagined preview)

Run everything from the `core/` folder, e.g.  python -m ingest.selftest
"""
