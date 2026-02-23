#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt

def parse_cwnd_extra(cwnd_file):
    """Parse CWND file returning flows with time, seq, and rtt."""
    flows = defaultdict(lambda: {"t": [], "seq": [], "rtt": []})
    
    with open(cwnd_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 9:
                continue
            try:
                t_ns = int(parts[0])
                src = int(parts[1])
                dst = int(parts[2])
                sport = int(parts[3])
                dport = int(parts[4])
                
                # Check if rtt and seq are available and valid
                lastRtt = int(parts[7])
                lastAckSeq = int(parts[8])
                
                key = (src, dport)  # simplify key to src and dport for flow identification
                flows[key]["t"].append(t_ns / 1e9)
                flows[key]["seq"].append(lastAckSeq)
                # Filter out garbage timestamps (integer underflows)
                # Max realistic RTT in this network is < 100ms (100,000,000 ns)
                if lastRtt < 100000000:
                    flows[key]["rtt"].append(lastRtt / 1000.0) # convert to us
                else:
                    # Append None to maintain index alignment if necessary, or just skip
                    flows[key]["rtt"].append(None)
            except (ValueError, IndexError):
                pass
                
    return flows

def _parse_schedules(config_file):
    """Parse config file to extract RX_PULL_RATE_SCHEDULE."""
    schedules = {}
    if not config_file or not Path(config_file).exists():
        return schedules
    
    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#'): continue
            if 'RX_PULL_RATE_SCHEDULE' in line:
                parts = line.split()
                if len(parts) >= 3 and parts[0] == 'RX_PULL_RATE_SCHEDULE':
                    try:
                        node_id = int(parts[1])
                        count = int(parts[2])
                        schedule = []
                        idx = 3
                        for _ in range(count):
                            if idx + 1 < len(parts):
                                t = float(parts[idx])
                                r = float(parts[idx+1])
                                schedule.append((t, r))
                                idx += 2
                        schedules[node_id] = schedule
                    except ValueError: pass
    return schedules

def _draw_lines(ax, schedules):
    for node_id, schedule in schedules.items():
            for time, rate in schedule:
                ax.axvline(x=time, color='gray', linestyle=':', alpha=0.8, linewidth=1.5)
                ax.text(time, 0.98, f' t={time}s\nRate={rate}', rotation=90, 
                        transform=ax.get_xaxis_transform(),
                        verticalalignment='top', fontsize=8, color='black', alpha=0.7)

def plot_ack_analysis(cwnd_file, output_file, config_path=None):
    flows = parse_cwnd_extra(cwnd_file)
    if not flows:
        print("ERROR: No tracking data found in CWND file. Make sure simulator logs the extra 2 columns.")
        return
        
    schedules = _parse_schedules(config_path) if config_path else {}
    
    fig = plt.figure(figsize=(12, 10))
    fig.suptitle('ACK Level Flow Analysis', fontsize=16, fontweight='bold', y=0.96)
    
    colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']
    
    # Plot 1: Stevens Plot (Sequence Number vs Time)
    ax1 = plt.subplot(211)
    
    for idx, (flow_key, data) in enumerate(sorted(flows.items())):
        src, dport = flow_key
        # unwrap sequence numbers if they wrap around
        seqs = data["seq"]
        unwrapped_seqs = []
        last_seq = 0
        offset = 0
        for s in seqs:
            if s < last_seq and (last_seq - s) > 1000000000:
                offset += 4294967296 # 2^32
            unwrapped_seqs.append(s + offset)
            last_seq = s
            
        color = colors[idx % len(colors)]
        label = f"Sender {src} (port {dport})"
        
        # Only plot senders 0 and 1
        if src in [0, 1]:
            ax1.plot(data["t"], unwrapped_seqs, label=label, linewidth=1.5, color=color, alpha=0.8)
    
    ax1.set_xlabel('Time (s)', fontsize=11, fontweight='bold')
    ax1.set_ylabel('ACK Sequence Number', fontsize=11, fontweight='bold')
    ax1.set_title('Stevens Graph (Data Delivery Over Time)', fontsize=12, fontweight='bold', pad=10)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='best', fontsize=9)
    if schedules: _draw_lines(ax1, schedules)
    
    # Plot 2: Real Measured RTT vs Time
    ax2 = plt.subplot(212)
    for idx, (flow_key, data) in enumerate(sorted(flows.items())):
        src, dport = flow_key
        color = colors[idx % len(colors)]
        label = f"Sender {src} (port {dport})"
        
        if src in [0, 1]:
            valid_t = [t for t, r in zip(data["t"], data["rtt"]) if r is not None]
            valid_r = [r for r in data["rtt"] if r is not None]
            ax2.plot(valid_t, valid_r, label=label, linewidth=1, color=color, alpha=0.6)
            
    ax2.set_xlabel('Time (s)', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Measured RTT (µs)', fontsize=11, fontweight='bold')
    ax2.set_title('Per-Packet Measured Round Trip Time', fontsize=12, fontweight='bold', pad=10)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='best', fontsize=9)
    # Cap RTT to 500us to avoid extreme spikes ruining the plot view
    # ax2.set_ylim([0, 500])
    if schedules: _draw_lines(ax2, schedules)
    
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"✓ ACK Analysis dashboard saved to: {output_file}")
    plt.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate ACK analysis")
    parser.add_argument("cwnd_file", help="Input CWND text file")
    parser.add_argument("output_file", nargs="?", help="Output PNG file")
    parser.add_argument("config_path", nargs="?", help="Configuration file path")
    args = parser.parse_args()
    
    output_file = args.output_file if args.output_file else args.cwnd_file.replace('.txt', '_ack_analysis.png')
    plot_ack_analysis(args.cwnd_file, output_file, config_path=args.config_path)
