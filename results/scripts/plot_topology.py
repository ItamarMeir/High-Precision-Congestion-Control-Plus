#!/usr/bin/env python3
"""
Visualization of network topology from simulation config
Shows node connections and link speeds
"""

import matplotlib.pyplot as plt
import networkx as nx
import sys
import os
from matplotlib.patches import FancyBboxPatch

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


def plot_topology(topo_file, output_file='topology.png'):
    """Create network topology visualization"""
    nodes, links, num_hosts, num_switches = parse_topology(topo_file)
    
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
    
    # Create graph
    G = nx.DiGraph()
    G.add_nodes_from(nodes.keys())
    
    # Add edges
    speeds = {}
    for src, dst, speed in links:
        G.add_edge(src, dst)
        speeds[(src, dst)] = speed
    
    # Layout: circular for large networks, hierarchical for small
    if len(G.nodes()) > 100:
        # Circular layout for dense topologies
        pos = nx.circular_layout(G)
    else:
        # Use a spring layout
        pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
    
    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
    
    # ===== Subplot 1: Full Topology Graph =====
    ax1.set_title('Network Topology (Full View)', fontsize=14, fontweight='bold')
    
    # Draw edges
    nx.draw_networkx_edges(G, pos, ax=ax1, edge_color='gray', 
                          width=1, alpha=0.6, arrows=True, 
                          arrowsize=10, arrowstyle='->')
    
    # Color nodes: hosts=blue, switches=red
    node_colors = []
    for node in G.nodes():
        if node < num_hosts:
            node_colors.append('lightblue')  # Host
        else:
            node_colors.append('lightcoral')  # Switch
    
    nx.draw_networkx_nodes(G, pos, ax=ax1, node_color=node_colors, 
                          node_size=300, edgecolors='black', linewidths=2)
    
    # Labels
    labels = {i: nodes[i] for i in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, ax=ax1, font_size=8)
    
    ax1.set_xlabel(f'Hosts: {num_hosts} | Switches: {num_switches} | Total Nodes: {len(G.nodes())}', fontsize=11)
    ax1.axis('off')
    
    # ===== Subplot 2: Statistics =====
    ax2.axis('off')
    ax2.set_title('Topology Statistics', fontsize=14, fontweight='bold')
    
    # Count links by speed
    speed_counts = {}
    for src, dst, speed in links:
        speed_counts[speed] = speed_counts.get(speed, 0) + 1
    
    # Statistics text
    stats_text = f"""
TOPOLOGY INFORMATION

Total Nodes: {len(G.nodes())}
  └─ Hosts: {num_hosts}
  └─ Switches: {num_switches}

Total Links: {len(links)}

Link Speeds:
"""
    
    for speed, count in sorted(speed_counts.items()):
        stats_text += f"  • {speed}: {count} links\n"
    
    # Add node type legend
    stats_text += f"""

NODE TYPES:
  • H<n> = Host (compute node)
  • S<n> = Switch (network switch)

LINK STRUCTURE:
  Format: src → dst
  Switches connect multiple hosts
  for fault-tolerant communication
"""
    
    ax2.text(0.05, 0.95, stats_text, transform=ax2.transAxes,
            fontsize=11, verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"✅ Topology visualization saved to: {output_file}")
    print(f"   - {len(G.nodes())} nodes ({num_hosts} hosts, {num_switches} switches)")
    print(f"   - {len(links)} links")
    plt.close()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        topo_arg = sys.argv[1]
        if topo_arg.endswith('.txt') and 'config' in topo_arg:
            topo_file = _extract_topology_from_config(topo_arg) or topo_arg
        else:
            topo_file = topo_arg
    else:
        topo_file = '../data/topology.txt'
    
    output = topo_file.replace('.txt', '.png')
    plot_topology(topo_file, output)
