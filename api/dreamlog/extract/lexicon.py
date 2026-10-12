"""The offline symbol extractor: deterministic, no model, no network.

Two passes over the tokens. The first looks words up in the lexicon, longest
phrase first, after undoing plurals. The second catches nouns the lexicon does
not know by their grammar: a run of words after a determiner ("the enormous
brass telescope was") is taken to end in its noun. Pattern finds are trusted
less than lexicon finds and carry lower salience.

Salience rewards repetition and an early first mention, then is scaled so the
most salient symbol in a dream is 1.0.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .base import MAX_SYMBOLS, ExtractedSymbol, Extraction, Kind, Mood
from .lexicon_data import BODY_NOISE, DETERMINERS, IRREGULAR, LEXICON, MOOD_CUES, NEGATORS, NOT_SYMBOLS, STOPWORDS, VERBS

_TOKEN = re.compile(r"[a-z]+(?:'[a-z]+)?|[.!?;,:]")

_WORD_KIND: dict[str, Kind] = {}
_PHRASES: dict[tuple[str, ...], Kind] = {}
for _kind, _block in LEXICON.items():
    for _entry in _block.split():
        if "_" in _entry:
            _PHRASES[tuple(_entry.split("_"))] = _kind
        else:
            _WORD_KIND[_entry] = _kind
_MAX_PHRASE = max(len(p) for p in _PHRASES)


def lemma(word: str) -> str:
    """Singular form, as far as a few suffix rules can tell."""
    if word in IRREGULAR:
        return IRREGULAR[word]
    if word in _WORD_KIND:
        return word
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("ses", "xes", "zes", "ches", "shes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def tokenize(text: str) -> list[str]:
    out: list[str] = []
    for token in _TOKEN.findall(text.lower().replace("’", "'")):
        out.append(token[:-2] if token.endswith("'s") else token)
    return out


@dataclass
class _Hit:
    kind: Kind
    count: int
    first: int
    weight: float


def _verbish(word: str) -> bool:
    return word in VERBS or (len(word) > 4 and word.endswith(("ed", "ing")) and word not in _WORD_KIND)


def _adjectivish(word: str) -> bool:
    return word in NOT_SYMBOLS or (len(word) > 4 and word.endswith(("est", "ly", "ful", "ous", "ive", "less")))


class LexiconExtractor:
    name = "lexicon"

    def extract(self, text: str) -> Extraction:
        tokens = tokenize(text)
        hits: dict[str, _Hit] = {}
        taken = [False] * len(tokens)

        def record(name: str, kind: Kind, position: int, weight: float) -> None:
            hit = hits.get(name)
            if hit is None:
                hits[name] = _Hit(kind, 1, position, weight)
            else:
                hit.count += 1

        # Pass 1: lexicon, longest phrase first.
        i = 0
        while i < len(tokens):
            matched = False
            for size in range(min(_MAX_PHRASE, len(tokens) - i), 1, -1):
                window = tokens[i : i + size]
                phrase = tuple(window[:-1] + [lemma(window[-1])])
                if phrase in _PHRASES:
                    record(" ".join(phrase), _PHRASES[phrase], i, 1.0)
                    for k in range(i, i + size):
                        taken[k] = True
                    i += size
                    matched = True
                    break
            if matched:
                continue
            word = lemma(tokens[i])
            kind = _WORD_KIND.get(word)
            if kind is not None and word not in BODY_NOISE:
                record(word, kind, i, 0.8 if kind == "body" else 1.0)
                taken[i] = True
            i += 1

        # Pass 2: the noun that ends a run of unknown words after a determiner.
        i = 0
        while i < len(tokens):
            if tokens[i] not in DETERMINERS:
                i += 1
                continue
            j = i + 1
            run: list[int] = []
            while j < len(tokens) and j - i <= 4:
                word = tokens[j]
                if taken[j] or word in STOPWORDS or not word.isalpha() or _verbish(word):
                    break
                run.append(j)
                j += 1
            blocked = j < len(tokens) and taken[j]  # the run led into a lexicon word: that word is the noun
            if run and not blocked:
                head = lemma(tokens[run[-1]])
                if len(head) >= 4 and not _adjectivish(head) and not _adjectivish(tokens[run[-1]]) and head not in BODY_NOISE:
                    record(head, "object", run[-1], 0.6)
            i = max(j, i + 1)

        return Extraction(symbols=_rank(hits, len(tokens)), moods=tag_moods(tokens))


def _rank(hits: dict[str, _Hit], length: int) -> list[ExtractedSymbol]:
    if not hits:
        return []
    scored: list[tuple[float, int, str, Kind]] = []
    for name, hit in hits.items():
        early = 1.15 - 0.3 * (hit.first / max(length, 1))
        scored.append(((1 + 0.5 * (hit.count - 1)) * early * hit.weight, hit.first, name, hit.kind))
    scored.sort(key=lambda t: (-t[0], t[1], t[2]))
    top = scored[0][0]
    return [ExtractedSymbol(name=name, kind=kind, salience=round(max(score / top, 0.05), 2)) for score, _first, name, kind in scored[:MAX_SYMBOLS]]


def tag_moods(tokens: list[str]) -> list[Mood]:
    """Up to two moods by cue-word count. A cue within three words after a
    negator ("not afraid", "it was not frightening") does not count."""
    scores: dict[Mood, float] = {}
    first: dict[Mood, int] = {}
    for i, token in enumerate(tokens):
        for mood, cues in MOOD_CUES.items():
            weight = cues.get(token)
            if weight is None:
                continue
            window = tokens[max(0, i - 3) : i]
            if any(w in NEGATORS or w.endswith("n't") for w in window):
                continue
            scores[mood] = scores.get(mood, 0.0) + weight
            first.setdefault(mood, i)
    ranked = sorted(scores, key=lambda m: (-scores[m], first[m]))
    strong = [m for m in ranked if scores[m] >= 1.0][:2]
    return strong or ranked[:1] or ["neutral"]
