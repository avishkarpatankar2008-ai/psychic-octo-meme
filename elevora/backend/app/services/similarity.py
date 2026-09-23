import re

_TOKEN_RE = re.compile(r"[a-z0-9']+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def jaccard_similarity(a: str, b: str) -> float:
    tokens_a, tokens_b = _tokens(a), _tokens(b)
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def find_too_similar(candidate: str, existing: list[str], threshold: float = 0.6) -> str | None:
    """Returns the first previously-asked question too similar to `candidate`, or None.

    This is a cheap word-overlap heuristic, not semantic similarity — the
    spec explicitly says not to reach for embeddings/vector DBs this early
    (section 0, "Do NOT learn ... embeddings unless needed later"). It will
    miss paraphrases that share no vocabulary; it reliably catches the
    common failure mode of the model asking a near-identical question with
    a few words swapped.
    """
    for question in existing:
        if jaccard_similarity(candidate, question) >= threshold:
            return question
    return None
