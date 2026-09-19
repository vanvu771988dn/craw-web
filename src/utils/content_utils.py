import hashlib
import re


WHITESPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9'-]{2,}")
STOP_WORDS = {
    "the", "and", "for", "with", "that", "from", "this", "have", "after", "will",
    "into", "about", "their", "they", "them", "over", "under", "more", "than",
    "your", "just", "into", "while", "where", "when", "what", "which", "been",
    "said", "says", "say", "are", "was", "were", "his", "her", "its", "our",
    "who", "why", "how", "you", "not", "but", "too", "can",
}


def normalize_text_for_storage(value: str | None) -> str:
    if not value:
        return ""
    return WHITESPACE_RE.sub(" ", value).strip().lower()


def compute_content_fingerprint(title: str | None, main_content: str | None) -> str | None:
    normalized_title = normalize_text_for_storage(title)
    normalized_content = normalize_text_for_storage(main_content)
    if not normalized_title and not normalized_content:
        return None

    key = f"{normalized_title}\n{normalized_content}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def extract_meaningful_tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    tokens = {
        token.lower()
        for token in TOKEN_RE.findall(value)
        if token.lower() not in STOP_WORDS and len(token) >= 4
    }
    return tokens


def compute_token_overlap(left: str | None, right: str | None) -> float:
    left_tokens = extract_meaningful_tokens(left)
    right_tokens = extract_meaningful_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0

    intersection = left_tokens & right_tokens
    denominator = min(len(left_tokens), len(right_tokens))
    if denominator == 0:
        return 0.0
    return len(intersection) / denominator
