#!/usr/bin/env python
"""Quick visualization of queue length data per link"""
import matplotlib.pyplot as plt
import sys

def plot_qlen(filename):
    # Format: First line "time: <nanoseconds>"
    # Then lines of "<src> <dest> <queue_length>"
    qlen_per_link = {}
    current_time = None
    
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('time:'):
                current_time = int(line.split(':')[1].strip())
                continue
            
            parts = line.split()
            if len(parts) >= 3 and current_time is not None:
                try:
                    src = int(parts[0])
                    dest = int(parts[1])
                    qlen = int(parts[2])
                    
                    link = (src, dest)
                    if link not in qlen_per_link:
                        qlen_per_link[link] = {'times': [], 'qlen': []}
                    
                    qlen_per_link[link]['times'].append(current_time / 1e9)  # Convert to seconds
                    qlen_per_link[link]['qlen'].append(qlen)
                except:
                    continue
    
    if not qlen_per_link:
        print("No data found in file")
        return
    
    plt.figure(figsize=(12, 6))
    
    # Plot all links (only if they have congestion)
    plotted = 0
    for link, data in sorted(qlen_per_link.items()):
        if data['qlen'] and max(data['qlen']) > 0:
            plt.plot(data['times'], data['qlen'], marker='o', label=f'Link {link[0]}->{link[1]}', alpha=0.7)
            plotted += 1
    
    plt.xlabel('Time (s)')
    plt.ylabel('Queue Length (bytes)')
    plt.title('Queue Length Over Time (per Link)')
    plt.grid(True, alpha=0.3)
    if plotted > 1:
        plt.legend()
    plt.tight_layout()
    
    output_file = filename.replace('.txt', '.png')
    plt.savefig(output_file, dpi=150)
    print(f"Plot saved to: {output_file} ({plotted} links with congestion)")
    plt.close()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        plot_qlen(sys.argv[1])
    else:
        plot_qlen('simulation/mix/outputs/qlen/qlen.txt')
