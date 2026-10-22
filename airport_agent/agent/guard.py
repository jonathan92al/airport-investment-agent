"""Check that the narrator only used numbers it was given."""
import re

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_LIST_MARKER = re.compile(r"(?m)^\s*(?:\d+[.)]|#\d+)\s+")
SMALL_INT_LIMIT = 10  # counts and ordinals ("two airports", "3rd") are not checked


def _values(text: str) -> list[float]:
    text = _LIST_MARKER.sub("", text)
    out = []
    for m in _NUMBER.findall(text):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def unsupported_numbers(answer: str, sources: list[str]) -> list[float]:
    """Numbers in `answer` that appear in none of `sources` (facts, question, assumptions)."""
    allowed = {round(v, 6) for s in sources for v in _values(s)}
    bad = []
    for v in _values(answer):
        if v == int(v) and v <= SMALL_INT_LIMIT:
            continue
        if round(v, 6) not in allowed:
            bad.append(v)
    return bad
