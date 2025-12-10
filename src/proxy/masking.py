import re
from typing import Iterable

from core.models import MaskRule

MASKABLE_CONTENT_TYPES = {
    "application/json",
    "text/html",
    "text/xml",
    "text/plain",
    "application/xml",
}


def mask_content(content: str, rules: Iterable[MaskRule]) -> str:
    """Apply regex masking rules to content."""
    masked = content
    for rule in rules:
        masked = re.sub(rule.pattern, rule.replacement, masked)
    return masked
