"""Start the Facade back end with one line, from the Facade folder (venv active):

    python -m api

Runs the Facade API on http://localhost:8000 (site check + starts the agents for the dashboard), and a
practice legacy site on http://127.0.0.1:5061/products to test against. Ctrl+C stops both.
"""
import os
import sys
from pathlib import Path

import uvicorn

CORE = Path(__file__).resolve().parent.parent / "core"
sys.path.insert(0, str(CORE))

if os.getenv("FACADE_PRACTICE_SITE", "1") != "0":
    try:
        from mock_sites.server import start
        site = start("inventory", 5061)
        print(f"Practice legacy site: {site.url}/products  (\"{site.site.get('brand') or site.site.get('name')}\", try it in the dashboard)")
    except OSError:
        print("Practice legacy site: port 5061 is busy, skipped")

print("Facade API: http://localhost:8000  (docs: /docs)  ·  now run `npm run dev` in web/ for the dashboard")
uvicorn.run("api.main:app", host="127.0.0.1", port=int(os.getenv("FACADE_API_PORT", "8000")), log_level="warning")
