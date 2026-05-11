from wigs.algorithms.feedback import posterior_expected_trust, posterior_trust_multiplier


def test_posterior_expected_trust_midpoint():
    assert posterior_expected_trust(2.0, 2.0) == 0.5


def test_posterior_trust_multiplier_bounds():
    lo = posterior_trust_multiplier(0.01, 100.0, min_multiplier=0.7, max_multiplier=1.3)
    hi = posterior_trust_multiplier(100.0, 0.01, min_multiplier=0.7, max_multiplier=1.3)
    assert 0.7 <= lo <= 1.3
    assert 0.7 <= hi <= 1.3
    assert hi > lo
