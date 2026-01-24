#!/usr/bin/env python3
"""
Advanced Fat-Tree Topology Visualization with Proper Hierarchy Detection
Identifies core, aggregation, edge switches and hosts based on fat-tree structure
"""

import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
import sys

class SmartFatTreeVisualizer:
    def __init__(self, topology_file, k=4):
        self.topology_file = topology_file
        self.k = k
        self.graph = nx.Graph()
        self.node_types = {}
        self.node_pods = {}
        self.parse_topology_file()
        self.identify_hierarchy()
        
    def parse_topology_file(self):
        """Parse the topology.txt file to build the network graph"""
        with open(self.topology_file, 'r') as f:
            lines = f.readlines()
        
        # First line: node/switch/link counts
        first_line = lines[0].strip().split()
        total_nodes = int(first_line[0])

        # Second line: explicit switch ID list (hosts are everything else)
        switch_ids = set(int(x) for x in lines[1].strip().split())

        # Add nodes with provisional type (switch/host)
        for i in range(total_nodes):
            if i in switch_ids:
                self.graph.add_node(i, is_switch=True)
            else:
                self.graph.add_node(i, is_switch=False)
        
        # Parse links (start from line 3)
        for line in lines[2:]:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                try:
                    src = int(parts[0])
                    dst = int(parts[1])
                    self.graph.add_edge(src, dst)
                except ValueError:
                    continue
        
        print(f"Parsed topology: {len(self.graph.nodes())} nodes, {len(self.graph.edges())} links")
    
    def identify_hierarchy(self):
        """Intelligently identify node hierarchy in fat-tree topology"""
        degrees = dict(self.graph.degree())

        # Hosts: explicit non-switch nodes (degree can vary, but here degree=1)
        hosts = [n for n, data in self.graph.nodes(data=True) if not data.get('is_switch', False)]
        for h in hosts:
            self.node_types[h] = 'host'
        print(f"Identified {len(hosts)} hosts")

        # Edge switches: switches that connect to at least one host
        edge_switches = []
        for n, data in self.graph.nodes(data=True):
            if not data.get('is_switch', False):
                continue
            neighbors = list(self.graph.neighbors(n))
            if any(nb in hosts for nb in neighbors):
                edge_switches.append(n)
                self.node_types[n] = 'edge'
        print(f"Identified {len(edge_switches)} edge switches")

        # Aggregation switches: switches that connect to edge switches but no hosts
        agg_switches = []
        for n, data in self.graph.nodes(data=True):
            if not data.get('is_switch', False) or self.node_types.get(n):
                continue
            neighbors = list(self.graph.neighbors(n))
            if any(nb in edge_switches for nb in neighbors) and not any(nb in hosts for nb in neighbors):
                agg_switches.append(n)
                self.node_types[n] = 'aggregation'
        print(f"Identified {len(agg_switches)} aggregation switches")

        # Core switches: remaining switches (should connect only to aggregation)
        core_switches = []
        for n, data in self.graph.nodes(data=True):
            if not data.get('is_switch', False) or self.node_types.get(n):
                continue
            core_switches.append(n)
            self.node_types[n] = 'core'
        print(f"Identified {len(core_switches)} core switches")
    
    def _hierarchical_pos(self):
        """Create hierarchical layout grouped by pod and layer"""
        pos = {}
        
        # Group by type
        type_nodes = {t: [] for t in ['core', 'aggregation', 'edge', 'host']}
        for node in self.graph.nodes():
            node_type = self.node_types.get(node, 'unknown')
            if node_type in type_nodes:
                type_nodes[node_type].append(node)
        
        # Assign positions layer by layer with better spacing
        layers = ['core', 'aggregation', 'edge', 'host']
        
        for level, layer in enumerate(layers):
            y = len(layers) - 1 - level
            nodes = sorted(type_nodes[layer])
            
            if not nodes:
                continue
            
            # Spread nodes along x-axis with good spacing
            n = len(nodes)
            x_positions = [(i + 1) / (n + 1) for i in range(n)]
            
            for node, x in zip(nodes, x_positions):
                # Add slight jitter to avoid overlapping nodes in same layer
                pos[node] = (x, y)
        
        return pos
    
    def visualize(self, output_file=None):
        """Visualize with improved hierarchical layout"""
        print("Creating advanced hierarchical fat-tree visualization...")
        
        pos = self._hierarchical_pos()
        
        fig, ax = plt.subplots(figsize=(20, 14))
        
        # Color scheme
        type_colors = {
            'core': '#FF6B6B',           # Red
            'aggregation': '#FFD93D',    # Yellow
            'edge': '#6BCB77',           # Green
            'host': '#4D96FF'            # Blue
        }
        
        # Draw nodes by type with better visibility
        for node_type in ['core', 'aggregation', 'edge', 'host']:
            nodes = [n for n in self.graph.nodes() if self.node_types.get(n) == node_type]
            if nodes:
                nx.draw_networkx_nodes(
                    self.graph, pos,
                    nodelist=nodes,
                    node_color=type_colors[node_type],
                    node_size=200 if node_type == 'host' else 400,
                    edgecolors='black',
                    linewidths=0.5,
                    label=node_type.capitalize(),
                    ax=ax
                )
        
        # Draw edges with transparency
        nx.draw_networkx_edges(
            self.graph, pos,
            width=0.3,
            alpha=0.2,
            edge_color='black',
            ax=ax
        )
        
        # Add labels only for non-host nodes if too many nodes
        if len(self.graph.nodes()) < 100:
            labels = {n: str(n) for n in self.graph.nodes()}
            nx.draw_networkx_labels(self.graph, pos, labels, font_size=4, ax=ax)
        else:
            # Just label core and agg switches
            labels = {n: str(n) for n in self.graph.nodes() 
                     if self.node_types.get(n) in ['core', 'aggregation']}
            nx.draw_networkx_labels(self.graph, pos, labels, font_size=5, ax=ax)
        
        # Title
        type_counts = {}
        for t in self.node_types.values():
            type_counts[t] = type_counts.get(t, 0) + 1
        
        title = f'Fat-Tree (K={self.k}) Network Topology - Hierarchical View\n'
        title += f'Core: {type_counts.get("core", 0)}, Agg: {type_counts.get("aggregation", 0)}, '
        title += f'Edge: {type_counts.get("edge", 0)}, Hosts: {type_counts.get("host", 0)}'
        
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
        
        # Legend with better positioning
        handles = [
            mpatches.Patch(facecolor=type_colors['core'], edgecolor='black', label=f'Core ({type_counts.get("core", 0)})'),
            mpatches.Patch(facecolor=type_colors['aggregation'], edgecolor='black', label=f'Aggregation ({type_counts.get("aggregation", 0)})'),
            mpatches.Patch(facecolor=type_colors['edge'], edgecolor='black', label=f'Edge ({type_counts.get("edge", 0)})'),
            mpatches.Patch(facecolor=type_colors['host'], edgecolor='black', label=f'Hosts ({type_counts.get("host", 0)})')
        ]
        ax.legend(handles=handles, loc='upper left', fontsize=11, framealpha=0.95)
        
        # Add layer labels
        ax.text(0.02, 0.98, 'CORE\n(Top)', transform=ax.transAxes, fontsize=10, 
               verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        ax.text(0.02, 0.25, 'HOSTS\n(Bottom)', transform=ax.transAxes, fontsize=10,
               verticalalignment='top', bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
        
        ax.axis('off')
        plt.tight_layout()
        
        if output_file:
            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            print(f"✅ Saved to: {output_file}")
        
        plt.close()
    
    def print_topology_info(self):
        """Print detailed information"""
        type_counts = {}
        for t in self.node_types.values():
            type_counts[t] = type_counts.get(t, 0) + 1
        
        print("\n" + "="*70)
        print("FAT-TREE TOPOLOGY ANALYSIS".center(70))
        print("="*70)
        print(f"Total Nodes:        {len(self.graph.nodes()):>6d}")
        print(f"Total Links:        {len(self.graph.edges()):>6d}")
        print(f"Parameter K:        {self.k:>6d}")
        print("-"*70)
        print("Node Distribution:")
        for node_type in ['core', 'aggregation', 'edge', 'host']:
            count = type_counts.get(node_type, 0)
            pct = 100 * count / len(self.graph.nodes())
            print(f"  {node_type.capitalize():15s}: {count:>4d} nodes ({pct:>5.1f}%)")
        print("-"*70)
        print(f"Average Node Degree: {sum(dict(self.graph.degree()).values()) / len(self.graph.nodes()):>5.2f}")
        print("="*70 + "\n")

def main():
    if len(sys.argv) > 1:
        topology_file = sys.argv[1]
    else:
        topology_file = '../data/fat.txt'
    
    visualizer = SmartFatTreeVisualizer(topology_file, k=4)
    visualizer.print_topology_info()
    
    output_file = topology_file.replace('.txt', '_smart_hierarchy.png')
    visualizer.visualize(output_file=output_file)

if __name__ == '__main__':
    main()
