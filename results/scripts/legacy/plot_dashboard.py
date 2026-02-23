#!/usr/bin/env python3
"""Comprehensive simulation results dashboard"""
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import sys
import os

def parse_config(config_file):
    """Parse simulation configuration"""
    config = {}
    try:
        with open(config_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split()
                    if len(parts) >= 2:
                        config[parts[0]] = ' '.join(parts[1:])
    except:
        pass
    return config

def plot_dashboard(base_dir='simulation/mix'):
    """Create a comprehensive dashboard of simulation results"""
    
    # Read data
    qlen_times, qlen_values = [], []
    fct_data = []
    config = parse_config(os.path.join(base_dir, 'config.txt'))
    
    # Parse queue length data
    qlen_file = os.path.join(base_dir, 'qlen.txt')
    if os.path.exists(qlen_file):
        with open(qlen_file, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    try:
                        qlen_times.append(float(parts[0]) / 1e9)
                        qlen_values.append(int(parts[1]))
                    except:
                        pass
    
    # Parse FCT data
    fct_file = os.path.join(base_dir, 'fct.txt')
    if os.path.exists(fct_file):
        with open(fct_file, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 8:
                    try:
                        fct_data.append({
                            'size': int(parts[7]),
                            'fct': int(parts[6]) / 1e6,  # ms
                            'base_fct': int(parts[4]) / 1e6,
                            'start': int(parts[5]) / 1e9  # s
                        })
                    except:
                        pass
    
    # Create dashboard
    fig = plt.figure(figsize=(16, 10))
    gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.3, wspace=0.3)
    
    # Title
    cc_mode = config.get('CC_MODE', 'Unknown')
    cc_names = {
        '1': 'DCQCN',
        '3': 'HPCC',
        '7': 'TIMELY',
        '8': 'DCTCP'
    }
    cc_name = cc_names.get(cc_mode, 'CC_MODE=' + cc_mode)
    
    fig.suptitle('HPCC Simulation Results Dashboard - ' + cc_name, 
                 fontsize=16, fontweight='bold')
    
    # Configuration info (top-left)
    ax_config = fig.add_subplot(gs[0, 0])
    ax_config.axis('off')
    config_text = "Configuration:\\n"
    key_params = ['CC_MODE', 'TOPOLOGY_FILE', 'FLOW_FILE', 
                  'RATE_AI', 'RATE_HAI', 'U_TARGET', 'ALPHA_RESUME_INTERVAL']
    for key in key_params:
        if key in config:
            val = config[key]
            if len(val) > 30:
                val = val[:27] + '...'
            config_text += "{}:\\n  {}\\n".format(key.replace('_', ' '), val)
    ax_config.text(0.05, 0.95, config_text, fontsize=9, family='monospace',
                   verticalalignment='top', transform=ax_config.transAxes)
    
    # Queue length over time (top-middle and top-right)
    if qlen_times:
        ax_qlen = fig.add_subplot(gs[0, 1:])
        ax_qlen.plot(qlen_times, qlen_values, linewidth=0.8, color='blue', alpha=0.7)
        ax_qlen.set_xlabel('Time (s)')
        ax_qlen.set_ylabel('Queue Length (bytes)')
        ax_qlen.set_title('Queue Length Over Time')
        ax_qlen.grid(True, alpha=0.3)
        ax_qlen.fill_between(qlen_times, qlen_values, alpha=0.2)
    
    if fct_data:
        # FCT vs Flow Size (middle-left)
        ax_fct_size = fig.add_subplot(gs[1, 0])
        sizes = [d['size'] for d in fct_data]
        fcts = [d['fct'] for d in fct_data]
        ax_fct_size.scatter(sizes, fcts, alpha=0.7, s=100, c='green', edgecolors='black')
        ax_fct_size.set_xlabel('Flow Size (bytes)')
        ax_fct_size.set_ylabel('FCT (ms)')
        ax_fct_size.set_title('Flow Completion Time')
        ax_fct_size.grid(True, alpha=0.3)
        if len(sizes) > 1:
            ax_fct_size.set_xscale('log')
            ax_fct_size.set_yscale('log')
        
        # Slowdown (middle-middle)
        ax_slowdown = fig.add_subplot(gs[1, 1])
        slowdowns = [d['fct']/d['base_fct'] if d['base_fct'] > 0 else 1 for d in fct_data]
        ax_slowdown.scatter(sizes, slowdowns, alpha=0.7, s=100, c='orange', edgecolors='black')
        ax_slowdown.set_xlabel('Flow Size (bytes)')
        ax_slowdown.set_ylabel('Slowdown (FCT/Base FCT)')
        ax_slowdown.set_title('Slowdown vs Flow Size')
        ax_slowdown.grid(True, alpha=0.3)
        ax_slowdown.axhline(y=1, color='red', linestyle='--', linewidth=2, label='Ideal')
        ax_slowdown.legend()
        if len(sizes) > 1:
            ax_slowdown.set_xscale('log')
        
        # Flow timeline (middle-right)
        ax_timeline = fig.add_subplot(gs[1, 2])
        starts = [d['start'] for d in fct_data]
        ends = [d['start'] + d['fct']/1000 for d in fct_data]  # Convert ms to s
        for i, (start, end) in enumerate(zip(starts, ends)):
            ax_timeline.barh(i, end-start, left=start, height=0.8, 
                            color='purple', alpha=0.6, edgecolor='black')
        ax_timeline.set_xlabel('Time (s)')
        ax_timeline.set_ylabel('Flow ID')
        ax_timeline.set_title('Flow Timeline')
        ax_timeline.grid(True, alpha=0.3, axis='x')
        
        # Statistics (bottom-left)
        ax_stats = fig.add_subplot(gs[2, 0])
        ax_stats.axis('off')
        stats_text = "Flow Statistics:\\n\\n"
        stats_text += "Total Flows: {}\\n\\n".format(len(fct_data))
        stats_text += "FCT (ms):\\n"
        stats_text += "  Min: {:.3f}\\n".format(min(fcts))
        stats_text += "  Max: {:.3f}\\n".format(max(fcts))
        stats_text += "  Mean: {:.3f}\\n\\n".format(sum(fcts)/len(fcts))
        stats_text += "Slowdown:\\n"
        stats_text += "  Min: {:.3f}\\n".format(min(slowdowns))
        stats_text += "  Max: {:.3f}\\n".format(max(slowdowns))
        stats_text += "  Mean: {:.3f}\\n".format(sum(slowdowns)/len(slowdowns))
        ax_stats.text(0.1, 0.95, stats_text, fontsize=10, family='monospace',
                     verticalalignment='top', transform=ax_stats.transAxes)
        
        # FCT Distribution (bottom-middle)
        ax_hist = fig.add_subplot(gs[2, 1])
        ax_hist.hist(fcts, bins=max(5, len(fcts)//2), alpha=0.7, color='teal', 
                     edgecolor='black')
        ax_hist.set_xlabel('FCT (ms)')
        ax_hist.set_ylabel('Count')
        ax_hist.set_title('FCT Distribution')
        ax_hist.grid(True, alpha=0.3, axis='y')
        
        # Slowdown Distribution (bottom-right)
        ax_slow_hist = fig.add_subplot(gs[2, 2])
        ax_slow_hist.hist(slowdowns, bins=max(5, len(slowdowns)//2), alpha=0.7, 
                         color='coral', edgecolor='black')
        ax_slow_hist.set_xlabel('Slowdown')
        ax_slow_hist.set_ylabel('Count')
        ax_slow_hist.set_title('Slowdown Distribution')
        ax_slow_hist.grid(True, alpha=0.3, axis='y')
    
    # Save
    output_file = os.path.join(base_dir, 'dashboard.png')
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print("Dashboard saved to: " + output_file)
    plt.close()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        plot_dashboard(sys.argv[1])
    else:
        plot_dashboard()
