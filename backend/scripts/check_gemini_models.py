"""Report which Gemini models this API key can reach, and whether ours still exist.

Run this when transcription or coaching reports itself unavailable. The failure
those produce is deliberately gentle -- "transcription unavailable", "I'm having
trouble responding right now" -- and looks identical whether the key is missing,
the network is down, or a model name in this repository has been retired.

    python scripts/check_gemini_models.py
"""

import sys
from pathlib import Path

# Run as `python scripts/check_gemini_models.py` from backend/, so the package
# root is the parent of this file's directory rather than the directory itself.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import config  # noqa: E402
from app.services.model_check import available_models  # noqa: E402


def main() -> int:
    if not config.GEMINI_API_KEY:
        print("GEMINI_API_KEY is not set. The camera, face detection, emotion")
        print("tracking and voice measurement all still work without it; the")
        print("transcript and coaching replies do not.")
        return 1

    try:
        reachable = sorted(available_models(config.GEMINI_API_KEY))
    except Exception as exc:
        print(f"Could not list models: {exc}")
        return 1

    configured = {
        "TRANSCRIPTION_MODEL": config.TRANSCRIPTION_MODEL,
        "CHAT_MODEL": config.CHAT_MODEL,
    }

    print(f"{len(reachable)} models reachable with this key.\n")
    print("Configured:")
    ok = True
    for setting, name in configured.items():
        good = name in reachable
        ok = ok and good
        print(f"  {'OK  ' if good else 'GONE'}  {setting:<20} {name}")

    if not ok:
        print("\nA configured model is unavailable. Pick a replacement below and set")
        print("it in backend/.env, e.g.  CHAT_MODEL=gemini-3.5-flash-lite")

    print("\nReachable models:")
    for name in reachable:
        print(f"  {name}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
