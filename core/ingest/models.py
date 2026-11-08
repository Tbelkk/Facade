"""Which Nemotron models can this key use, and which one does each agent use?

    python -m ingest.models            # list Nemotron models on the endpoint + test each agent's model
    python -m ingest.models --try nvidia/some-model   # also test one specific model

Each test is one tiny call ("reply with OK"), so it costs almost nothing.
"""
import argparse
import time

from . import nemotron as N


def available(base_url):
    try:
        return sorted(m.id for m in N.client(base_url).models.list().data if "nemotron" in m.id.lower())
    except Exception as e:
        print(f"  could not list models at {base_url}: {str(e)[:120]}")
        return []


def ping(model, base_url):
    t0 = time.time()
    try:
        r = N.client(base_url).chat.completions.create(
            model=model, messages=[{"role": "user", "content": "Reply with the single word OK."}], max_tokens=600)
        ok = bool(r.choices and r.choices[0].message)
        return ok, f"{(time.time() - t0):.1f}s"
    except Exception as e:
        return False, str(getattr(e, "status_code", "") or "") + " " + str(e)[:90]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--try", dest="extra", action="append", default=[], help="also test this model id")
    a = ap.parse_args(argv)

    print(f"Endpoint: {N.BASE_URL}")
    models = available(N.BASE_URL)
    print(f"Nemotron models listed there ({len(models)}):")
    for m in models:
        print("  ", m)

    print("\nModel per agent (core/.env):")
    plan = [("explorer", "extract_page"), ("split", "split_column"), ("operator", "operator_design")]
    seen = {}
    for role, purpose in plan:
        model, base = N.route(purpose, N.MODEL_AGENT)
        key = (model, base)
        if key not in seen:
            seen[key] = ping(model, base)
        ok, info = seen[key]
        where = "" if base == N.BASE_URL else f"  @ {base}"
        print(f"  {role:<9} {model}{where}   {'OK ' + info if ok else 'FAILS: ' + info}")
    for m in a.extra:
        ok, info = ping(m, N.BASE_URL)
        print(f"  try       {m}   {'OK ' + info if ok else 'FAILS: ' + info}")


if __name__ == "__main__":
    main()
