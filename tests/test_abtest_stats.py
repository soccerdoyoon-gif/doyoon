from app.analytics.abtest import VariantStat, compare


def test_small_sample_no_conclusion():
    r = compare(VariantStat("A", 200, 20), VariantStat("B", 200, 5))
    assert r.verdict == "insufficient_data" and r.winner is None


def test_no_significant_difference():
    r = compare(VariantStat("A", 5000, 100), VariantStat("B", 5000, 104))
    assert r.verdict == "no_significant_difference" and r.p_value > 0.05


def test_significant():
    r = compare(VariantStat("A", 10000, 300), VariantStat("B", 10000, 180))
    assert r.verdict == "significant" and r.winner == "A" and r.lift_percent > 60
