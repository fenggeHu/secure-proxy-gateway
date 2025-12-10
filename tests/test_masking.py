import pytest

from core.models import MaskRule
from proxy.masking import mask_content


def test_mask_content_applies_rules():
    rules = [MaskRule(pattern=r"(\d{3})\d{4}(\d{4})", replacement=r"\1****\2")]
    masked = mask_content("Phone: 13812345678", rules)
    assert "138****5678" in masked


def test_mask_rule_validation_len():
    with pytest.raises(ValueError):
        MaskRule(pattern="a" * 501, replacement="x")
