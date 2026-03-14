import matplotlib.pyplot as plt
import sys

import struct
import os

def parse_file(filepath):
    data = []
    
    # Try binary first
    is_binary = filepath.endswith('.tr')
    if is_binary:
        try:
            # RxBufTrace: time(Q), node(I), intf(I), bytes(Q)
            fmt = "QIIQ"
            sz = struct.calcsize(fmt)
            with open(filepath, 'rb') as f:
                while True:
                    d = f.read(sz)
                    if not d or len(d) < sz: break
                    parts = struct.unpack(fmt, d)
                    data.append((parts[0] / 1e9, parts[3]))
            if data:
                return data
        except Exception as e:
            print(f"Error parsing binary file: {e}")
            is_binary = False

    with open(filepath, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 4:
                # format: time(ns) node_id port rx_buffer_bytes
                try:
                    time = int(parts[0]) / 1e9 # ns to s
                    node = int(parts[1])
                    bytes_val = int(parts[3])
                    data.append((time, bytes_val))
                except ValueError:
                    continue
    return data

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 verify_pull.py <input_file> <output_file>")
        sys.exit(1)
        
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    data = parse_file(input_file)
    times = [d[0] for d in data]
    bytes_list = [d[1] for d in data]
    
    plt.figure(figsize=(10, 6))
    plt.plot(times, bytes_list, label='RX Buffer Occupancy')
    plt.xlabel('Time (s)')
    plt.ylabel('Bytes')
    plt.title('RX Buffer Occupancy over Time (Multi-Step Schedule)')
    plt.legend()
    plt.grid(True)
    plt.savefig(output_file)
    print(f"Plot saved to {output_file}")
