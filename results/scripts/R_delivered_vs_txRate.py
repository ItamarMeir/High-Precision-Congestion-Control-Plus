import matplotlib.pyplot as plt
import os
import sys
from collections import defaultdict

def main():
    # Use relative paths instead of hardcoded /workspace
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    data_dir = os.path.join(project_root, 'results', 'study_cases', 'case4_test', 'data')
    debug_file = os.path.join(data_dir, 'debug_txrate.txt')
    
    if not os.path.exists(debug_file):
        print(f"File not found: {debug_file}")
        sys.exit(1)
        
    print(f"Reading {debug_file}...")
    
    data = defaultdict(lambda: {'time_ms': [], 'R_delivered': [], 'sw_txRate': []})
    
    with open(debug_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 4:
                try:
                    time_ns = float(parts[0])
                    sender_id = int(parts[1])
                    r_deliv = float(parts[2])
                    tx_rate = float(parts[3])
                    
                    data[sender_id]['time_ms'].append(time_ns / 1e6)
                    data[sender_id]['R_delivered'].append(r_deliv / 1e9)
                    data[sender_id]['sw_txRate'].append(tx_rate / 1e9)
                except ValueError:
                    continue
                    
    senders = sorted(list(data.keys()))
    
    if len(senders) == 0:
        print("No sender data found.")
        sys.exit(1)
        
    # Plot
    fig, axes = plt.subplots(nrows=len(senders), ncols=1, figsize=(12, 10), sharex=True)
    if len(senders) == 1:
        axes = [axes]
        
    for i, sender in enumerate(senders):
        ax = axes[i]
        
        ax.plot(data[sender]['time_ms'], data[sender]['R_delivered'], label='R_delivered', alpha=0.8, linewidth=1.5)
        ax.plot(data[sender]['time_ms'], data[sender]['sw_txRate'], label='SW_hop txRate', alpha=0.6, linewidth=1.5)
        
        ax.set_title(f'Sender {sender}')
        ax.set_ylabel('Rate (Gbps)')
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.legend()
        
    axes[-1].set_xlabel('Time (ms)')
    
    plt.tight_layout()
    plots_dir = os.path.join(project_root, 'results', 'study_cases', 'case4_test', 'plots')
    if not os.path.exists(plots_dir):
        os.makedirs(plots_dir)
    out_path = os.path.join(plots_dir, 'debug_rdelivered_vs_txrate.png')
    plt.savefig(out_path, dpi=150)
    print(f"Plot saved to: {out_path}")

if __name__ == "__main__":
    main()
