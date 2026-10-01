from decimal import Decimal

from mandapi_price_intelligence.normalize import canonicalize_model_id, parse_decimal_price


def test_brl_decimal_comma():
    assert parse_decimal_price("R$ 0,40 / 1M") == Decimal("0.40")
    assert parse_decimal_price("R$ 1.234,56") == Decimal("1234.56")


def test_usd_decimal_point():
    assert parse_decimal_price("US$ 2.00") == Decimal("2.00")


def test_openrouter_prefix_normalizes_conservatively():
    assert canonicalize_model_id("openai/gpt-6-sol") == "gpt-6-sol"
    assert canonicalize_model_id("somevendor/custom-model") == "somevendor/custom-model"
