"""Constructs BreakoutCandidate with every field and asserts the dataclass works."""

from twstock.strategy.patterns_strategy import BreakoutCandidate


def test_breakout_candidate_all_fields():
    cand = BreakoutCandidate(
        code="2330",
        name="台積電",
        pattern="W底",
        direction="bullish",
        price=585.0,
        volume=12345000,
        target=650.0,
        stop_loss=560.0,
        confidence=0.85,
        symbol="2330",
        neckline=580.0,
        extreme=550.0,
        quality=0.72,
        current_price=582.5,
        distance_pct=0.43,
        predicted_break_day=3,
        predicted_break_price=585.0,
        predicted_peak=640.0,
        points=[
            ("2025-01-02", 550.0),
            ("2025-01-15", 580.0),
            ("2025-02-01", 555.0),
        ],
        prev_close=580.0,
        prev_volume=9876000,
        amount=7200000000.0,
    )
    assert cand.symbol == "2330"
    assert cand.neckline == 580.0
    assert cand.extreme == 550.0
    assert cand.quality == 0.72
    assert cand.current_price == 582.5
    assert cand.distance_pct == 0.43
    assert cand.predicted_break_day == 3
    assert cand.predicted_break_price == 585.0
    assert cand.predicted_peak == 640.0
    assert len(cand.points) == 3
    assert cand.prev_close == 580.0
    assert cand.prev_volume == 9876000
    assert cand.amount == 7200000000.0


def test_breakout_candidate_defaults():
    cand = BreakoutCandidate()
    assert cand.symbol == ""
    assert cand.neckline == 0.0
    assert cand.extreme == 0.0
    assert cand.quality == 0.0
    assert cand.current_price == 0.0
    assert cand.distance_pct == 0.0
    assert cand.predicted_break_day == 0
    assert cand.predicted_break_price == 0.0
    assert cand.predicted_peak == 0.0
    assert cand.points == []
    assert cand.prev_close == 0.0
    assert cand.prev_volume == 0
    assert cand.amount == 0.0
