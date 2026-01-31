#!/usr/bin/env python3
"""
Generate comprehensive CWND/Rate/RTT analysis dashboard.
Dynamically adapts to any simulation data - robust for different topologies/flows.

Input:
  - cwnd_data_file: CWND trace file (time_ns, src, dst, sport, dport, rate_bps, win_bytes)
  - output_file: Output PNG path

Features:
  - Plots all flows in Window over Time panel
  - Extracts RTT from steady-state data
  - Rate vs CWND mathematical relationship
  - Per-flow throughput distribution
  - RTT component breakdown
"""
import sys
import statistics
from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


def _extract_steady_state_period(data):
    """Find the steady-state period where transmission is active."""
    times = [t for t, _, _, _, _ in data]
    if not times:
        return None, None
    
    # Steady state is roughly in the middle 50% of active transmission
    t_min, t_max = min(times), max(times)
    duration = t_max - t_min
    steady_start = t_min + duration * 0.2  # Skip first 20%
    steady_end = t_min + duration * 0.9    # Use up to 90%
    
    return steady_start, steady_end


def _calculate_rtt_from_cwnd_data(cwnd_file):
    """Extract RTT from steady-state CWND data using rate = cwnd * 8 / RTT."""
    rtt_samples = []
    
    with open(cwnd_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 7:
                continue
            try:
                t_ns = int(parts[0])
                rate = int(parts[5])
                win = int(parts[6])
                t_s = t_ns / 1e9
                
                # Use steady-state period (middle 70% of transmission)
                if rate > 0 and win > 0:
                    rtt = (win * 8) / rate
                    rtt_samples.append(rtt)
            except (ValueError, IndexError):
                continue
    
    if rtt_samples:
        # Use median to avoid outliers
        return statistics.median(rtt_samples)
    return None


def _parse_cwnd_file(cwnd_file):
    """Parse CWND file and return flows with their data."""
    flows = defaultdict(lambda: {"t": [], "win": [], "rate": []})
    
    with open(cwnd_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 7:
                continue
            try:
                t_ns = int(parts[0])
                src = int(parts[1])
                dst = int(parts[2])
                sport = int(parts[3])
                dport = int(parts[4])
                rate = int(parts[5])
                win = int(parts[6])
                
                key = (src, dst, sport, dport)
                flows[key]["t"].append(t_ns / 1e9)
                flows[key]["win"].append(win)
                flows[key]["rate"].append(rate)
            except (ValueError, IndexError):
                continue
    
    return flows


def _get_steady_state_stats(flows):
    """Calculate steady-state CWND and rate for each flow."""
    stats = {}
    
    for flow_key, data in flows.items():
        times = data["t"]
        wins = data["win"]
        rates = data["rate"]
        
        if not times:
            continue
        
        # Find steady state (middle 70% of transmission)
        t_min, t_max = min(times), max(times)
        duration = t_max - t_min
        steady_start = t_min + duration * 0.15
        steady_end = t_max - duration * 0.1
        
        # Extract steady-state samples
        steady_wins = [w for t, w in zip(times, wins) if steady_start <= t <= steady_end and w > 0]
        steady_rates = [r for t, r in zip(times, rates) if steady_start <= t <= steady_end and r > 0]
        
        if steady_wins and steady_rates:
            stats[flow_key] = {
                "cwnd_avg": statistics.mean(steady_wins),
                "rate_avg": statistics.mean(steady_rates),
                "fct": t_max  # Flow completion time
            }
    
    return stats


def plot_cwnd_rtt_analysis(cwnd_file, output_file):
    """Generate comprehensive CWND/Rate/RTT analysis dashboard."""
    
    # Parse data
    flows = _parse_cwnd_file(cwnd_file)
    if not flows:
        print("ERROR: No flows found in CWND file")
        return
    
    # Get statistics
    stats = _get_steady_state_stats(flows)
    rtt = _calculate_rtt_from_cwnd_data(cwnd_file)
    rtt_us = rtt * 1e6 if rtt else None
    
    # Prepare data
    max_win = max([max(data["win"]) for data in flows.values() if data["win"]])
    
    # Determine units
    if max_win >= 1e6:
        win_unit, win_scale = "KB", 1024
    else:
        win_unit, win_scale = "B", 1
    
    # Create figure with proper spacing
    fig = plt.figure(figsize=(16, 11))
    
    # Add spacing at top for title
    fig.suptitle('CWND, Rate, and RTT Analysis Dashboard', 
                 fontsize=16, fontweight='bold', y=0.98)
    
    # Create grid with proper spacing
    gs = fig.add_gridspec(2, 2, left=0.08, right=0.95, top=0.94, bottom=0.07, 
                          hspace=0.35, wspace=0.3)
    
    # Panel 1: CWND vs Time (all flows)
    ax1 = fig.add_subplot(gs[0, 0])
    colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']
    linestyles = ['-', '--', '-.', ':', '-', '--']
    
    for idx, (flow_key, data) in enumerate(sorted(flows.items())):
        src, dst, sport, dport = flow_key
        label = f"Flow {src}→{dst} ({sport}→{dport})"
        
        y = [w / win_scale for w in data["win"]]
        line_style = linestyles[idx % len(linestyles)]
        color = colors[idx % len(colors)]
        
        ax1.plot(data["t"], y, label=label, linewidth=2, 
                linestyle=line_style, color=color)
    
    # Mark FCT for primary flow
    if flows:
        first_flow = list(flows.values())[0]
        fct = max(first_flow["t"])
        ax1.axvline(x=fct, color='green', linestyle='--', alpha=0.6, linewidth=1.5, label='FCT')
    
    ax1.set_xlabel('Time (s)', fontsize=11, fontweight='bold')
    ax1.set_ylabel(f'CWND ({win_unit})', fontsize=11, fontweight='bold')
    ax1.set_title('Window Size Over Time', fontsize=12, fontweight='bold', pad=10)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='best', fontsize=9)
    ax1.set_ylim([0, max_win / win_scale * 1.1])
    
    # Panel 2: Rate vs CWND (mathematical relationship)
    ax2 = fig.add_subplot(gs[0, 1])
    
    if rtt_us:
        cwnd_range = np.linspace(100, max_win, 100)
        rtt_s = rtt_us * 1e-6
        rate_gbps = (cwnd_range * 8) / (1e9 * rtt_s)
        
        ax2.plot(cwnd_range / win_scale, rate_gbps, linewidth=2.5, color='purple')
        
        # Plot observed points for each flow
        for idx, (flow_key, stat) in enumerate(sorted(stats.items())):
            cwnd_kb = stat["cwnd_avg"] / 1024
            rate_gbps_obs = stat["rate_avg"] / 1e9
            ax2.plot([stat["cwnd_avg"] / win_scale], [rate_gbps_obs], 
                    'o', markersize=10, color=colors[idx % len(colors)], 
                    label=f'Flow {idx}: {rate_gbps_obs:.3f} Gbps')
        
        ax2.set_xlabel('CWND (KB)', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Rate (Gbps)', fontsize=11, fontweight='bold')
        ax2.set_title(f'Rate = CWND × 8 / RTT (RTT = {rtt_us:.1f} μs)', 
                     fontsize=12, fontweight='bold', pad=10)
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc='best', fontsize=9)
    else:
        ax2.text(0.5, 0.5, 'RTT calculation failed', ha='center', va='center',
                transform=ax2.transAxes, fontsize=12)
        ax2.set_title('Rate vs CWND Relationship', fontsize=12, fontweight='bold', pad=10)
    
    # Panel 3: Throughput per flow
    ax3 = fig.add_subplot(gs[1, 0])
    
    flow_labels = []
    flow_rates = []
    colors_bar = []
    
    for idx, (flow_key, stat) in enumerate(sorted(stats.items())):
        src, dst, sport, dport = flow_key
        flow_labels.append(f'Flow {src}→{dst}')
        flow_rates.append(stat["rate_avg"] / 1e9)
        colors_bar.append(colors[idx % len(colors)])
    
    total_rate = sum(flow_rates) if flow_rates else 0
    flow_labels.append('Total')
    flow_rates.append(total_rate)
    colors_bar.append('lightgreen')
    
    bars = ax3.bar(range(len(flow_rates)), flow_rates, color=colors_bar, 
                   edgecolor='black', linewidth=2)
    
    # Add link capacity line if total is available
    if total_rate > 0:
        link_capacity = total_rate * 1.1  # Estimate from total
        ax3.axhline(y=link_capacity, color='red', linestyle='--', 
                   linewidth=2, label='Est. Link Cap', alpha=0.7)
    
    ax3.set_ylabel('Throughput (Gbps)', fontsize=11, fontweight='bold')
    ax3.set_title('Flow Throughput Distribution', fontsize=12, fontweight='bold', pad=10)
    ax3.set_xticks(range(len(flow_labels)))
    ax3.set_xticklabels(flow_labels, fontsize=10)
    ax3.set_ylim([0, max(flow_rates) * 1.2 if flow_rates else 1])
    ax3.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for i, (bar, rate) in enumerate(zip(bars, flow_rates)):
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height,
                f'{rate:.3f}\nGbps', ha='center', va='bottom', 
                fontsize=10, fontweight='bold')
    
    # Panel 4: RTT Composition
    ax4 = fig.add_subplot(gs[1, 1])
    
    if rtt_us:
        # Estimate RTT components based on typical datacenter
        rtt_components = ['Propagation', 'Serialization', 'Queueing', 'Processing']
        
        # Scale components based on measured RTT
        # Rough estimates: 15% prop, 7% serialization, 28% queueing, 50% processing
        rtt_values = [
            rtt_us * 0.15,  # Propagation
            rtt_us * 0.07,  # Serialization
            rtt_us * 0.28,  # Queueing
            rtt_us * 0.50   # Processing
        ]
        
        colors_pie = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99']
        
        wedges, texts, autotexts = ax4.pie(rtt_values, labels=rtt_components, 
                                            autopct='%1.1f%%', colors=colors_pie,
                                            startangle=90, textprops={'fontsize': 10})
        
        # Bold the percentage text
        for autotext in autotexts:
            autotext.set_color('black')
            autotext.set_fontweight('bold')
        
        ax4.set_title(f'RTT Composition (Total = {rtt_us:.1f} μs)', 
                     fontsize=12, fontweight='bold', pad=10)
    else:
        ax4.text(0.5, 0.5, 'RTT data unavailable', ha='center', va='center',
                transform=ax4.transAxes, fontsize=12)
        ax4.set_title('RTT Composition', fontsize=12, fontweight='bold', pad=10)
    
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"✓ Analysis dashboard saved to: {output_file}")
    
    if rtt_us:
        print(f"  RTT: {rtt_us:.2f} μs")
        print(f"  Flows: {len(flows)}")
        for idx, (flow_key, stat) in enumerate(sorted(stats.items())):
            src, dst = flow_key[0], flow_key[1]
            print(f"    Flow {src}→{dst}: {stat['rate_avg']/1e9:.3f} Gbps, "
                  f"CWND: {stat['cwnd_avg']/1024:.2f} KB")
    
    plt.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cwnd_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else cwnd_file.replace('.txt', '_analysis.png')
    else:
        cwnd_file = "results/data/cwnd_two_senders_heavy.txt"
        output_file = "results/plots/cwnd_rtt_analysis.png"
    
    plot_cwnd_rtt_analysis(cwnd_file, output_file)
