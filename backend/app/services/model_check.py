"""Confirm at startup that the configured Gemini models still exist.

Google retires model versions. When one goes, the API answers with a 404, and
every layer above it turns that into something reassuring: transcription reports
itself "unavailable", the coach says "I'm having trouble responding right now".
Both read as a network blip or a missing key. Neither says the thing that is
actually true -- that a model name in this repository has expired and needs a
one-word change.

This app ran with two retired models (`gemini-2.0-flash` and
`gemini-2.0-flash-lite`) and looked, from the outside, exactly like a Gemini key
that had not been set.

So the names are checked against what the key can actually reach, once, at
startup. Listing models costs a metadata call rather than a generation, so this
is cheap and never touches quota.
"""

import logging
from typing import Iterable, List

logger = logging.getLogger(__name__)


def available_models(api_key: str) -> List[str]:
    """Model names this key can reach, without the `models/` prefix."""
    from google import genai

    client = genai.Client(api_key=api_key)
    names = []
    for model in client.models.list():
        name = getattr(model, "name", "") or ""
        names.append(name.split("/")[-1])
    return names


def check_configured_models(api_key: str, wanted: Iterable[str]) -> List[str]:
    """Log and return the configured models this key cannot reach.

    Returns an empty list when everything is fine, including when there is no
    API key at all -- running without one is a supported mode, and the services
    already say so individually. A network failure here is reported and treated
    as "cannot tell", never as "the model is gone": refusing to start over a
    flaky metadata call would be worse than the fault it guards against.
    """
    wanted = list(dict.fromkeys(wanted))          # de-duplicate, keep order
    if not api_key:
        return []

    try:
        reachable = set(available_models(api_key))
    except Exception:
        logger.warning(
            "Could not list Gemini models, so %s could not be verified. "
            "If transcription or coaching report themselves unavailable, run "
            "scripts/check_gemini_models.py to see what this key can reach.",
            ", ".join(wanted),
        )
        return []

    missing = [name for name in wanted if name not in reachable]
    if missing:
        logger.error(
            "Gemini model(s) unavailable to this API key: %s. Transcription "
            "and/or coaching will fail, and will report themselves merely "
            "'unavailable'. Model versions are retired over time -- run "
            "scripts/check_gemini_models.py to list what this key can reach, "
            "then set TRANSCRIPTION_MODEL / CHAT_MODEL accordingly.",
            ", ".join(missing),
        )
    else:
        logger.info("Gemini models verified: %s", ", ".join(wanted))

    return missing
