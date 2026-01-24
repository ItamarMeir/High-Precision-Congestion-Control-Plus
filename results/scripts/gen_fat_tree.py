#!/usr/bin/env python3
"""Generate a classic k-ary fat-tree topology file in HPCC format."""

from __future__ import annotations

import argparse
from pathlib import Path


def generate_fat_tree(
    k: int,
    host_bw: str,
    switch_bw: str,
    delay: str,
    loss: str,
) -> list[str]:
    if k % 2 != 0 or k < 2:
        raise ValueError("k must be an even integer >= 2")

    pods = k
    edge_per_pod = k // 2
    agg_per_pod = k // 2
    hosts_per_edge = k // 2

    total_edge = pods * edge_per_pod
    total_agg = pods * agg_per_pod
    total_core = (k // 2) ** 2
    total_hosts = pods * edge_per_pod * hosts_per_edge

    edge_start = total_hosts
    agg_start = edge_start + total_edge
    core_start = agg_start + total_agg

    switch_ids = list(range(edge_start, core_start + total_core))

    links: list[tuple[int, int, str, str, str]] = []

    # Hosts to edge switches
    host_id = 0
    for pod in range(pods):
        for e in range(edge_per_pod):
            edge_id = edge_start + pod * edge_per_pod + e
            for _ in range(hosts_per_edge):
                links.append((host_id, edge_id, host_bw, delay, loss))
                host_id += 1

    # Edge to aggregation (full mesh within pod)
    for pod in range(pods):
        edge_ids = [edge_start + pod * edge_per_pod + e for e in range(edge_per_pod)]
        agg_ids = [agg_start + pod * agg_per_pod + a for a in range(agg_per_pod)]
        for edge_id in edge_ids:
            for agg_id in agg_ids:
                links.append((edge_id, agg_id, switch_bw, delay, loss))

    # Aggregation to core (per fat-tree spec)
    cores_per_group = k // 2
    for pod in range(pods):
        for a in range(agg_per_pod):
            agg_id = agg_start + pod * agg_per_pod + a
            for c in range(cores_per_group):
                core_id = core_start + a * cores_per_group + c
                links.append((agg_id, core_id, switch_bw, delay, loss))

    total_nodes = total_hosts + total_edge + total_agg + total_core
    total_links = len(links)

    lines = []
    lines.append(f"{total_nodes} {len(switch_ids)} {total_links}")
    lines.append(" ".join(str(s) for s in switch_ids))

    for u, v, bw, dly, ls in links:
        lines.append(f"{u} {v} {bw} {dly} {ls}")

    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a k-ary fat-tree topology")
    parser.add_argument("-k", type=int, default=4, help="Fat-tree parameter k (even)")
    parser.add_argument("--host-bw", default="100Gbps", help="Host-edge bandwidth")
    parser.add_argument("--switch-bw", default="400Gbps", help="Switch-switch bandwidth")
    parser.add_argument("--delay", default="1000ns", help="Link delay")
    parser.add_argument("--loss", default="0.000000", help="Link loss")
    parser.add_argument("-o", "--out", required=True, help="Output topology file")
    args = parser.parse_args()

    lines = generate_fat_tree(args.k, args.host_bw, args.switch_bw, args.delay, args.loss)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
