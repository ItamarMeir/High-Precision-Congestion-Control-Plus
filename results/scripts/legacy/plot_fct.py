#!/usr/bin/env python3
"""Visualize Flow Completion Time data"""
import matplotlib.pyplot as plt
import sys

def plot_fct(filename):
    flow_sizes = []
    fcts = []
    base_fcts = []
    slowdowns = []
    
    with open(filename, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 8:
                try:
                    # Format: src dst sport dport base_fct start_time fct size
                    size = int(parts[7])
                    fct = int(parts[6])
                    base_fct = int(parts[4])
                    slowdown = float(fct) / float(base_fct) if base_fct > 0 else 1
                    
                    flow_sizes.append(size)
                    fcts.append(fct / 1e6)  # Convert to ms
                    base_fcts.append(base_fct / 1e6)
                    slowdowns.append(slowdown)
                except:
                    continue
    
    if not flow_sizes:
        print("No data found in file")
        return
    
    # Create subplots
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # Plot 1: FCT vs Flow Size
    axes[0, 0].scatter(flow_sizes, fcts, alpha=0.6, s=50)
    axes[0, 0].set_xlabel('Flow Size (bytes)')
    axes[0, 0].set_ylabel('FCT (ms)')
    axes[0, 0].set_title('Flow Completion Time vs Flow Size')
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].set_xscale('log')
    axes[0, 0].set_yscale('log')
    
    # Plot 2: Slowdown vs Flow Size
    axes[0, 1].scatter(flow_sizes, slowdowns, alpha=0.6, s=50, color='orange')
    axes[0, 1].set_xlabel('Flow Size (bytes)')
    axes[0, 1].set_ylabel('Slowdown (FCT/Base FCT)')
    axes[0, 1].set_title('Slowdown vs Flow Size')
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].set_xscale('log')
    axes[0, 1].axhline(y=1, color='r', linestyle='--', label='Ideal (slowdown=1)')
    axes[0, 1].legend()
    
    # Plot 3: FCT histogram
    axes[1, 0].hist(fcts, bins=20, alpha=0.7, color='green', edgecolor='black')
    axes[1, 0].set_xlabel('FCT (ms)')
    axes[1, 0].set_ylabel('Count')
    axes[1, 0].set_title('FCT Distribution')
    axes[1, 0].grid(True, alpha=0.3)
    
    # Plot 4: Statistics summary
    axes[1, 1].axis('off')
    stats_text = "Flow Completion Time Statistics\\n\\n"
    stats_text += "Total Flows: {}\\n\\n".format(len(fcts))
    stats_text += "FCT (ms):\\n"
    stats_text += "  Min: {:.3f}\\n".format(min(fcts))
    stats_text += "  Max: {:.3f}\\n".format(max(fcts))
    stats_text += "  Mean: {:.3f}\\n".format(sum(fcts)/len(fcts))
    stats_text += "\\nSlowdown:\\n"
    stats_text += "  Min: {:.3f}\\n".format(min(slowdowns))
    stats_text += "  Max: {:.3f}\\n".format(max(slowdowns))
    stats_text += "  Mean: {:.3f}\\n".format(sum(slowdowns)/len(slowdowns))
    axes[1, 1].text(0.1, 0.5, stats_text, fontsize=12, family='monospace',
                    verticalalignment='center')
    
    plt.tight_layout()
    output_file = filename.replace('.txt', '.png')
    plt.savefig(output_file, dpi=150)
    print("Plot saved to: " + output_file)
    plt.close()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        plot_fct(sys.argv[1])
    else:
        plot_fct('simulation/mix/fct.txt')
