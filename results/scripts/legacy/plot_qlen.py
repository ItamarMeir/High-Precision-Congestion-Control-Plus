#!/usr/bin/env python
"""Quick visualization of queue length data"""
import matplotlib.pyplot as plt
import sys

def plot_qlen(filename):
    times = []
    qlens = []
    
    with open(filename, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                try:
                    times.append(float(parts[0]) / 1e9)  # Convert to seconds
                    qlens.append(int(parts[1]))
                except:
                    continue
    
    if not times:
        print("No data found in file")
        return
    
    plt.figure(figsize=(12, 6))
    plt.plot(times, qlens, linewidth=0.5)
    plt.xlabel('Time (s)')
    plt.ylabel('Queue Length (bytes)')
    plt.title('Queue Length Over Time')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    output_file = filename.replace('.txt', '.png')
    plt.savefig(output_file, dpi=150)
    print("Plot saved to: " + output_file)
    plt.close()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        plot_qlen(sys.argv[1])
    else:
        plot_qlen('simulation/mix/qlen.txt')
