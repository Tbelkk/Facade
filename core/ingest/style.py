"""Screenshot -> Style Profile (contract 6.3): keep the app's identity, modernize the rendering.

1. MEASURE the palette from pixels (exact colors, never guessed).
2. Ask Nemotron to DESCRIBE the look and pick which measured color is the identity color.
3. BUILD modern design tokens from the app's own hues, with contrast checked in code (WCAG AA).

Usage (from core/):
    python -m ingest.style ../shared/fixtures/screenshot.png --app OpenDental.exe
    python -m ingest.style shot.png --app eventvwr.exe --no-ai      # palette + rules only
"""
import argparse
import colorsys
import json
import re
import time
from pathlib import Path

from . import nemotron
from .paths import CACHE_DIR, PROMPTS_DIR

PROMPT_FILE = PROMPTS_DIR / "style_v1.md"
STYLE_CACHE = CACHE_DIR / "style"
DANGER = "#B3261E"
FONTS = {
    "sans": "Segoe UI Variable, Inter, system-ui, sans-serif",
    "serif": "Georgia, 'Source Serif 4', serif",
    "monospace": "'Cascadia Code', 'JetBrains Mono', Consolas, monospace",
}


# ---------- color math ----------

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02X}" for c in rgb)


def hls(hexcode):
    return colorsys.rgb_to_hls(*hex_to_rgb(hexcode))


def from_hls(h, l, s):
    return rgb_to_hex(colorsys.hls_to_rgb(h % 1.0, max(0, min(1, l)), max(0, min(1, s))))


def luminance(hexcode):
    def ch(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in hex_to_rgb(hexcode))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def is_chromatic(hexcode):
    h, l, s = hls(hexcode)
    return s > 0.18 and 0.08 < l < 0.92


def hue_distance(a, b):
    d = abs(hls(a)[0] - hls(b)[0])
    return min(d, 1 - d)


def ensure_contrast(fg_h, fg_l, fg_s, bg, target=4.5, direction=-1):
    """Move fg lightness (darker by default) until it meets the contrast target against bg."""
    color = from_hls(fg_h, fg_l, fg_s)
    steps = 0
    while contrast(color, bg) < target and 0.0 < fg_l < 1.0 and steps < 60:
        fg_l += 0.015 * direction
        color = from_hls(fg_h, fg_l, fg_s)
        steps += 1
    return color


# ---------- step 1: measure ----------

def extract_palette(png_path, k=8, sample_width=400, merge_dist=28, min_share=0.004):
    """Dominant colors by pixel share. Returns [{"hex", "share"}], most common first.

    Legacy UIs are made of flat colors, so we count EXACT pixel colors (nearest-neighbor
    downscale, never blending) and merge near-identical shades. Blending would invent
    in-between colors the app never used.
    """
    from PIL import Image

    img = Image.open(png_path).convert("RGB")
    if img.width > sample_width:
        nearest = getattr(getattr(Image, "Resampling", Image), "NEAREST")
        img = img.resize((sample_width, max(1, round(img.height * sample_width / img.width))), nearest)
    total = img.width * img.height
    counts = sorted(img.getcolors(maxcolors=total) or [], reverse=True)

    clusters = []  # [count, (r, g, b) of the most common member]
    for count, rgb in counts:
        for cl in clusters:
            if sum((a - b) ** 2 for a, b in zip(rgb, cl[1])) ** 0.5 <= merge_dist:
                cl[0] += count
                break
        else:
            if len(clusters) < 64:
                clusters.append([count, rgb])
    clusters.sort(key=lambda c: -c[0])
    return [{"hex": "#%02X%02X%02X" % rgb, "share": round(count / total, 3)}
            for count, rgb in clusters[:k] if count / total >= min_share]


def measured_density(snapshot):
    if not snapshot:
        return None
    wr = snapshot.get("window_rect", {})
    area = (wr.get("w") or 0) * (wr.get("h") or 0)
    if area <= 0:
        return None
    per_100k = len(snapshot.get("nodes", [])) / (area / 100_000)
    return "compact" if per_100k > 12 else "comfortable" if per_100k > 4 else "spacious"


# ---------- step 2: describe (Nemotron) ----------

def describe_style(png_path, palette, budget=None):
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    pal_text = "\n".join(f'{p["hex"]}  ({round(p["share"] * 100)}% of screen)' for p in palette)
    part, _ = nemotron.image_part(png_path, max_width=1200)
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": [{"type": "text", "text": "Measured palette:\n" + pal_text}, part]},
    ]
    res = nemotron.chat(messages, purpose="style_traits", budget=budget, answer_tokens=800)
    return nemotron.extract_json(res["text"]), res["ms"]


def _clean_traits(raw, palette):
    raw = raw if isinstance(raw, dict) else {}
    pal_hex = {p["hex"].upper() for p in palette}

    def pick_hex(v):
        if isinstance(v, str) and re.fullmatch(r"#?[0-9a-fA-F]{6}", v.strip()):
            v = "#" + v.strip().lstrip("#").upper()
            return v if v in pal_hex else None  # must come from the measured palette
        return None

    def pick(v, allowed, default):
        return v if v in allowed else default

    return {
        "traits": str(raw.get("traits") or "")[:300],
        "theme": pick(raw.get("theme"), {"light", "dark"}, None),
        "density": pick(raw.get("density"), {"compact", "comfortable", "spacious"}, None),
        "primary_hint": pick_hex(raw.get("primary_hint")),
        "accent_hint": pick_hex(raw.get("accent_hint")),
        "corner_style": pick(raw.get("corner_style"), {"sharp", "rounded"}, "sharp"),
        "chrome_style": pick(raw.get("chrome_style"), {"classic_3d", "flat", "skeuomorphic", "terminal"}, "classic_3d"),
        "font_hint": pick(raw.get("font_hint"), {"sans", "serif", "monospace"}, "sans"),
        "font_family": str(raw.get("font_family"))[:40] if isinstance(raw.get("font_family"), str) else None,
        "font_size_pt": raw.get("font_size_pt") if isinstance(raw.get("font_size_pt"), (int, float))
        and 5 <= raw.get("font_size_pt") <= 24 else None,
    }


# ---------- step 3: build tokens ----------

def build_tokens(palette, traits, density):
    chromatic = [p["hex"] for p in palette if is_chromatic(p["hex"])]
    dominant = palette[0]["hex"] if palette else "#F0F0F0"
    theme = traits.get("theme") or ("dark" if luminance(dominant) < 0.18 and palette[0]["share"] > 0.35 else "light")

    primary_src = traits.get("primary_hint") or (chromatic[0] if chromatic else None)
    identity_from = "measured" if primary_src else "fallback"
    primary_src = primary_src or "#3A6EA5"  # classic Windows blue when an app is fully gray
    ph, pl, ps = hls(primary_src)

    accent_src = traits.get("accent_hint")
    if not accent_src:
        accent_src = next((c for c in chromatic if c != primary_src and hue_distance(c, primary_src) > 0.07), None)

    if theme == "dark":
        surface = from_hls(ph, 0.11, min(ps, 0.18))
        surface_alt = from_hls(ph, 0.16, min(ps, 0.18))
        border = from_hls(ph, 0.26, min(ps, 0.15))
        text = ensure_contrast(ph, 0.92, 0.10, surface, 7.0, +1)
        text_muted = ensure_contrast(ph, 0.70, 0.08, surface, 4.5, +1)
        p_l = min(max(pl, 0.55), 0.68)
        p_s = min(max(ps, 0.40), 0.75)
        primary = ensure_contrast(ph, p_l, p_s, surface, 4.5, +1)
        on_primary = "#0B0F0E"
        primary_hover = from_hls(ph, hls(primary)[1] + 0.06, p_s)
    else:
        surface = from_hls(ph, 0.985, 0.18 if ps > 0.1 else 0.0)
        surface_alt = from_hls(ph, 0.955, 0.16 if ps > 0.1 else 0.0)
        border = from_hls(ph, 0.86, 0.12 if ps > 0.1 else 0.0)
        text = ensure_contrast(ph, 0.13, 0.15, surface, 7.0, -1)
        text_muted = ensure_contrast(ph, 0.42, 0.08, surface, 4.5, -1)
        p_l = min(max(pl, 0.32), 0.46)
        p_s = min(max(ps, 0.35), 0.72)
        on_primary = "#FFFFFF"
        primary = ensure_contrast(ph, p_l, p_s, on_primary, 4.5, -1)
        primary_hover = from_hls(ph, hls(primary)[1] - 0.06, p_s)

    if accent_src:
        ah, al, as_ = hls(accent_src)
        if theme == "dark":
            accent = ensure_contrast(ah, min(max(al, 0.55), 0.7), min(max(as_, 0.4), 0.8), surface, 4.5, +1)
        else:
            accent = ensure_contrast(ah, min(max(al, 0.32), 0.45), min(max(as_, 0.4), 0.8), surface, 4.5, -1)
    else:  # same identity hue, different weight
        accent = ensure_contrast(ph, 0.36 if theme == "light" else 0.66, min(p_s + 0.1, 0.85), surface, 4.5,
                                 -1 if theme == "light" else +1)

    danger = DANGER if theme == "light" else ensure_contrast(*hls(DANGER), surface, 4.5, +1)

    density = traits.get("density") or density or "comfortable"
    sharp = traits.get("corner_style") == "sharp"
    flat = traits.get("chrome_style") in ("flat", "terminal")
    font = "monospace" if traits.get("chrome_style") == "terminal" else traits.get("font_hint", "sans")

    tokens = {
        "color.primary": primary,
        "color.primary.hover": primary_hover,
        "color.on.primary": on_primary,
        "color.surface": surface,
        "color.surface.alt": surface_alt,
        "color.border": border,
        "color.text": text,
        "color.text.muted": text_muted,
        "color.accent": accent,
        "color.danger": danger,
        "radius.sm": "3px" if sharp else "6px",
        "radius.md": "6px" if sharp else "10px",
        "font.family": FONTS.get(font, FONTS["sans"]),
        "font.size.base": {"compact": "13px", "comfortable": "14px", "spacious": "15px"}[density],
        "space.unit": {"compact": "4px", "comfortable": "5px", "spacious": "6px"}[density],
        "shadow.card": "none" if flat else ("0 1px 2px rgba(0,0,0,0.08)" if theme == "light"
                                             else "0 1px 2px rgba(0,0,0,0.5)"),
    }
    report = {
        "text_on_surface": round(contrast(text, surface), 2),
        "muted_on_surface": round(contrast(text_muted, surface), 2),
        "on_primary": round(contrast(on_primary, primary), 2),
        "accent_on_surface": round(contrast(accent, surface), 2),
        "danger_on_surface": round(contrast(danger, surface), 2),
    }
    passed = all(v >= 4.5 for v in report.values())
    return {"tokens": tokens, "theme": theme, "density": density, "identity_from": identity_from,
            "identity_color": primary_src if identity_from == "measured" else None,
            "report": report, "passed": passed}


# ---------- main entry ----------

def _cache_file(app_key):
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", app_key)[:80] or "app"
    return STYLE_CACHE / f"{safe}.json"


def style_profile(app_key, screenshot_path, snapshot=None, use_cache=True, use_ai=True, budget=None):
    """Build (or load) the style profile for one app. Contract 6.3 plus a few extras."""
    cf = _cache_file(app_key)
    if use_cache and cf.is_file():
        prof = json.loads(cf.read_text(encoding="utf-8"))
        prof["cached"] = True
        return prof

    palette = extract_palette(screenshot_path)
    traits_raw, model_ms, source, error = {}, 0, "rules", None
    if use_ai:
        try:
            traits_raw, model_ms = describe_style(screenshot_path, palette, budget)
            source = "nemotron"
        except Exception as e:  # never block the UI on style
            error = str(e)[:200]
    traits = _clean_traits(traits_raw, palette)
    built = build_tokens(palette, traits, measured_density(snapshot))

    profile = {
        "app_key": app_key,
        "source_palette": [p["hex"] for p in palette],
        "palette_share": palette,
        "traits": traits["traits"],
        "theme": built["theme"],
        "density": built["density"],
        "chrome_style": traits["chrome_style"],
        "original_font": {"family": traits["font_family"], "size": traits["font_size_pt"]},
        "identity_color": built["identity_color"],
        "identity_from": built["identity_from"],
        "tokens": built["tokens"],
        "contrast_checked": built["passed"],
        "contrast_report": built["report"],
        "traits_source": source,
        "model_ms": model_ms,
        "cached": False,
    }
    if error:
        profile["error"] = error
    STYLE_CACHE.mkdir(parents=True, exist_ok=True)
    if source == "nemotron" or not use_ai:
        cf.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    return profile


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a Style Profile for an app screenshot.")
    ap.add_argument("screenshot")
    ap.add_argument("--app", required=True, help="app key, e.g. OpenDental.exe")
    ap.add_argument("--snapshot", help="optional snapshot JSON (improves density estimate)")
    ap.add_argument("--no-ai", action="store_true", help="skip Nemotron; palette + rules only")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args(argv)

    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8")) if args.snapshot else None
    t0 = time.time()
    prof = style_profile(args.app, args.screenshot, snapshot, use_cache=not args.no_cache, use_ai=not args.no_ai)
    out = Path(args.out) if args.out else Path(args.screenshot).with_suffix(".style.json")
    out.write_text(json.dumps(prof, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"theme={prof['theme']} density={prof['density']} chrome={prof['chrome_style']} "
          f"identity={prof['identity_color']} ({prof['identity_from']}) source={prof['traits_source']}")
    print("palette:", " ".join(f'{p["hex"]}:{round(p["share"] * 100)}%' for p in prof["palette_share"]))
    print("tokens:", {k: v for k, v in prof["tokens"].items() if k.startswith("color.")})
    print(f"contrast ok={prof['contrast_checked']} {prof['contrast_report']}")
    print(f"model_ms={prof['model_ms']} total={time.time() - t0:.2f}s  saved {out}")
    if prof.get("error"):
        print("NOTE: Nemotron step failed, used rules only:", prof["error"])


if __name__ == "__main__":
    main()
