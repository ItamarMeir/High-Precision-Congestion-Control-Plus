#!/usr/bin/env python3
"""
Visualization of network topology from simulation config
Shows node connections and link speeds
Optionally filters to show only nodes involved in specified flows
"""

import matplotlib.pyplot as plt
import networkx as nx
import sys
import os
from matplotlib.patches import FancyBboxPatch
import argparse

def parse_topology(topo_file):
    """Parse topology file (supports both standard and fat-tree formats)."""
    nodes = {}
    links = []
    num_hosts = 0
    num_switches = 0
    switch_ids = set()

    with open(topo_file, 'r') as f:
        lines = f.readlines()

        # First line: node counts
        first = lines[0].strip().split()
        total_nodes = int(first[0])
        num_switches = int(first[1]) if len(first) > 1 else 0
        num_hosts = total_nodes - num_switches

        # Second line: either a switch-id list (fat.txt) or a type indicator (topology.txt)
        if len(lines) > 1:
            second_parts = lines[1].strip().split()
            if len(second_parts) > 1 and len(second_parts) == num_switches:
                try:
                    switch_ids = set(int(x) for x in second_parts)
                except ValueError:
                    switch_ids = set()

        # Create node labels
        if switch_ids:
            for i in range(total_nodes):
                if i in switch_ids:
                    nodes[i] = f'S{i}'
                else:
                    nodes[i] = f'H{i}'
            num_hosts = total_nodes - len(switch_ids)
            num_switches = len(switch_ids)
        else:
            for i in range(total_nodes):
                if i < num_hosts:
                    nodes[i] = f'H{i}'  # Host
                else:
                    nodes[i] = f'S{i-num_hosts}'  # Switch

        # Parse links
        for line_idx in range(2, len(lines)):
            line = lines[line_idx].strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 3:
                try:
                    src = int(parts[0])
                    dst = int(parts[1])
                    speed = parts[2]
                    links.append((src, dst, speed))
                except (ValueError, IndexError):
                    continue

    return nodes, links, num_hosts, num_switches

def _extract_topology_from_config(config_file):
    try:
        with open(config_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split()
                    if parts[0] == 'TOPOLOGY_FILE' and len(parts) >= 2:
                        topo_path = parts[1]
                        if not os.path.isabs(topo_path):
                            base_dir = os.path.dirname(os.path.abspath(config_file))
                            if topo_path.startswith('mix/') and os.path.basename(base_dir) == 'mix':
                                topo_path = os.path.normpath(os.path.join(os.path.dirname(base_dir), topo_path))
                            else:
                                topo_path = os.path.normpath(os.path.join(base_dir, topo_path))
                        return topo_path
    except OSError:
        return None
    return None

def parse_flows(flows_file):
    """Parse flows file and return set of involved node IDs.
    
    Format:
    <num_flows>
    <src0> <dst0> <port0> <port0_dst> <size0> <start_time0>
    <src1> <dst1> <port1> <port1_dst> <size1> <start_time1>
    ...
    """
    active_nodes = set()
    try:
        with open(flows_file, 'r') as f:
            lines = f.readlines()
            if len(lines) > 0:
                try:
                    num_flows = int(lines[0].strip())
                except ValueError:
                    return active_nodes
                
                for i in range(1, min(1 + num_flows, len(lines))):
                    parts = lines[i].strip().split()
                    if len(parts) >= 2:
                        try:
                            src = int(parts[0])
                            dst = int(parts[1])
                            active_nodes.add(src)
                            active_nodes.add(dst)
                        except ValueError:
                            continue
    except (OSError, IOError):
        pass
    
    return active_nodes


def parse_flows_details(flows_file):
    """Return list of flow dicts with keys: src, dst, dstport, size, start_time"""
    flows = []
    try:
        with open(flows_file, 'r') as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            if not lines:
                return flows
            try:
                num_flows = int(lines[0])
            except ValueError:
                num_flows = len(lines)
            for i in range(1, min(1 + num_flows, len(lines))):
                parts = lines[i].split()
                if len(parts) >= 6:
                    try:
                        src = int(parts[0])
                        dst = int(parts[1])
                        # Expected format: src dst <proto> dst_port size start_time
                        dstport = int(parts[3]) if parts[3].isdigit() else None
                        size = int(parts[4]) if parts[4].isdigit() else None
                        start_time = int(parts[5]) if parts[5].isdigit() else None
                    except (ValueError, IndexError):
                        continue
                    flows.append({
                        'src': src,
                        'dst': dst,
                        'dstport': dstport,
                        'size': size,
                        'start_time': start_time,
                    })
    except (OSError, IOError):
        pass
    return flows


def plot_topology(topo_file, output_file='topology.png', flows_file=None):
    """Create network topology visualization
    
    Args:
        topo_file: Path to topology file
        output_file: Output PNG file path
        flows_file: Optional flows file - if provided, only show nodes involved in flows
    """
    nodes, links, num_hosts, num_switches = parse_topology(topo_file)
    
    # Parse flows if provided to filter nodes
    active_nodes_from_flows = None
    if flows_file and os.path.exists(flows_file):
        active_nodes_from_flows = parse_flows(flows_file)
        print(f"Flows file provided: showing only active nodes {sorted(active_nodes_from_flows)}")
    
    # Get all node IDs that actually appear in links
    all_node_ids = set(nodes.keys())
    for src, dst, _ in links:
        all_node_ids.add(src)
        all_node_ids.add(dst)
    
    # Update node count if needed
    max_node = max(all_node_ids) if all_node_ids else 0
    for i in range(max_node + 1):
        if i not in nodes:
            nodes[i] = f'Node{i}'
    
    # Filter links and nodes if flows file provided
    if active_nodes_from_flows:
        # Include any link that touches an active flow node, and include both
        # endpoints of those links so switch nodes are shown as well.
        filtered_links = []
        nodes_to_show = set(active_nodes_from_flows)
        for src, dst, speed in links:
            if (src in active_nodes_from_flows) or (dst in active_nodes_from_flows):
                filtered_links.append((src, dst, speed))
                nodes_to_show.add(src)
                nodes_to_show.add(dst)
        links = filtered_links
    else:
        nodes_to_show = all_node_ids
    
    # Create graph
    G = nx.DiGraph()
    G.add_nodes_from(nodes_to_show)
    
    # Add edges
    speeds = {}
    for src, dst, speed in links:
        if src in nodes_to_show and dst in nodes_to_show:
            G.add_edge(src, dst)
            speeds[(src, dst)] = speed
    
    # Layout
    if len(G.nodes()) > 100:
        # Circular layout for dense topologies
        pos = nx.circular_layout(G)
    elif len(G.nodes()) <= 3:
        # Simple layout for very small graphs
        pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
    else:
        # Use a spring layout
        pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
    
    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
    
    # ===== Subplot 1: Topology Graph =====
    title = 'Active Flow Topology' if active_nodes_from_flows else 'Network Topology (Full View)'
    ax1.set_title(title, fontsize=14, fontweight='bold')
    
    # Draw edges
    nx.draw_networkx_edges(G, pos, ax=ax1, edge_color='gray', 
                          width=1.5, alpha=0.7, arrows=True, 
                          arrowsize=15, arrowstyle='->')
    
    # Edge labels: show speed on each edge
    edge_labels = {}
    for u, v in G.edges():
        if (u, v) in speeds:
            edge_labels[(u, v)] = speeds[(u, v)]
    if edge_labels:
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, ax=ax1, font_size=9)
    
    # Color nodes: hosts=blue, switches=red, active flows=bright
    node_colors = []
    for node in G.nodes():
        if active_nodes_from_flows:
            # For flow topology, highlight active nodes
            if node < num_hosts:
                node_colors.append('dodgerblue')  # Active host - bright blue
            else:
                node_colors.append('crimson')  # Active switch - bright red
        else:
            # For full topology
            if node < num_hosts:
                node_colors.append('lightblue')  # Host
            else:
                node_colors.append('lightcoral')  # Switch
    
    nx.draw_networkx_nodes(G, pos, ax=ax1, node_color=node_colors, 
                          node_size=500 if len(G.nodes()) <= 10 else 300, 
                          edgecolors='black', linewidths=2)
    
    # Labels
    labels = {i: nodes[i] for i in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, ax=ax1, font_size=10, font_weight='bold')
    
    ax1.set_xlabel(f'Nodes: {len(G.nodes())} | Links: {len(G.edges())}', fontsize=11)
    ax1.axis('off')
    
    # ===== Subplot 2: Statistics =====
    ax2.axis('off')
    ax2.set_title('Topology Statistics', fontsize=14, fontweight='bold')
    
    # Count links by speed
    speed_counts = {}
    for src, dst, speed in links:
        speed_counts[speed] = speed_counts.get(speed, 0) + 1
    
    # Statistics text
    flow_details_text = ""
    if active_nodes_from_flows:
        stats_text = f"""
ACTIVE FLOW TOPOLOGY

Active Nodes: {len(G.nodes())}
"""
        for node in sorted(G.nodes()):
            node_type = "Host" if node < num_hosts else "Switch"
            stats_text += f"  • Node {node} ({nodes.get(node,'')}) - {node_type}\n"
        # Add flow legend/details
        flows_list = parse_flows_details(flows_file) if flows_file else []
        def _fmt_size(b):
            try:
                b = int(b)
            except Exception:
                return str(b)
            if b >= 1024**2:
                return f"{b} B ({b/1024**2:.1f} MB)"
            if b >= 1024:
                return f"{b} B ({b/1024:.1f} KB)"
            return f"{b} B"

        if flows_list:
            flow_details_text += "\nFLOWS:\n"
            for i, fdict in enumerate(flows_list):
                flow_details_text += (
                    f"  {i+1}. {fdict.get('src')} -> {fdict.get('dst')} "
                    f"(dstport={fdict.get('dstport')}, size={_fmt_size(fdict.get('size'))})\n"
                )
            stats_text += flow_details_text
    else:
        stats_text = f"""
TOPOLOGY INFORMATION

Total Nodes: {len(G.nodes())}
  └─ Hosts: {num_hosts}
  └─ Switches: {num_switches}
"""
    
    stats_text += f"""
Total Links: {len(links)}

Link Speeds:
"""
    
    for speed, count in sorted(speed_counts.items()):
        stats_text += f"  • {speed}: {count} links\n"
    
    # Add node type legend
    stats_text += f"""

NODE TYPES:
  • H<n> = Host (endpoint)
  • S<n> = Switch (forwarder)
"""
    
    ax2.text(0.05, 0.95, stats_text, transform=ax2.transAxes,
            fontsize=11, verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"✅ Topology visualization saved to: {output_file}")
    if active_nodes_from_flows:
        print(f"   - {len(G.nodes())} active nodes for flows")
    else:
        print(f"   - {len(G.nodes())} nodes ({num_hosts} hosts, {num_switches} switches)")
    print(f"   - {len(links)} links")
    plt.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Visualize network topology')
    parser.add_argument('topo_file', nargs='?', default='../data/topology.txt',
                        help='Path to topology file')
    parser.add_argument('--flows', help='Path to flows file (shows only active flow nodes)')
    parser.add_argument('--out', help='Output PNG file path')
    
    args = parser.parse_args()
    
    topo_file = args.topo_file
    if topo_file.endswith('.txt') and 'config' in topo_file:
        topo_file = _extract_topology_from_config(topo_file) or topo_file
    
    output = args.out or topo_file.replace('.txt', '.png')
    plot_topology(topo_file, output, flows_file=args.flows)
