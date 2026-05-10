"""Wallet clustering using co-purchase graphs."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime

import networkx as nx

try:
    import community as community_louvain
except Exception:  # pragma: no cover
    community_louvain = None


def build_copurchase_graph(
    copurchase_pairs: list[tuple[str, str, int]],
    min_shared_tokens: int = 2,
) -> nx.Graph:
    graph = nx.Graph()
    for wallet_a, wallet_b, shared_count in copurchase_pairs:
        if shared_count < min_shared_tokens:
            continue
        graph.add_edge(wallet_a, wallet_b, weight=shared_count)
    return graph


def run_louvain(graph: nx.Graph) -> dict[str, int]:
    """Returns wallet -> community id."""
    if graph.number_of_nodes() == 0:
        return {}
    if community_louvain is not None:
        return community_louvain.best_partition(graph, weight="weight")

    communities = list(nx.algorithms.community.greedy_modularity_communities(graph, weight="weight"))
    partition: dict[str, int] = {}
    for idx, members in enumerate(communities):
        for member in members:
            partition[str(member)] = idx
    return partition


def _timing_tightness(member_wallets: list[str], wallet_events: list[dict]) -> float:
    buy_times = [
        event["event_time"]
        for event in wallet_events
        if event.get("wallet_address") in member_wallets and event.get("event_type", "BUY") == "BUY"
    ]
    if len(buy_times) < 2:
        return 0.0
    ts = [float(dt.timestamp()) for dt in buy_times]
    mean = sum(ts) / len(ts)
    variance = sum((value - mean) ** 2 for value in ts) / len(ts)
    std_dev = math.sqrt(variance)
    return max(0.0, 1.0 - min(1.0, std_dev / 300.0))


def _shared_funding(member_wallets: list[str], funding_sources: dict[str, str]) -> float:
    sources = [funding_sources.get(wallet) for wallet in member_wallets if funding_sources.get(wallet)]
    if not sources or not member_wallets:
        return 0.0
    most_common = Counter(sources).most_common(1)[0][1]
    return most_common / len(member_wallets)


def _copurchase_rate(member_wallets: list[str], wallet_events: list[dict]) -> float:
    token_sets = {
        wallet: {
            event.get("token_mint")
            for event in wallet_events
            if event.get("wallet_address") == wallet and event.get("token_mint")
        }
        for wallet in member_wallets
    }
    all_tokens = set().union(*token_sets.values()) if token_sets else set()
    if not all_tokens or len(member_wallets) < 2:
        return 0.0
    overlap_sum = 0.0
    comparisons = 0
    wallets = list(token_sets)
    for idx, wallet_a in enumerate(wallets):
        for wallet_b in wallets[idx + 1 :]:
            union = token_sets[wallet_a] | token_sets[wallet_b]
            if not union:
                continue
            overlap_sum += len(token_sets[wallet_a] & token_sets[wallet_b]) / len(union)
            comparisons += 1
    if comparisons == 0:
        return 0.0
    return overlap_sum / comparisons


def _sync_exits(member_wallets: list[str], wallet_events: list[dict]) -> float:
    sell_times = sorted(
        event["event_time"]
        for event in wallet_events
        if event.get("wallet_address") in member_wallets and event.get("event_type") == "SELL"
    )
    if len(sell_times) < 2 or not member_wallets:
        return 0.0
    grouped = 1
    for previous, current in zip(sell_times, sell_times[1:]):
        if (current - previous).total_seconds() <= 600:
            grouped += 1
    return min(1.0, grouped / len(member_wallets))


def _social_diversity(member_wallets: list[str], wallet_events: list[dict]) -> float:
    social_types = {
        event.get("social_type")
        for event in wallet_events
        if event.get("wallet_address") in member_wallets and event.get("social_type")
    }
    return max(0.0, 1.0 - min(1.0, len(social_types) / 5.0))


def score_cluster_suspicion(
    member_wallets: list[str],
    wallet_events: list[dict],
    funding_sources: dict[str, str],
) -> float:
    timing_tightness = _timing_tightness(member_wallets, wallet_events)
    shared_funding = _shared_funding(member_wallets, funding_sources)
    copurchase_rate = _copurchase_rate(member_wallets, wallet_events)
    sync_exits = _sync_exits(member_wallets, wallet_events)
    social_diversity = _social_diversity(member_wallets, wallet_events)
    score = (
        0.30 * timing_tightness
        + 0.25 * shared_funding
        + 0.20 * copurchase_rate
        + 0.15 * sync_exits
        + 0.10 * social_diversity
    )
    return max(0.0, min(100.0, score * 100.0))


def classify_cluster(suspicion_score: float, timing_tightness: float, shared_funding: float) -> str:
    normalized = suspicion_score / 100.0
    if normalized > 0.80 and timing_tightness > 0.9:
        return "BOT_FARM"
    if shared_funding > 0.8:
        return "DEV_SUSPECT"
    if normalized > 0.70:
        return "CABAL_SUSPECT"
    if normalized < 0.30:
        return "SMART_MONEY"
    return "UNKNOWN"


def build_clusters(
    copurchase_pairs: list[tuple[str, str, int]],
    wallet_events: list[dict],
    funding_sources: dict[str, str],
) -> list[dict]:
    graph = build_copurchase_graph(copurchase_pairs)
    partition = run_louvain(graph)
    grouped: dict[int, list[str]] = defaultdict(list)
    for wallet, cluster_id in partition.items():
        grouped[cluster_id].append(wallet)

    clusters = []
    for cluster_id, members in grouped.items():
        timing_tightness = _timing_tightness(members, wallet_events)
        shared_funding = _shared_funding(members, funding_sources)
        suspicion_score = score_cluster_suspicion(members, wallet_events, funding_sources)
        cluster_type = classify_cluster(suspicion_score, timing_tightness, shared_funding)
        clusters.append(
            {
                "cluster_id": cluster_id,
                "cluster_type": cluster_type,
                "suspicion_score": round(suspicion_score, 2),
                "members": sorted(members),
            }
        )
    return clusters
