"""Quick check that Nemotron works (text, plus vision if you pass an image).

Usage (from core/):
    python -m ingest.test_nvidia
    python -m ingest.test_nvidia ../shared/fixtures/screenshot.png
Try REASONING_BUDGET=512 / 1024 / 4096 in core/.env and compare speed vs answer quality.
"""
import sys

from . import nemotron


def main():
    print(f"endpoint={nemotron.BASE_URL}  model={nemotron.MODEL_VISION}  budget={nemotron.REASONING_BUDGET}")
    r = nemotron.chat([{"role": "user", "content": "Reply with exactly: RESTore online."}],
                      purpose="test_text", answer_tokens=200)
    print(f"[text]   {r['ms']} ms -> {r['text']!r}")
    print(f"         usage={r['usage']}")

    if len(sys.argv) > 1:
        part, scale = nemotron.image_part(sys.argv[1])
        r = nemotron.chat([{"role": "user", "content": [
            {"type": "text", "text": "What application is this and what is this screen for? "
                                     "List the 5 most important controls you see."},
            part]}], purpose="test_vision", answer_tokens=800)
        print(f"[vision] {r['ms']} ms (image scale {scale:.2f})\n{r['text']}")


if __name__ == "__main__":
    main()
