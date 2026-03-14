#!/usr/bin/env python3
"""
Master plotting script - generates all simulation analysis plots
Runs all major visualization scripts in sequence
"""

import os
import sys
import subprocess
import shutil
import argparse
from pathlib import Path

# Get results directory
# Get results directory by default, but allow override
DEFAULT_RESULTS_DIR = Path(__file__).parent.resolve()
RESULTS_DIR = DEFAULT_RESULTS_DIR 
DATA_DIR = RESULTS_DIR / "data"
PLOTS_DIR = RESULTS_DIR / "plots"
INTERACTIVE_PLOTS_DIR = RESULTS_DIR / "interactive_plots"
SCRIPTS_DIR = DEFAULT_RESULTS_DIR / "scripts"

def setup_directories(base_dir=None):
    global RESULTS_DIR, DATA_DIR, PLOTS_DIR, INTERACTIVE_PLOTS_DIR
    if base_dir:
        RESULTS_DIR = Path(base_dir).resolve()
    
    DATA_DIR = RESULTS_DIR / "data"
    PLOTS_DIR = RESULTS_DIR / "plots"
    INTERACTIVE_PLOTS_DIR = RESULTS_DIR / "interactive_plots"
    
    # Ensure directories exist
    if not DATA_DIR.exists():
        print(f"❌ Data directory not found: {DATA_DIR}")
        sys.exit(1)
        
    PLOTS_DIR.mkdir(exist_ok=True)
    INTERACTIVE_PLOTS_DIR.mkdir(exist_ok=True)
    
    print(f"📂 Working directory: {RESULTS_DIR}")
    print(f"   Data: {DATA_DIR}")
    print(f"   Plots: {PLOTS_DIR}")

# List of all plot scripts to run (order matters for dependencies)
PLOT_SCRIPTS = [
    ("plot_topology.py", "Network Topology Visualization"),
    # ("plot_qlen.py", "Queue Length Analysis"), # Unified into queue metrics
    ("plot_fct.py", "Flow Completion Time Analysis"),
    ("plot_rx_buffer.py", "RX Buffer Occupancy"),
    ("plot_packet_drops.py", "Packet Drop Analysis"),
    ("plot_queue_metrics.py", "Queue Metrics Analysis"),
    ("plot_utilization_metrics.py", "Utilization Metrics Analysis"),
    ("plot_utilization_metrics_interactive.py", "Interactive Utilization Metrics Analysis"),
    ("plot_ack_analysis.py", "ACK Analysis Dashboard"),
    ("plot_cwnd_rtt_analysis.py", "CWND/Rate Analysis Dashboard"),
    ("plot_switch_throughput.py", "Switch Throughput"),
    ("plot_dashboard.py", "Comprehensive Dashboard"),
    ("plot_interactive_dashboard.py", "Interactive Dashboard"),
    ("plot_ack_analysis_interactive.py", "Interactive ACK Analysis Dashboard"),
]

INTERACTIVE_PLOTS_DIR = RESULTS_DIR / "interactive_plots"
INTERACTIVE_PLOTS_DIR.mkdir(exist_ok=True)
def find_data_files():
    """Find all relevant data files in the data directory"""
    data_files = {}
    
    # Look for key data files (.txt, .tr, .csv)
    for ext in ["*.txt", "*.tr", "*.csv"]:
        for file in DATA_DIR.glob(ext):
            if "fat" in file.name or "topology" in file.name:
                continue
            data_files[file.name] = file
    
    return data_files

def find_config_file(exp_name=None):
    """Find configuration file for an experiment with robust fallback logic."""
    # 1. Direct match based on experiment name
    if exp_name:
        config_name = f"config_{exp_name}.txt"
        candidates = [
            RESULTS_DIR / "config" / config_name,
            RESULTS_DIR / "configs" / config_name,
            DEFAULT_RESULTS_DIR.parent / "simulation" / "mix" / "configs" / config_name
        ]
        for c in candidates:
            if c.exists(): return c

    # 2. Fallback: Any file starting with 'config' in the local config/ directory
    for subdir in ["config", "configs"]:
        cfg_dir = RESULTS_DIR / subdir
        if cfg_dir.exists():
            # Be more specific: must contain 'config' and end with .txt
            txt_files = [f for f in cfg_dir.glob("*.txt") if "config" in f.name.lower()]
            if txt_files:
                return txt_files[0]
                
    # 3. Global default
    global_default = DEFAULT_RESULTS_DIR.parent / "simulation" / "mix" / "configs" / "config_two_senders_per_node.txt"
    if global_default.exists():
        return global_default
        
    return None

def extract_file_from_config(config_file, key):
    """Extract a file path from NS-3 config file."""
    if not config_file or not os.path.exists(config_file):
        return None
    try:
        with open(config_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split()
                    if parts[0] == key and len(parts) >= 2:
                        path_str = parts[1]
                        # Resolve path relative to config file if not absolute
                        if not os.path.isabs(path_str):
                            # Try relative to results dir first, then config dir
                            candidates = [
                                RESULTS_DIR / path_str,
                                Path(config_file).parent / path_str,
                                DEFAULT_RESULTS_DIR.parent / "simulation" / path_str
                            ]
                            for c in candidates:
                                if c.exists(): return c.resolve()
                        return Path(path_str).resolve()
    except:
        pass
    return None

def run_plot_script(script_name, description, data_files):
    """Run a single plot script with available data files"""
    script_path = SCRIPTS_DIR / script_name
    
    if not script_path.exists():
        print(f"⚠️  Skipping {description}: Script not found")
        return False
    
    print(f"\n{'='*70}")
    print(f"Running: {description}")
    print(f"Script: {script_name}")
    print(f"{'='*70}")
    
    try:
        if "topology" in script_name:
            # This script visualizes the network topology
            # 1. Try to find config to get real topology/flow files
            config_file = find_config_file()
            topo_file = extract_file_from_config(config_file, "TOPOLOGY_FILE")
            flows_file = extract_file_from_config(config_file, "FLOW_FILE")

            if not topo_file or not topo_file.exists():
                topo_file = (DEFAULT_RESULTS_DIR.parent / "simulation" / "mix" / "topologies" / "topology_two_senders.txt").resolve()
            
            if not topo_file.exists():
                topo_file = DATA_DIR / "topology.txt"
            
            if topo_file.exists():
                cmd = [sys.executable, str(script_path), 
                       str(topo_file),
                       "--out", str(PLOTS_DIR / "topology_analysis.png")]
                
                if flows_file and flows_file.exists():
                    cmd.extend(["--flows", str(flows_file)])
                    print(f"Generating unified topology analysis (using {flows_file.name})...")
                else:
                    print(f"Generating topology analysis (Full view only)...")

                print(f"Command: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
                
                if result.returncode == 0:
                    if result.stdout:
                        print(result.stdout)
                    print(f"✓ {description} completed successfully")
                    return True
                else:
                    print(f"✗ {description} failed")
                    if result.stderr:
                        print(result.stderr)
                    return False
            else:
                print(f"⚠️  Skipping {description}: Topology file not found")
                return False
        
        elif "switch_throughput" in script_name:
            # This script needs --trace, --topo, and --flows flags
            trace_files = sorted(DATA_DIR.glob("mix_*.tr"))
            
            if trace_files:
                for trace_file in trace_files:
                    exp_name = trace_file.stem
                    # Infer config file (strip "mix_" prefix added by trace naming)
                    config_exp = exp_name.replace("mix_", "", 1) if exp_name.startswith("mix_") else exp_name
                    config_file = find_config_file(config_exp)

                    topo_file = extract_file_from_config(config_file, "TOPOLOGY_FILE")
                    if not topo_file or not topo_file.exists():
                        topo_file = DEFAULT_RESULTS_DIR.parent / "simulation" / "mix" / "topologies" / "topology_two_senders.txt"
                    
                    flows_file = extract_file_from_config(config_file, "FLOW_FILE")
                    if not flows_file or not flows_file.exists():
                         flows_file = (DEFAULT_RESULTS_DIR.parent / "simulation" / "mix" / "flows" / "flow_two_senders_long.txt").resolve()

                    if trace_file.exists():
                        cmd = [sys.executable, str(script_path), 
                               "--trace", str(trace_file),
                               "--out", str(PLOTS_DIR / f"switch_throughput_{exp_name}.png")]
                        
                        if config_file:
                            cmd.extend(["--config", str(config_file)])
                        
                        if topo_file and topo_file.exists():
                             cmd.extend(["--topo", str(topo_file)])
                        if flows_file and flows_file.exists():
                             cmd.extend(["--flows", str(flows_file)])
                        
                        print(f"Command: {' '.join(cmd)}")
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900) # Large timeout for big traces (1.2GB)
                        
                        if result.returncode == 0:
                            print(f"✓ {description} ({trace_file.name}) completed successfully")
                            if result.stdout:
                                print(result.stdout)
                        else:
                            print(f"✗ {description} ({trace_file.name}) failed")
                            if result.stderr:
                                print(f"Error: {result.stderr[:300]}")
                            return False
                return True
            else:
                print(f"⚠️  Skipping {description}: No trace files found")
                return False

        elif "cwnd_rtt_analysis" in script_name:
            # This script generates CWND/RTT analysis dashboard
            # Find all cwnd files
            cwnd_files = list(DATA_DIR.glob("cwnd_*.tr")) + list(DATA_DIR.glob("cwnd_*.txt"))
            
            if cwnd_files:
                for cwnd_file in cwnd_files:
                    exp_name = cwnd_file.stem.replace("cwnd_", "")
                    config_file = find_config_file(exp_name)

                    # Try to get topo from config
                    topo_file = extract_file_from_config(config_file, "TOPOLOGY_FILE")
                    if not topo_file or not topo_file.exists():
                        topo_file = (DEFAULT_RESULTS_DIR.parent / "simulation" / "mix" / "topologies" / "topology_two_senders.txt").resolve()
                    
                    cmd = [sys.executable, str(script_path), 
                               str(cwnd_file),
                               str(PLOTS_DIR / f"cwnd_rate_analysis_{exp_name}.png")]
                    
                    if config_file:
                        cmd.append(str(config_file))
                    if topo_file.exists():
                        cmd.append(str(topo_file))

                    # Keep full-fidelity parsing and cap plotted points per flow.
                    cwnd_size_mb = cwnd_file.stat().st_size / (1024 * 1024)
                    stride = 1
                    max_pts = 1000000
                    cmd.extend([
                        "--read-stride", str(stride),
                        "--max-points-per-flow", str(max_pts),
                        "--max-flows", "16",
                        "--max-flows-plot", "4",
                        "--plot-start-time", "0.0",
                    ])
                    print(f"  CWND trace {cwnd_size_mb:.0f} MB → stride={stride}, max_pts={max_pts}")
                    
                    print(f"Command: {' '.join(cmd)}")
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=900) # Increased default timeout for large traces
                    
                    if result.returncode == 0:
                        print(f"✓ {description} ({cwnd_file.name}) completed successfully")
                        if result.stdout:
                            print(result.stdout)
                    else:
                        print(f"✗ {description} ({cwnd_file.name}) failed")
                        if result.stderr:
                            print(f"Error: {result.stderr[:300]}")
                        return False
                return True
            else:
                print(f"⚠️  Skipping {description}: No CWND data file found")
                return False

        elif "plot_ack_analysis" in script_name:
            # Shared logic for static and interactive ack analysis
            cwnd_files = list(DATA_DIR.glob("cwnd_*.tr")) + list(DATA_DIR.glob("cwnd_*.txt"))
            
            if cwnd_files:
                for cwnd_file in cwnd_files:
                    exp_name = cwnd_file.stem.replace("cwnd_", "")
                    config_file = find_config_file(exp_name)
                    
                    ext = ".html" if "interactive" in script_name else ".png"
                    out_dir = INTERACTIVE_PLOTS_DIR if "interactive" in script_name else PLOTS_DIR
                    out_file = out_dir / f"ack_analysis_{exp_name}{ext}"
                    
                    cmd = [sys.executable, str(script_path), str(cwnd_file), str(out_file)]

                    # Keep positional args before optional flags for argparse compatibility.
                    if config_file:
                        cmd.append(str(config_file))

                    if "interactive" in script_name:
                        cmd.extend(["--max-points-per-flow", "30000"])
                    else:
                        cmd.extend(["--max-points-per-flow", "60000"])
                    cmd.extend(["--read-stride", "1"])
                    
                    print(f"Command: {' '.join(cmd)}")
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)  # Large timeout for big cwnd files
                    
                    if result.returncode == 0:
                        print(f"✓ {description} ({cwnd_file.name}) completed successfully")
                        if result.stdout:
                            print(result.stdout)
                    else:
                        print(f"✗ {description} ({cwnd_file.name}) failed")
                        if result.stderr:
                            print(f"Error: {result.stderr[:300]}")
                        return False
                return True
            else:
                print(f"⚠️  Skipping {description}: No CWND data file found")
                return False

        elif "queue_metrics" in script_name:
            # This script needs --qlen, optional --pfc, and --out-dir
            # Find all qlen files
            qlen_files = list(DATA_DIR.glob("qlen_*.txt"))
            queue_depth_tr = DATA_DIR / "queue_depth.tr"
            queue_depth_csv = DATA_DIR / "queue_depth.csv"
            
            if qlen_files or queue_depth_tr.exists() or queue_depth_csv.exists():
                # Prefer INT binary queue depth for binary pipeline
                queue_depth_file = queue_depth_tr if queue_depth_tr.exists() else queue_depth_csv

                if qlen_files:
                    for qlen_file in qlen_files:
                        exp_name = qlen_file.stem.replace("qlen_", "")
                        pfc_file = DATA_DIR / f"pfc_{exp_name}.txt"
                        if not pfc_file.exists():
                            pfc_file = DATA_DIR / f"pfc_{exp_name}.tr"
                        
                        # Infer config file
                        exp_name = qlen_file.stem.replace("qlen_", "")
                        config_file = find_config_file(exp_name)

                        cmd = [sys.executable, str(script_path), 
                               "--qlen", str(qlen_file),
                               "--out-dir", str(PLOTS_DIR)]
                        
                        if pfc_file.exists():
                            cmd.extend(["--pfc", str(pfc_file)])

                        if config_file:
                            cmd.extend(["--config", str(config_file)])

                        if queue_depth_file and queue_depth_file.exists():
                            cmd.extend(["--queue-depth-csv", str(queue_depth_file)])
                            
                        print(f"Command: {' '.join(cmd)}")
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
                        
                        if result.returncode == 0:
                            print(f"✓ {description} ({qlen_file.name}) completed successfully")
                            if result.stdout:
                                print(result.stdout)
                        else:
                            print(f"✗ {description} ({qlen_file.name}) failed")
                            if result.stderr:
                                 print(f"Error: {result.stderr[:300]}")
                                 return False
                    return True

                # If qlen_*.txt is absent, still run queue metrics once using INT queue depth.
                cmd = [sys.executable, str(script_path), "--out-dir", str(PLOTS_DIR)]
                if queue_depth_file and queue_depth_file.exists():
                    cmd.extend(["--queue-depth-csv", str(queue_depth_file)])

                # Use best-effort config discovery.
                config_file = find_config_file()
                if config_file:
                    cmd.extend(["--config", str(config_file)])

                # Use first available PFC trace (binary preferred, then text).
                pfc_candidates = sorted(DATA_DIR.glob("pfc_*.tr")) + sorted(DATA_DIR.glob("pfc_*.txt"))
                if pfc_candidates:
                    cmd.extend(["--pfc", str(pfc_candidates[0])])

                print(f"Command: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
                if result.returncode == 0:
                    print(f"✓ {description} (INT queue depth mode) completed successfully")
                    if result.stdout:
                        print(result.stdout)
                    return True
                print(f"✗ {description} (INT queue depth mode) failed")
                if result.stderr:
                    print(f"Error: {result.stderr[:300]}")
                return False
            else:
                 print(f"⚠️  Skipping {description}: No qlen files found")
                 return False

        elif "utilization_metrics" in script_name:
            utilization_files = list(DATA_DIR.glob("utilization_*.txt"))

            if utilization_files:
                for utilization_file in utilization_files:
                    exp_name = utilization_file.stem.replace("utilization_", "")
                    config_file = find_config_file(exp_name)
                    if "interactive" in script_name:
                        cmd = [sys.executable, str(script_path), str(utilization_file),
                               str(INTERACTIVE_PLOTS_DIR / f"utilization_{exp_name}.html")]
                    else:
                        cmd = [sys.executable, str(script_path), str(utilization_file),
                               "--out", str(PLOTS_DIR / f"utilization_{exp_name}.png")]

                    if config_file:
                        if "interactive" in script_name:
                            cmd.append(str(config_file))
                        else:
                            cmd.extend(["--config", str(config_file)])

                    print(f"Command: {' '.join(cmd)}")
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)

                    if result.returncode == 0:
                        print(f"✓ {description} ({utilization_file.name}) completed successfully")
                        if result.stdout:
                            print(result.stdout)
                    else:
                        print(f"✗ {description} ({utilization_file.name}) failed")
                        if result.stderr:
                            print(f"Error: {result.stderr[:300]}")
                        return False
                return True
            else:
                print(f"⚠️  Skipping {description}: No utilization trace file found")
                return False
        
        elif "plot_rx_buffer" in script_name or "rx_buffer" in script_name:
            # This script needs RX buffer trace
            # Find all rxbuf files
            rxbuf_files = list(DATA_DIR.glob("rxbuf_*.tr")) + list(DATA_DIR.glob("rxbuf_*.txt"))
            
            if rxbuf_files:
                for rxbuf_file in rxbuf_files:
                    # Infer config file
                    # rxbuf_dynamic_pull.txt -> config_dynamic_pull.txt
                    exp_name = rxbuf_file.stem.replace("rxbuf_", "")
                    config_file = find_config_file(exp_name)
                    
                    cmd = [sys.executable, str(script_path), str(rxbuf_file),
                           "--out", str(PLOTS_DIR / f"rx_buffer_{exp_name}.png")]
                    
                    if config_file:
                        cmd.extend(["--config", str(config_file)])
                        
                    print(f"Command: {' '.join(cmd)}")
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
                    if result.returncode == 0:
                        print(f"✓ {description} ({rxbuf_file.name}) completed successfully")
                        if result.stdout:
                            print(result.stdout)
                    else:
                        print(f"✗ {description} ({rxbuf_file.name}) failed")
                        if result.stderr:
                            print(f"Error: {result.stderr[:300]}")
                        return False
                return True
            else:
                print(f"⚠️  Skipping {description}: No RX buffer file found")
                return False

        elif "plot_fct" in script_name:
             # FCT Plot
             # Find all fct files
             fct_files = list(DATA_DIR.glob("fct_*.tr")) + list(DATA_DIR.glob("fct_*.txt"))
             if fct_files:
                 for fct_file in fct_files:
                     exp_name = fct_file.stem.replace("fct_", "")
                     cmd = [sys.executable, str(script_path), str(fct_file),
                            "--out", str(PLOTS_DIR / f"fct_{exp_name}.png")]
                     print(f"Command: {' '.join(cmd)}")
                     result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
                     if result.returncode == 0:
                         print(f"✓ {description} ({fct_file.name}) completed successfully")
                         if result.stdout:
                             print(result.stdout)
                     else:
                         print(f"✗ {description} ({fct_file.name}) failed")
                         if result.stderr:
                             print(f"Error: {result.stderr[:300]}")
                 return True
             else:
                 print(f"⚠️  Skipping {description}: No FCT file found")
                 return False

        elif "packet_drops" in script_name or "drop" in script_name:
            # This script needs packet drop trace AND pfc trace for unified plot
            # Find all drop files
            drop_files = list(DATA_DIR.glob("drop_*.tr")) + list(DATA_DIR.glob("drop_*.txt"))
            
            if drop_files:
                for drop_file in drop_files:
                    exp_name = drop_file.stem.replace("drop_", "")
                    pfc_file = DATA_DIR / f"pfc_{exp_name}.txt"
                    if not pfc_file.exists():
                        pfc_file = DATA_DIR / f"pfc_{exp_name}.tr"
                    
                    cmd = [sys.executable, str(script_path), 
                           "-o", str(PLOTS_DIR / f"reliability_analysis_{exp_name}.png")]
                    
                    cmd.extend(["--drops", str(drop_file)])
                    
                    if pfc_file.exists():
                        cmd.extend(["--pfc", str(pfc_file)])
                        
                    print(f"Command: {' '.join(cmd)}")
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
                    if result.returncode == 0:
                        print(f"✓ {description} ({drop_file.name}) completed successfully")
                        if result.stdout:
                            print(result.stdout)
                    else:
                        print(f"✗ {description} ({drop_file.name}) failed")
                        if result.stderr:
                            print(f"Error: {result.stderr[:300]}")
                return True
            else:
                print(f"✓ {description}: No drop files found (Clean Run)")
                return True 

        elif "dashboard" in script_name and "interactive" not in script_name:
             # Comprehensive Dashboard (Matplotlib)
             # Needs FCT and Qlen files
             fct_files = list(DATA_DIR.glob("fct_*.tr")) + list(DATA_DIR.glob("fct_*.txt"))
             
             if fct_files:
                 for fct_file in fct_files:
                     exp_name = fct_file.stem.replace("fct_", "")
                     qlen_file = DATA_DIR / f"qlen_{exp_name}.txt"
                     
                     cmd = [sys.executable, str(script_path), 
                            "--out", str(PLOTS_DIR / f"dashboard_{exp_name}.png"),
                            "--fct", str(fct_file)]
                     
                     if qlen_file.exists():
                         cmd.extend(["--qlen", str(qlen_file)])
                         
                     print(f"Command: {' '.join(cmd)}")
                     result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
                     
                     if result.returncode == 0:
                         print(f"✓ {description} ({exp_name}) completed successfully")
                         if result.stdout:
                             print(result.stdout)
                     else:
                         print(f"✗ {description} ({exp_name}) failed")
                         if result.stderr:
                             print(f"Error: {result.stderr[:300]}")
                             return False
                 return True
             else:
                 print(f"⚠️  Skipping {description}: No FCT files found for dashboard")
                 return False

        elif "interactive_dashboard" in script_name:
             # Interactive Dashboard (Plotly)
               # Find all qlen/cwnd files to get experiment names.
             qlen_files = list(DATA_DIR.glob("qlen_*.txt"))
             cwnd_files = list(DATA_DIR.glob("cwnd_*.tr")) + list(DATA_DIR.glob("cwnd_*.txt"))
             
             # Collect unique experiment names
             exp_names = set()
             for f in qlen_files: exp_names.add(f.stem.replace("qlen_", ""))
             for f in cwnd_files: exp_names.add(f.stem.replace("cwnd_", ""))
             
             if exp_names:
                 for exp_name in sorted(exp_names):
                     config_file = find_config_file(exp_name)
                     
                     cmd = [sys.executable, str(script_path), 
                            "--data-dir", str(DATA_DIR),
                            "--out-dir", str(INTERACTIVE_PLOTS_DIR),
                        "--exp-name", exp_name,
                        "--throughput-peak-envelope"]
                     
                     if config_file:
                         cmd.extend(["--config", str(config_file)])
                         
                     print(f"Command: {' '.join(cmd)}")
                     result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                     
                     if result.returncode == 0:
                         print(f"✓ {description} ({exp_name}) completed successfully")
                     else:
                         print(f"✗ {description} ({exp_name}) failed")
                         if result.stderr:
                             print(f"Error: {result.stderr[:300]}")
                 return True
             else:
                 print(f"⚠️  Skipping {description}: No experiment data found")
                 return False
        
        # Default behavior: try to find matching data file
        for data_file in sorted(data_files):
            cmd = [sys.executable, str(script_path), str(DATA_DIR / data_file)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            
            if result.returncode == 0:
                print(f"✓ {description} completed successfully")
                if result.stdout:
                    print(result.stdout)
                return True
        
        # If no data files worked, try running without arguments
        print("Attempting to run without arguments...")
        result = subprocess.run([sys.executable, str(script_path)], 
                              capture_output=True, text=True, timeout=900)
        
        if result.returncode == 0:
            print(f"✓ {description} completed successfully")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"✗ {description} failed")
            if result.stderr:
                print(f"Error: {result.stderr[:300]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"✗ {description} timed out")
        return False
    except Exception as e:
        print(f"✗ {description} encountered error: {e}")
        return False

def main():
    """Main function to run all plots"""
    parser = argparse.ArgumentParser(description="Master plotting script for HPCC simulations")
    parser.add_argument("--base-dir", help="Base directory containing data/ and plots/ subdirectories")
    args = parser.parse_args()

    print("\n" + "="*70)
    print("HPCC Simulation - Master Plotting Script")
    print("="*70)
    
    setup_directories(args.base_dir)
    
    # Find available data files
    data_files = find_data_files()
    
    if not data_files:
        print("⚠️  No data files found in data directory")
    else:
        print(f"\n📊 Found {len(data_files)} data file(s):")
        for fname in sorted(data_files.keys()):
            print(f"   - {fname}")
    
    # Run all plot scripts
    results = {}
    for script_name, description in PLOT_SCRIPTS:
        results[description] = run_plot_script(script_name, description, data_files.keys())
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    successful = sum(1 for v in results.values() if v)
    total = len(results)
    
    for description, success in results.items():
        status = "✓" if success else "✗"
        print(f"{status} {description}")
    
    print(f"\nCompleted: {successful}/{total} scripts")
    
    if successful == total:
        print("\n✓ All plotting scripts completed successfully!")
        print(f"✓ Plots organized in: {PLOTS_DIR}")
        return 0
    else:
        print(f"\n⚠️  {total - successful} script(s) failed or were skipped")
        print(f"✓ Generated plots available in: {PLOTS_DIR}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
