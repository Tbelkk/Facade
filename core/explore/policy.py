"""The two Nemotron roles in the Explorer, each with an offline heuristic twin.

PageReader  page model -> {page_id, purpose, entity, kind, confidence}
            NemotronReader uses Nemotron 3 Nano Omni (DOM summary + screenshot).
Planner     (site so far, current page, candidates) -> one candidate id or "stop"
            NemotronPlanner uses Nemotron 3 Super.

Every Nemotron answer is validated. A bad or failed answer falls back to the heuristic, and the
fallback is reported so it shows up in the agent log (team rule 5: log every Nemotron call).
"""
import os
import re

from .capture_dom import summarize
from .urlpattern import page_id_from_pattern, slug

KINDS = {"list", "detail", "form", "menu", "login", "other"}
PROMPTS = {"read": "explore_read_v1.md", "plan": "explore_plan_v1.md"}
TYPE_RANK = {"follow_link_nav": 0, "open_row": 1, "open_form": 2, "follow_link": 3}


def _prompt(name):
    from ingest.paths import PROMPTS_DIR
    return (PROMPTS_DIR / PROMPTS[name]).read_text(encoding="utf-8")


# ---------------------------------------------------------------- page reader

class HeuristicReader:
    """Names a page from its structure and URL alone. No AI."""
    name = "heuristic"

    def read(self, model, known_ids=()):
        h = model["screen"]["heuristic"]
        kind, entity = h["kind"], h["entity"]
        pattern = model["screen"]["url_pattern"]
        path = pattern.split("?")[0].lower()
        if kind == "login":
            pid = "login"
        elif entity and kind in ("list", "detail"):
            pid = f"{slug(entity)}_{kind}"
        elif entity and kind == "form":
            verb = "new" if re.search(r"/(new|add|create)\b", path) else "edit" if "edit" in path else "form"
            pid = f"{slug(entity)}_{verb}"
        else:
            pid = page_id_from_pattern(pattern)
        purpose = {
            "list": f"Browse and search {entity or 'record'}s",
            "detail": f"View one {entity or 'record'}",
            "form": f"Create or edit a {entity or 'record'}",
            "menu": "Navigate between sections",
            "login": "Sign in",
        }.get(kind, model["screen"]["title"] or "Page")
        return {"page_id": pid, "purpose": purpose, "entity": entity if kind != "menu" else None,
                "kind": kind, "confidence": 0.4, "by": "heuristic", "ms": 0}


class NemotronReader:
    """Nemotron 3 Nano Omni reads the DOM summary (+ screenshot) and labels the page."""
    name = "nemotron"

    def __init__(self, model=None, budget=None, use_screenshot=True):
        self.model = model or os.getenv("MODEL_VISION", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning")
        self.budget = budget
        self.use_screenshot = use_screenshot
        self.fallback = HeuristicReader()

    def read(self, model, known_ids=()):
        from ingest import nemotron

        base = self.fallback.read(model, known_ids)
        text = (f"Already known page_ids: {', '.join(known_ids) or '(none)'}\n"
                f"Structural guess (may be wrong): kind={base['kind']} entity={base['entity']}\n\n"
                + summarize(model))
        content = [{"type": "text", "text": text}]
        shot = model["screen"].get("screenshot")
        if self.use_screenshot and shot and os.path.isfile(shot):
            part, _ = nemotron.image_part(shot, max_width=1280)
            content.append(part)
        messages = [{"role": "system", "content": _prompt("read")}, {"role": "user", "content": content}]
        try:
            res = nemotron.chat(messages, purpose="explore_read", model=self.model, budget=self.budget,
                                answer_tokens=400, temperature=0.2)
            raw = nemotron.extract_json(res["text"])
        except Exception as e:
            base.update({"by": "heuristic_fallback", "error": str(e)[:200]})
            return base
        return validate_read(raw, base, res["ms"])


def validate_read(raw, base, ms=0):
    """Clean a reader answer; anything missing or invalid comes from the heuristic guess."""
    out = dict(base)
    out.update({"by": "nemotron", "ms": ms})
    if not isinstance(raw, dict):
        out["by"] = "heuristic_fallback"
        return out
    pid = slug(str(raw.get("page_id") or ""), "")
    if pid and not re.search(r"_\d+$", pid):
        out["page_id"] = pid
    if isinstance(raw.get("purpose"), str) and raw["purpose"].strip():
        out["purpose"] = raw["purpose"].strip()[:200]
    ent = raw.get("entity")
    if ent is None or (isinstance(ent, str) and ent.strip().lower() in ("", "null", "none")):
        out["entity"] = None if raw.get("kind") in ("menu", "login") else base["entity"]
    elif isinstance(ent, str):
        out["entity"] = re.sub(r"[^A-Za-z0-9]", "", ent.title() if ent.islower() else ent)[:40] or base["entity"]
    if raw.get("kind") in KINDS:
        out["kind"] = raw["kind"]
    try:
        out["confidence"] = max(0.0, min(1.0, float(raw.get("confidence", 0.5))))
    except (TypeError, ValueError):
        out["confidence"] = 0.5
    return out


# ---------------------------------------------------------------- planner

def _rank(c):
    key = "follow_link_nav" if c["type"] == "follow_link" and c.get("in_nav") else c["type"]
    return (TYPE_RANK.get(key, 9), c["order"])


class HeuristicPlanner:
    """Breadth first: unseen nav sections, then one row per list, then forms."""
    name = "heuristic"

    def choose(self, site_pages, current, candidates):
        if not candidates:
            return {"action": "stop", "reason": "nothing new to visit", "by": "heuristic", "ms": 0}
        best = min(candidates, key=_rank)
        return {"action": best["id"], "reason": f"{best['type']} '{best['label']}'", "by": "heuristic", "ms": 0}


class NemotronPlanner:
    """Nemotron 3 Super picks the next exploration step from a fixed, safe menu of actions."""
    name = "nemotron"

    def __init__(self, model=None, budget=None, max_candidates=40):
        self.model = model or os.getenv("MODEL_AGENT", "nvidia/nemotron-3.5-super-vl-120b-a12b")
        self.budget = budget
        self.max_candidates = max_candidates
        self.fallback = HeuristicPlanner()

    def choose(self, site_pages, current, candidates):
        from ingest import nemotron

        if not candidates:
            return {"action": "stop", "reason": "nothing new to visit", "by": "rule", "ms": 0}
        shown = sorted(candidates, key=_rank)[: self.max_candidates]
        mapped = "\n".join(f"- {p['id']} ({p['kind']}, entity={p.get('entity')}): {p['url_pattern']}"
                           for p in site_pages) or "(none yet)"
        cands = "\n".join(f"{c['id']} | {c['type']} | \"{c['label']}\" | {c['url_pattern']} | found on {c['from_page']}"
                          for c in shown)
        text = (f"PAGES MAPPED SO FAR:\n{mapped}\n\nCURRENT PAGE ({current or 'start'}).\n\n"
                f"CANDIDATES (id | action | link text | url pattern | found on):\n{cands}")
        messages = [{"role": "system", "content": _prompt("plan")}, {"role": "user", "content": text}]
        try:
            res = nemotron.chat(messages, purpose="explore_plan", model=self.model, budget=self.budget,
                                answer_tokens=300, temperature=0.2)
            raw = nemotron.extract_json(res["text"])
        except Exception as e:
            out = self.fallback.choose(site_pages, current, candidates)
            out.update({"by": "heuristic_fallback", "error": str(e)[:200]})
            return out
        action = str(raw.get("action", "")).strip() if isinstance(raw, dict) else ""
        reason = str(raw.get("reason", ""))[:200] if isinstance(raw, dict) else ""
        ids = {c["id"] for c in candidates}
        if action == "stop" or action in ids:
            return {"action": action, "reason": reason, "by": "nemotron", "ms": res["ms"]}
        out = self.fallback.choose(site_pages, current, candidates)
        out.update({"by": "heuristic_fallback", "error": f"invalid action {action!r}", "ms": res["ms"]})
        return out


def make(reader="heuristic", planner="heuristic", **kw):
    r = NemotronReader(use_screenshot=kw.get("use_screenshot", True), budget=kw.get("budget")) \
        if reader == "nemotron" else HeuristicReader()
    p = NemotronPlanner(budget=kw.get("budget")) if planner == "nemotron" else HeuristicPlanner()
    return r, p
