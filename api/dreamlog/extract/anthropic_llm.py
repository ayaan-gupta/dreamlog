"""The LLM symbol extractor: Claude through the Anthropic SDK, strict JSON schema.

UNTESTED against the live API: there was no ANTHROPIC_API_KEY on the machine
this was written on. The request shape follows the SDK's structured-output
interface (``output_config.format`` with a JSON schema) and the response is
validated again with pydantic. ``tests/test_extraction.py`` exercises the
parsing, validation and fallback paths with a stub client.

Privacy: this sends the transcript to Anthropic. The default extractor does not.
"""

from __future__ import annotations

import logging
from typing import Any

import anthropic
from pydantic import ValidationError

from .base import KINDS, MAX_SYMBOLS, MOODS, ExtractedSymbol, Extraction, SymbolExtractor

log = logging.getLogger(__name__)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "symbols": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "kind": {"type": "string", "enum": list(KINDS)},
                    "salience": {"type": "number"},
                },
                "required": ["name", "kind", "salience"],
                "additionalProperties": False,
            },
        },
        "moods": {"type": "array", "items": {"type": "string", "enum": list(MOODS)}},
    },
    "required": ["symbols", "moods"],
    "additionalProperties": False,
}

SYSTEM = f"""You tag entries in a private dream journal. For the dream you are given, list its symbols and its moods.

Symbols are the concrete things in the dream: places, kinds of people (mother, stranger, teacher; never a name), \
animals, objects, and natural things such as water or fire. Give each as a singular lower-case noun of one to three \
words, exactly as plainly as the dreamer put it. Do not merge related things yourself: if the dream says ocean, write \
ocean, not water. A separate step decides which symbols are the same. List at most {MAX_SYMBOLS}, most central first, \
with a salience from 0 to 1 where the most central symbol is 1.

Moods are how the dream felt to the dreamer, at most three, strongest first, chosen only from the allowed list. Use \
neutral when the dream gives no feeling.

Report what is in the dream. Do not interpret it, explain it, or say what anything might mean."""


class AnthropicExtractor:
    def __init__(self, model: str, fallback: SymbolExtractor, client: Any | None = None) -> None:
        self.name = f"anthropic:{model}"
        self._model = model
        self._fallback = fallback
        self._client = client if client is not None else anthropic.Anthropic()

    def extract(self, text: str) -> Extraction:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2000,
                system=SYSTEM,
                messages=[{"role": "user", "content": text}],
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            )
        except anthropic.RateLimitError:
            return self._give_up(text, "rate limited")
        except anthropic.APIStatusError as exc:
            return self._give_up(text, f"API status {exc.status_code}")
        except anthropic.APIConnectionError:
            return self._give_up(text, "network error")
        if response.stop_reason != "end_turn":
            # refusal, max_tokens and anything else: the JSON cannot be trusted.
            return self._give_up(text, f"stop_reason {response.stop_reason}")
        body = first_text(response.content)
        try:
            return _clean(Extraction.model_validate_json(_clamp(body)))
        except (ValidationError, ValueError) as exc:
            return self._give_up(text, f"invalid output ({type(exc).__name__})")

    def _give_up(self, text: str, why: str) -> Extraction:
        log.warning("LLM extraction failed (%s); using the offline extractor", why)
        return self._fallback.extract(text)


def first_text(content: Any) -> str:
    """The text of the first text block. Thinking blocks come first and are skipped."""
    return next((str(getattr(block, "text", "")) for block in content if getattr(block, "type", "") == "text"), "")


def _clamp(body: str) -> str:
    """The schema cannot bound numbers or list lengths, so do it before validating."""
    import json

    data = json.loads(body)
    symbols = data.get("symbols", [])[:MAX_SYMBOLS]
    for symbol in symbols:
        symbol["salience"] = min(max(float(symbol.get("salience", 0.0)), 0.0), 1.0)
        symbol["name"] = " ".join(str(symbol.get("name", "")).lower().split())[:40]
    data["symbols"] = [s for s in symbols if s["name"]]
    data["moods"] = list(dict.fromkeys(data.get("moods", [])))[:3] or ["neutral"]
    return json.dumps(data)


def _clean(extraction: Extraction) -> Extraction:
    seen: dict[str, ExtractedSymbol] = {}
    for symbol in extraction.symbols:
        seen.setdefault(symbol.name, symbol)
    return Extraction(symbols=list(seen.values()), moods=extraction.moods)
