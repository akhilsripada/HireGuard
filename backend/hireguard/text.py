"""Text preparation and evidence helpers."""
import unicodedata

from .config import LOOKALIKE_CHARS

_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def prepare(text: str) -> str:
    """Normalise unicode and fancy punctuation, keeping text close to the original
    so match positions can be used to quote evidence back to the user."""
    return unicodedata.normalize("NFKC", text or "").translate(_QUOTES)


def deobfuscate(word: str) -> str:
    """Map look-alike characters (0->o, 1->l ...) so 'amaz0n' reads 'amazon'."""
    return word.lower().translate(LOOKALIKE_CHARS)


def evidence(text: str, start: int, end: int, width: int = 70) -> str:
    """Return the sentence around a match, trimmed to a readable length."""
    if not text:
        return ""
    stops = ".!?\n"
    s = max(text.rfind(c, 0, start) for c in stops) + 1
    ends = [i for i in (text.find(c, end) for c in stops) if i != -1]
    e = min(ends) + 1 if ends else len(text)
    snippet = text[s:e].strip()
    if len(snippet) > 2 * width:
        rel_start, rel_end = start - s, end - s
        a = max(0, rel_start - width // 2)
        b = min(len(snippet), rel_end + width)
        snippet = ("…" if a > 0 else "") + snippet[a:b].strip() + ("…" if b < len(snippet) else "")
    return snippet
