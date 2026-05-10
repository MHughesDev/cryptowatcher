from datetime import datetime, timedelta

from wigs.algorithms.clustering import (
    build_clusters,
    build_copurchase_graph,
    classify_cluster,
    run_louvain,
    score_cluster_suspicion,
)


def test_build_copurchase_graph_filters_by_threshold():
    graph = build_copurchase_graph(
        [("a", "b", 3), ("b", "c", 1)],
        min_shared_tokens=2,
    )
    assert graph.has_edge("a", "b")
    assert not graph.has_edge("b", "c")


def test_run_louvain_returns_partition():
    graph = build_copurchase_graph([("a", "b", 2), ("b", "c", 2)], min_shared_tokens=2)
    partition = run_louvain(graph)
    assert set(partition) == {"a", "b", "c"}


def test_score_cluster_suspicion_high_for_tight_shared_group():
    now = datetime.utcnow()
    events = [
        {"wallet_address": "a", "token_mint": "mint1", "event_type": "BUY", "event_time": now, "social_type": "telegram"},
        {"wallet_address": "b", "token_mint": "mint1", "event_type": "BUY", "event_time": now + timedelta(seconds=2), "social_type": "telegram"},
        {"wallet_address": "c", "token_mint": "mint1", "event_type": "BUY", "event_time": now + timedelta(seconds=4), "social_type": "telegram"},
        {"wallet_address": "a", "token_mint": "mint1", "event_type": "SELL", "event_time": now + timedelta(minutes=15)},
        {"wallet_address": "b", "token_mint": "mint1", "event_type": "SELL", "event_time": now + timedelta(minutes=15, seconds=30)},
    ]
    funding = {"a": "src1", "b": "src1", "c": "src1"}
    score = score_cluster_suspicion(["a", "b", "c"], events, funding)
    assert score > 60


def test_classify_cluster_prefers_bot_farm_when_extreme():
    label = classify_cluster(90.0, timing_tightness=0.95, shared_funding=0.9)
    assert label == "BOT_FARM"


def test_build_clusters_returns_cluster_dicts():
    now = datetime.utcnow()
    pairs = [("a", "b", 3), ("b", "c", 3)]
    events = [
        {"wallet_address": "a", "token_mint": "mint1", "event_type": "BUY", "event_time": now},
        {"wallet_address": "b", "token_mint": "mint1", "event_type": "BUY", "event_time": now + timedelta(seconds=1)},
        {"wallet_address": "c", "token_mint": "mint1", "event_type": "BUY", "event_time": now + timedelta(seconds=2)},
    ]
    clusters = build_clusters(pairs, events, {"a": "f1", "b": "f1", "c": "f2"})
    assert clusters
    assert "cluster_type" in clusters[0]
