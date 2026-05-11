from wigs.observability import MetricsStore


def test_metrics_store_incr_set_and_snapshot():
    m = MetricsStore()
    m.incr("a")
    m.incr("a", 2)
    m.set_gauge("g", 7)
    snap = m.snapshot()
    assert snap["counters"]["a"] == 3
    assert snap["gauges"]["g"] == 7
