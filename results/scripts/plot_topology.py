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
            # If specified length matches num_switches, assume they are switch IDs
            if len(second_parts) == num_switches and num_switches > 0:
                try:
                    switch_ids = set(int(x) for x in second_parts)
                except ValueError:
                    switch_ids = set()

        # Create node labels and identify roles
        if switch_ids:
            for i in range(total_nodes):
                if i in switch_ids:
                    nodes[i] = f'S{i}'
                else:
                    nodes[i] = f'H{i}'
            num_switches = len(switch_ids)
            num_hosts = total_nodes - num_switches
        else:
            for i in range(total_nodes):
                if i < num_hosts:
                    nodes[i] = f'H{i}'
                else:
                    nodes[i] = f'S{i-num_hosts}'
            switch_ids = set(range(num_hosts, total_nodes))

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
                    delay = parts[3] if len(parts) > 3 else "0us"
                    links.append((src, dst, speed, delay))
                except (ValueError, IndexError):
                    continue

    return nodes, links, num_hosts, num_switches, switch_ids

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
                        # Expected format: src dst proto dst_port size start_time
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

def format_size(size_bytes):
    """Format flow size with appropriate units."""
    if size_bytes is None:
        return "N/A"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f} KB"
    else:
        return f"{size_bytes/(1024*1024):.1f} MB"

def plot_topology(topo_file, output_file='topology.png', flows_file=None):
    """Create network topology visualization."""
    nodes, links, num_hosts, num_switches, switch_ids = parse_topology(topo_file)
    
    # Parse flows
    flow_details = []
    active_nodes = set()
    if flows_file and os.path.exists(flows_file):
        flow_details = parse_flows_details(flows_file)
        active_nodes = {f['src'] for f in flow_details} | {f['dst'] for f in flow_details}
        print(f"Flows file provided: showing architecture with {len(flow_details)} active flows")

    G = nx.DiGraph()
    senders = {f['src'] for f in flow_details}
    receivers = {f['dst'] for f in flow_details}
    
    nodes_to_show = set(nodes.keys())
    for src, dst, _, _ in links:
        nodes_to_show.add(src)
        nodes_to_show.add(dst)

    G.add_nodes_from(nodes_to_show)
    
    link_info = {}
    for src, dst, speed, delay in links:
        G.add_edge(src, dst)
        link_info[(src, dst)] = (speed, delay)

    pos = {}
    pure_senders = sorted(list(senders - receivers))
    pure_receivers = sorted(list(receivers - senders))
    mixed_hosts = sorted(list((senders | receivers) - set(pure_senders) - set(pure_receivers)))
    idle_hosts = sorted([n for n in nodes_to_show if n not in switch_ids and n not in active_nodes])
    switches = sorted(list(switch_ids))

    def assign_layer_positions(node_list, y_coord):
        if not node_list: return
        n = len(node_list)
        width = 2.0
        step = width / (n + 1)
        for i, node in enumerate(node_list):
            pos[node] = (-1.0 + (i + 1) * step, y_coord)

    assign_layer_positions(pure_senders, 2.0)
    assign_layer_positions(switches, 1.0)
    assign_layer_positions(pure_receivers, 0.0)
    assign_layer_positions(mixed_hosts, 2.0)
    assign_layer_positions(idle_hosts, 0.0)

    for n in G.nodes():
        if n not in pos:
            pos[n] = (0, 0)

    fig = plt.figure(figsize=(15, 12))
    ax_graph = plt.axes([0.05, 0.35, 0.9, 0.6])
    ax_table = plt.axes([0.05, 0.05, 0.9, 0.25])
    ax_table.axis('off')

    plt.suptitle('Network Topology & Flow Configuration', fontsize=20, fontweight='bold', y=0.98)
    
    nx.draw_networkx_edges(G, pos, ax=ax_graph, edge_color='gray', width=1.5, alpha=0.6, 
                          arrows=True, arrowsize=20, connectionstyle="arc3,rad=0.1")
    
    edge_labels = {edge: f"{link_info[edge][0]}\n{link_info[edge][1]}" for edge in G.edges() if edge in link_info}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, ax=ax_graph, font_size=9, rotate=False)

    node_colors = []
    for n in G.nodes():
        if n in switch_ids:
            node_colors.append('#e74c3c')
        elif n in senders:
            node_colors.append('#3498db')
        elif n in receivers:
            node_colors.append('#2ecc71')
        else:
            node_colors.append('#bdc3c7')

    nx.draw_networkx_nodes(G, pos, ax=ax_graph, node_color=node_colors, node_size=1000, 
                          edgecolors='black', linewidths=2)
    
    labels = {i: nodes[i] for i in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, ax=ax_graph, font_size=11, font_weight='bold')
    ax_graph.axis('off')

    if flow_details:
        table_data = []
        for i, f in enumerate(flow_details):
            src_label = nodes.get(f['src'], f"H{f['src']}")
            dst_label = nodes.get(f['dst'], f"H{f['dst']}")
            size_fmt = format_size(f['size'])
            table_data.append([i, src_label, dst_label, f['dstport'], size_fmt, f"{f['start_time']:.1f} s"])

        col_labels = ['Flow ID', 'Source', 'Destination', 'Dest Port', 'Flow Size', 'Start Time']
        table = ax_table.table(cellText=table_data, colLabels=col_labels, loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1.2, 1.8)
        
        for (row, col), cell in table.get_celld().items():
            if row == 0:
                cell.set_text_props(weight='bold', color='white')
                cell.set_facecolor('#2c3e50')
            elif row % 2 == 0:
                cell.set_facecolor('#f2f2f2')

    plt.savefig(output_file, dpi=200, bbox_inches='tight')
    print(f"✅ Enhanced topology visualization saved to: {output_file}")
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
    
    output = args.out or topo_file.replace('.txt', '_analysis.png')
    plot_topology(topo_file, output, flows_file=args.flows)
