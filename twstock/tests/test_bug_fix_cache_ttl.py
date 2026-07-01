import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_sr_cache_has_ttl():
    from strategy import sr_analyzer
    assert hasattr(sr_analyzer, '_CACHE_TTL')
    assert sr_analyzer._CACHE_TTL > 0

def test_ma_cache_has_ttl():
    from strategy import ma_strategy
    assert hasattr(ma_strategy, '_CACHE_TTL')
    assert ma_strategy._CACHE_TTL > 0

def test_prediction_cache_has_ttl():
    from strategy import prediction_strategy
    assert hasattr(prediction_strategy, '_CACHE_TTL')
    assert prediction_strategy._CACHE_TTL > 0

def test_patterns_cache_has_ttl():
    from strategy import patterns_strategy
    assert hasattr(patterns_strategy, '_CACHE_TTL')
    assert patterns_strategy._CACHE_TTL > 0
