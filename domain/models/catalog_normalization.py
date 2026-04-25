import re
import unicodedata


def normalize_catalog_name(value: str) -> str:
    """Normalize a catalog label for exact duplicate detection."""
    without_accents = "".join(
        char
        for char in unicodedata.normalize("NFKD", value.strip().casefold())
        if not unicodedata.combining(char)
    )
    normalized = re.sub(r"[^\w]+", " ", without_accents, flags=re.UNICODE)
    return re.sub(r"\s+", " ", normalized).strip()
