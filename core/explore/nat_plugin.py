"""NVIDIA NeMo Agent Toolkit (NAT) plugin: the RESTore Explorer as a NAT function.

Registered under the entry point group `nat.components` (see core/pyproject.toml), so after
`uv pip install -e core` NAT discovers it automatically:

    nat run --config_file explore/configs/explorer_offline.yml --input "http://localhost:5005"
    nat run --config_file explore/configs/explorer.yml         --input "http://localhost:5005"
    nat run --config_file explore/configs/agent.yml            --input "Map the clinic system at http://localhost:5005"

`explorer*.yml` run the explorer directly as the workflow. `agent.yml` puts a Nemotron ReAct agent on
top that decides when to call the explorer tool and summarizes the site map it gets back.
NAT also gives us its profiler, tracing and `nat serve` (REST endpoint) for free.
"""
import asyncio
import json

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig


class FacadeExplorerConfig(FunctionBaseConfig, name="facade_explorer"):
    """Map a legacy website (read-only) into a RESTore site map."""
    page_budget: int = Field(default=25, description="Max page types to map.")
    reader: str = Field(default="nemotron", description="'nemotron' (Nano Omni) or 'heuristic'.")
    planner: str = Field(default="nemotron", description="'nemotron' (Super) or 'heuristic'.")
    headless: bool = Field(default=True)
    login: str = Field(default="none", description="'none' or 'env' (FACADE_LOGIN_USER / FACADE_LOGIN_PASS).")
    sink: str = Field(default="json", description="'json' or 'spacetime'.")
    screenshots: bool = Field(default=True)
    full_site_map: bool = Field(default=False, description="Return the whole site map instead of a summary.")


def _summary(result):
    sm = result["site_map"]
    return {
        "site": sm["site"],
        "site_map_path": result["site_map_path"],
        "pages": [{k: p.get(k) for k in ("id", "kind", "entity", "url_pattern", "purpose")} for p in sm["pages"]],
        "edges": len(sm["edges"]),
        "unexplored": sm["unexplored"][:10],
        "notes": sm["notes"],
        "stats": sm["stats"],
    }


@register_function(config_type=FacadeExplorerConfig)
async def facade_explorer(config: FacadeExplorerConfig, builder: Builder):
    from ingest import nemotron  # noqa: F401  (loads core/.env)

    from .explorer import ExploreConfig, Explorer

    async def _explore(url: str) -> str:
        """Explore the website at `url` read-only and return its site map (pages, kinds, entities, links) as JSON."""
        url = url.strip().strip("'\"")
        cfg = ExploreConfig(start_url=url, page_budget=config.page_budget, headless=config.headless,
                            reader=config.reader, planner=config.planner, login=config.login,
                            sink=config.sink, screenshots=config.screenshots)
        # Playwright's sync API must not run inside NAT's event loop: run the agent in a worker thread.
        result = await asyncio.to_thread(lambda: Explorer(cfg).run())
        out = result["site_map"] if config.full_site_map else _summary(result)
        return json.dumps(out, indent=2)

    yield FunctionInfo.from_fn(
        _explore,
        description=("Explore a legacy website read-only, starting from its URL. Returns a site map: every page "
                     "type found (list / detail / form / menu), the business entity it holds, its URL pattern, "
                     "and how pages link together. Input: the site's start URL."),
    )
