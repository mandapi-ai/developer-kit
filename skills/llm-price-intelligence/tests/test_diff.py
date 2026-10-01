from pathlib import Path

from mandapi_price_intelligence.diff import build_diff_markdown


def test_diff_detects_changes(tmp_path: Path):
    header = "platform,model_id,pricing_variant,context_tier,currency,input_per_1m,output_per_1m\n"
    old = tmp_path / "old.csv"
    new = tmp_path / "new.csv"
    old.write_text(header + "X,m1,standard,,USD,1,2\nX,m2,standard,,USD,3,4\n", encoding="utf-8")
    new.write_text(header + "X,m1,standard,,USD,1.5,2\nX,m3,standard,,USD,5,6\n", encoding="utf-8")
    report = build_diff_markdown(old, new)
    assert "Added offers: **1**" in report
    assert "Removed offers: **1**" in report
    assert "1 → 1.5" in report
