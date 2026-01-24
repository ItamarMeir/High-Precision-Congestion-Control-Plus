#!/usr/bin/env python3
"""
Hierarchical Fat-Tree Topology Visualization
Creates a clear hierarchical layout showing core, aggregation, edge switches, and hosts
"""

import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
import sys

class FatTreeVisualizer:
    def __init__(self, topology_file, k=4):
        self.topology_file = topology_file
        self.k = k
        self.graph = nx.Graph()
        self.node_types = {}
        self.node_pods = {}
        self.parse_topology_file()
        
    def parse_topology_file(self):
        """Parse the topology.txt file to build the network graph"""
        with open(self.topology_file, 'r') as f:
            lines = f.readlines()
        
        # First line contains node counts
        first_line = lines[0].strip().split()
        total_nodes = int(first_line[0])

        # Optional second line: explicit switch ID list (fat-tree format)
        switch_ids = set()
        if len(lines) > 1:
            second_parts = lines[1].strip().split()
            try:
                if len(second_parts) > 1:
                    switch_ids = set(int(x) for x in second_parts)
            except ValueError:
                switch_ids = set()

        # Add all nodes with provisional type
        for i in range(total_nodes):
            self.graph.add_node(i, is_switch=(i in switch_ids))
        
        # Parse links starting from line 2 (after node counts and type indicator)
        link_count = 0
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
                    link_count += 1
                except ValueError:
                    continue
        
        print(f"Parsed topology: {len(self.graph.nodes())} nodes, {len(self.graph.edges())} links")
        
        # Infer node types based on connectivity and structure
        self._infer_node_types()
    
    def _infer_node_types(self):
        """Infer node types (host, edge, aggregation, core) based on topology structure"""
        # If explicit switch list is present, classify based on neighbors
        nodes_with_flag = list(self.graph.nodes(data=True))
        switch_ids = {n for n, data in nodes_with_flag if data.get('is_switch', False)}

        if switch_ids:
            hosts = [n for n in self.graph.nodes() if n not in switch_ids]
            for h in hosts:
                self.node_types[h] = 'host'

            edge_switches = []
            for s in switch_ids:
                if any(nb in hosts for nb in self.graph.neighbors(s)):
                    edge_switches.append(s)
                    self.node_types[s] = 'edge'

            agg_switches = []
            for s in switch_ids:
                if s in edge_switches:
                    continue
                neighbors = list(self.graph.neighbors(s))
                if any(nb in edge_switches for nb in neighbors) and not any(nb in hosts for nb in neighbors):
                    agg_switches.append(s)
                    self.node_types[s] = 'aggregation'

            for s in switch_ids:
                if s not in self.node_types:
                    self.node_types[s] = 'core'
        else:
            degrees = dict(self.graph.degree())
            for node in self.graph.nodes():
                degree = degrees[node]
                if degree == 1:
                    self.node_types[node] = 'host'
                elif degree <= 4:
                    self.node_types[node] = 'edge'
                elif degree <= 8:
                    self.node_types[node] = 'aggregation'
                else:
                    self.node_types[node] = 'core'
    
    def _hierarchical_pos(self):
        """Create a hierarchical layout: core (top) -> agg -> edge -> hosts (bottom)"""
        pos = {}
        
        # Separate nodes by type
        type_nodes = {t: [] for t in ['core', 'aggregation', 'edge', 'host']}
        for node in self.graph.nodes():
            node_type = self.node_types.get(node, 'unknown')
            if node_type in type_nodes:
                type_nodes[node_type].append(node)
        
        # Assign positions layer by layer
        layers = ['core', 'aggregation', 'edge', 'host']
        y_spacing = 1.0
        
        for level, layer in enumerate(layers):
            y = len(layers) - 1 - level
            nodes = sorted(type_nodes[layer])
            
            if not nodes:
                continue
            
            # Spread nodes evenly along x-axis
            n = len(nodes)
            for i, node in enumerate(nodes):
                x = (i + 1) / (n + 1)
                pos[node] = (x, y)
        
        return pos
    
    def visualize(self, output_file=None):
        """Visualize the fat-tree topology with hierarchical layout"""
        print("Creating hierarchical fat-tree visualization...")
        
        pos = self._hierarchical_pos()
        
        # Create figure
        fig, ax = plt.subplots(figsize=(16, 12))
        
        # Color mapping for node types
        type_colors = {
            'host': 'lightblue',
            'edge': 'lightgreen',
            'aggregation': 'lightyellow',
            'core': 'lightcoral'
        }
        
        # Draw nodes by type (so we can control colors)
        for node_type, color in type_colors.items():
            nodes = [n for n in self.graph.nodes() if self.node_types.get(n) == node_type]
            if nodes:
                nx.draw_networkx_nodes(
                    self.graph, pos, 
                    nodelist=nodes,
                    node_color=color,
                    node_size=300,
                    label=node_type.capitalize(),
                    ax=ax
                )
        
        # Draw edges
        nx.draw_networkx_edges(
            self.graph, pos,
            width=0.5,
            alpha=0.3,
            edge_color='gray',
            ax=ax
        )
        
        # Draw labels (optional - can be cluttered with many nodes)
        if len(self.graph.nodes()) <= 50:
            nx.draw_networkx_labels(
                self.graph, pos,
                font_size=6,
                ax=ax
            )
        
        # Title and legend
        plt.title(f'Fat-Tree (K={self.k}) Hierarchical Topology\n'
                 f'{len(self.graph.nodes())} nodes, {len(self.graph.edges())} links',
                 fontsize=14, fontweight='bold')
        
        # Create legend
        handles = [
            mpatches.Patch(color='lightcoral', label='Core Switches'),
            mpatches.Patch(color='lightyellow', label='Aggregation Switches'),
            mpatches.Patch(color='lightgreen', label='Edge Switches'),
            mpatches.Patch(color='lightblue', label='Hosts')
        ]
        ax.legend(handles=handles, loc='upper right', fontsize=10)
        
        ax.set_title(f'Hierarchical Layout: Core (Top) → Aggregation → Edge → Hosts (Bottom)',
                    fontsize=10, style='italic', pad=20)
        ax.axis('off')
        
        plt.tight_layout()
        
        # Save if output file specified
        if output_file:
            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            print(f"✅ Visualization saved to: {output_file}")
        
        plt.close()
    
    def print_topology_info(self):
        """Print detailed topology information"""
        type_counts = {}
        for node_type in self.node_types.values():
            type_counts[node_type] = type_counts.get(node_type, 0) + 1
        
        print("\n" + "="*60)
        print("FAT-TREE TOPOLOGY INFORMATION")
        print("="*60)
        print(f"Total Nodes: {len(self.graph.nodes())}")
        print(f"Total Links: {len(self.graph.edges())}")
        print(f"Parameter K: {self.k}")
        print("\nNode Distribution:")
        for node_type in ['core', 'aggregation', 'edge', 'host']:
            count = type_counts.get(node_type, 0)
            print(f"  • {node_type.capitalize():15s}: {count:4d}")
        
        print("\nNetwork Properties:")
        print(f"  • Average Degree: {sum(dict(self.graph.degree()).values()) / len(self.graph.nodes()):.2f}")
        if nx.is_connected(self.graph):
            print(f"  • Network Diameter: {nx.diameter(self.graph)}")
        print("="*60 + "\n")

def main():
    if len(sys.argv) > 1:
        topology_file = sys.argv[1]
    else:
        topology_file = '../data/fat.txt'
    
    # Create visualizer
    visualizer = FatTreeVisualizer(topology_file, k=4)
    visualizer.print_topology_info()
    
    # Generate visualization
    output_file = topology_file.replace('.txt', '_hierarchical.png')
    visualizer.visualize(output_file=output_file)

if __name__ == '__main__':
    main()
